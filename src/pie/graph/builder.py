"""Knowledge Graph Builder: constructs typed directed multigraphs from ADF metadata."""

from pie.core.logging import get_logger
from pie.discovery.models import FactoryMetadata
from pie.graph.models import (
    NodeType,
    EdgeType,
    GraphNode,
    GraphEdge,
)
from pie.graph.expression_analyzer import ExpressionAnalyzer

logger = get_logger(__name__)


def _extract_inner_activities(type_props: dict) -> list[dict]:
    """Extract inner activity definitions from ForEach, IfCondition, Until, Switch, etc.

    Returns a flat list of activity-like dicts with 'name', 'type', and 'typeProperties'.
    """
    if not isinstance(type_props, dict):
        return []

    activities: list[dict] = []

    # ForEach: typeProperties.activities[]
    for_each_acts = type_props.get("activities", [])
    if isinstance(for_each_acts, list):
        for act in for_each_acts:
            if isinstance(act, dict):
                activities.append(act)

    # IfCondition: typeProperties.ifTrueActivities[] and ifFalseActivities[]
    for branch_key in ("ifTrueActivities", "ifFalseActivities"):
        branch_acts = type_props.get(branch_key, [])
        if isinstance(branch_acts, list):
            for act in branch_acts:
                if isinstance(act, dict):
                    activities.append(act)

    # Switch: typeProps.cases[].activities[]
    cases = type_props.get("cases", [])
    if isinstance(cases, list):
        for case in cases:
            if isinstance(case, dict):
                case_acts = case.get("activities", [])
                if isinstance(case_acts, list):
                    for act in case_acts:
                        if isinstance(act, dict):
                            activities.append(act)

    return activities


class KnowledgeGraph:
    """In-memory directed Knowledge Graph representing ADF architecture and dependency lineage."""

    def __init__(self, factory_name: str = "default_factory"):
        self.factory_name = factory_name
        self.nodes: dict[str, GraphNode] = {}
        self.edges: list[GraphEdge] = []
        # Adjacency maps for fast O(1) graph traversal
        self.outgoing_adj: dict[str, list[GraphEdge]] = {}
        self.incoming_adj: dict[str, list[GraphEdge]] = {}
        self.expr_analyzer: ExpressionAnalyzer | None = None

    def add_node(self, node: GraphNode) -> None:
        """Add a vertex to the graph."""
        self.nodes[node.id] = node
        self.outgoing_adj.setdefault(node.id, [])
        self.incoming_adj.setdefault(node.id, [])

    def add_edge(self, source_id: str, target_id: str, edge_type: EdgeType, properties: dict | None = None) -> None:
        """Add a directed edge between two vertices."""
        edge = GraphEdge(
            source_id=source_id,
            target_id=target_id,
            type=edge_type,
            properties=properties or {},
        )
        self.edges.append(edge)
        self.outgoing_adj.setdefault(source_id, []).append(edge)
        self.incoming_adj.setdefault(target_id, []).append(edge)

    def get_node(self, node_id: str) -> GraphNode | None:
        """Retrieve node by ID."""
        return self.nodes.get(node_id)

    def get_node_by_name(self, name: str, node_type: NodeType | None = None) -> GraphNode | None:
        """Lookup node by simple asset name and optional type."""
        for node in self.nodes.values():
            if node.name.lower() == name.lower():
                if node_type is None or node.type == node_type:
                    return node
        return None

    def get_outgoing_edges(self, node_id: str, edge_type: EdgeType | None = None) -> list[GraphEdge]:
        """Get all outgoing directed edges from node_id."""
        edges = self.outgoing_adj.get(node_id, [])
        if edge_type is None:
            return edges
        return [e for e in edges if e.type == edge_type]

    def get_incoming_edges(self, node_id: str, edge_type: EdgeType | None = None) -> list[GraphEdge]:
        """Get all incoming directed edges to node_id."""
        edges = self.incoming_adj.get(node_id, [])
        if edge_type is None:
            return edges
        return [e for e in edges if e.type == edge_type]


class KnowledgeGraphBuilder:
    """Constructs a fully linked in-memory Knowledge Graph from normalized FactoryMetadata."""

    @staticmethod
    def build(factory_meta: FactoryMetadata) -> KnowledgeGraph:
        """Build directed knowledge graph from extracted Azure Data Factory metadata."""
        graph = KnowledgeGraph(factory_name=factory_meta.factory_name)
        logger.info(f"Building Knowledge Graph for [bold cyan]{factory_meta.factory_name}[/bold cyan]...")

        # 1. Add Linked Service Nodes
        for ls in factory_meta.linked_services:
            node_id = f"linked_service:{ls.name}"
            graph.add_node(
                GraphNode(
                    id=node_id,
                    name=ls.name,
                    type=NodeType.LINKED_SERVICE,
                    description=ls.description,
                    properties={
                        "type": ls.type,
                        "connection_properties": ls.connection_properties,
                        "connect_via_integration_runtime": ls.connect_via_integration_runtime,
                    },
                    annotations=getattr(ls, "annotations", []) or [],
                )
            )

        # 1b. Add Integration Runtime Nodes & USES_INTEGRATION_RUNTIME edges
        ir_seen: set[str] = set()
        for ls in factory_meta.linked_services:
            if ls.connect_via_integration_runtime:
                ir_name = ls.connect_via_integration_runtime
                if ir_name not in ir_seen:
                    ir_seen.add(ir_name)
                    ir_node_id = f"integration_runtime:{ir_name}"
                    graph.add_node(
                        GraphNode(
                            id=ir_node_id,
                            name=ir_name,
                            type=NodeType.INTEGRATION_RUNTIME,
                            description=f"Integration Runtime used by linked services",
                            properties={"type": "SelfHosted" if "self" in ir_name.lower() else "Managed"},
                        )
                    )
                # LinkedService -[USES_INTEGRATION_RUNTIME]-> IntegrationRuntime
                ls_node_id = f"linked_service:{ls.name}"
                ir_node_id = f"integration_runtime:{ir_name}"
                graph.add_edge(ls_node_id, ir_node_id, EdgeType.USES_INTEGRATION_RUNTIME)

        # 2. Add Dataset Nodes & Edges to Linked Services (Dataset -[USES]-> LinkedService)
        for ds in factory_meta.datasets:
            ds_node_id = f"dataset:{ds.name}"
            graph.add_node(
                GraphNode(
                    id=ds_node_id,
                    name=ds.name,
                    type=NodeType.DATASET,
                    folder=ds.folder,
                    description=ds.description,
                    properties={
                        "type": ds.type,
                        "linked_service_name": ds.linked_service_name,
                        "schema_fields": [f.model_dump() if hasattr(f, "model_dump") else f for f in ds.schema_fields],
                        "parameters": ds.parameters,
                    },
                    annotations=getattr(ds, "annotations", []) or [],
                )
            )

            # Link Dataset -> LinkedService
            if ds.linked_service_name:
                ls_node_id = f"linked_service:{ds.linked_service_name}"
                # Ensure LinkedService placeholder if external/referenced
                if ls_node_id not in graph.nodes:
                    graph.add_node(
                        GraphNode(
                            id=ls_node_id,
                            name=ds.linked_service_name,
                            type=NodeType.LINKED_SERVICE,
                            description="Referenced Linked Service",
                        )
                    )
                graph.add_edge(ds_node_id, ls_node_id, EdgeType.USES)

        # 3. Add Pipeline Nodes, Activity Nodes, and Intra-Pipeline Dependencies
        for pipe in factory_meta.pipelines:
            pipe_node_id = f"pipeline:{pipe.name}"
            graph.add_node(
                GraphNode(
                    id=pipe_node_id,
                    name=pipe.name,
                    type=NodeType.PIPELINE,
                    folder=pipe.folder,
                    description=pipe.description,
                    properties={
                        "parameters": pipe.parameters,
                        "variables": pipe.variables,
                        "activity_count": len(pipe.activities),
                    },
                    annotations=pipe.annotations,
                )
            )

            # Add activities and edges
            for act in pipe.activities:
                act_node_id = f"activity:{pipe.name}.{act.name}"
                graph.add_node(
                    GraphNode(
                        id=act_node_id,
                        name=act.name,
                        type=NodeType.ACTIVITY,
                        description=act.description,
                        properties={
                            "pipeline_name": pipe.name,
                            "type": act.type,
                            "retry_policy": act.retry_policy.model_dump(),
                            "timeout": act.timeout,
                            "called_pipeline": act.called_pipeline,
                            "linked_service": act.linked_service,
                            "type_properties": act.type_properties,
                        },
                    )
                )

                # Pipeline -[CONTAINS]-> Activity
                graph.add_edge(pipe_node_id, act_node_id, EdgeType.CONTAINS)

                # Activity -[DEPENDS_ON]-> Preceding Activity
                for dep_name in act.depends_on:
                    dep_node_id = f"activity:{pipe.name}.{dep_name}"
                    graph.add_edge(act_node_id, dep_node_id, EdgeType.DEPENDS_ON)

                # Activity -[CALLS]-> Child Pipeline (ExecutePipeline)
                if act.called_pipeline:
                    child_pipe_id = f"pipeline:{act.called_pipeline}"
                    if child_pipe_id not in graph.nodes:
                        graph.add_node(
                            GraphNode(
                                id=child_pipe_id,
                                name=act.called_pipeline,
                                type=NodeType.PIPELINE,
                                description="Dynamically referenced child pipeline",
                            )
                        )
                    graph.add_edge(act_node_id, child_pipe_id, EdgeType.CALLS)
                    # Also link parent pipeline -> child pipeline for high-level graph
                    graph.add_edge(pipe_node_id, child_pipe_id, EdgeType.CALLS)

                # Activity -[READS]-> Input Datasets
                for in_ds in act.inputs:
                    in_ds_id = f"dataset:{in_ds}"
                    if in_ds_id not in graph.nodes:
                        graph.add_node(
                            GraphNode(
                                id=in_ds_id,
                                name=in_ds,
                                type=NodeType.DATASET,
                                description="Referenced input dataset",
                            )
                        )
                    graph.add_edge(act_node_id, in_ds_id, EdgeType.READS)
                    graph.add_edge(pipe_node_id, in_ds_id, EdgeType.READS)

                # Activity -[WRITES]-> Output Datasets
                for out_ds in act.outputs:
                    out_ds_id = f"dataset:{out_ds}"
                    if out_ds_id not in graph.nodes:
                        graph.add_node(
                            GraphNode(
                                id=out_ds_id,
                                name=out_ds,
                                type=NodeType.DATASET,
                                description="Referenced output dataset",
                            )
                        )
                    graph.add_edge(act_node_id, out_ds_id, EdgeType.WRITES)
                    graph.add_edge(pipe_node_id, out_ds_id, EdgeType.WRITES)

                # Activity -[USES]-> LinkedService (e.g. WebActivity, AzureFunction, Databricks)
                if act.linked_service:
                    ls_node_id = f"linked_service:{act.linked_service}"
                    if ls_node_id not in graph.nodes:
                        graph.add_node(
                            GraphNode(
                                id=ls_node_id,
                                name=act.linked_service,
                                type=NodeType.LINKED_SERVICE,
                                description="Referenced compute linked service",
                            )
                        )
                    graph.add_edge(act_node_id, ls_node_id, EdgeType.USES)

                # ForEach / IfCondition / Until / Switch: build ITERATES_OVER / CONDITION_DEPENDS_ON edges
                act_type_lower = act.type.lower() if act.type else ""
                if act_type_lower in ("foreach", "ifcondition", "until", "switch"):
                    inner_activities = _extract_inner_activities(act.type_properties)
                    for inner_act in inner_activities:
                        inner_name = inner_act.get("name", "unknown")
                        inner_act_type = inner_act.get("type", "Unknown")
                        inner_node_id = f"activity:{pipe.name}.{inner_name}"

                        # Create node for inner activity if not already present
                        if inner_node_id not in graph.nodes:
                            graph.add_node(
                                GraphNode(
                                    id=inner_node_id,
                                    name=inner_name,
                                    type=NodeType.ACTIVITY,
                                    description=f"Inner activity of {act.type}: {act.name}",
                                    properties={
                                        "pipeline_name": pipe.name,
                                        "type": inner_act_type,
                                        "parent_activity": act.name,
                                    },
                                )
                            )

                        # Create appropriate edge type
                        if act_type_lower in ("foreach", "until"):
                            graph.add_edge(act_node_id, inner_node_id, EdgeType.ITERATES_OVER, {
                                "parent_type": act.type,
                            })
                        elif act_type_lower == "ifcondition":
                            graph.add_edge(act_node_id, inner_node_id, EdgeType.CONDITION_DEPENDS_ON, {
                                "parent_type": act.type,
                            })
                        elif act_type_lower == "switch":
                            graph.add_edge(act_node_id, inner_node_id, EdgeType.CONDITION_DEPENDS_ON, {
                                "parent_type": act.type,
                            })

        # 4. Add Triggers & Edges (Trigger -[EXECUTES]-> Pipeline)
        for tr in factory_meta.triggers:
            tr_node_id = f"trigger:{tr.name}"
            graph.add_node(
                GraphNode(
                    id=tr_node_id,
                    name=tr.name,
                    type=NodeType.TRIGGER,
                    description=tr.description,
                    properties={
                        "type": tr.type,
                        "runtime_state": tr.runtime_state,
                        "recurrence_schedule": tr.recurrence_schedule,
                        "pipelines": tr.pipelines,
                    },
                    annotations=getattr(tr, "annotations", []) or [],
                )
            )

            for target_pipe_name in tr.pipelines:
                target_pipe_id = f"pipeline:{target_pipe_name}"
                if target_pipe_id not in graph.nodes:
                    graph.add_node(
                        GraphNode(
                            id=target_pipe_id,
                            name=target_pipe_name,
                            type=NodeType.PIPELINE,
                            description="Triggered pipeline",
                        )
                    )
                # Trigger -[EXECUTES]-> Pipeline
                graph.add_edge(tr_node_id, target_pipe_id, EdgeType.EXECUTES)
                # Pipeline -[TRIGGERED_BY]-> Trigger
                graph.add_edge(target_pipe_id, tr_node_id, EdgeType.TRIGGERED_BY)

        # 5. Add Mapping Data Flows
        for df in factory_meta.data_flows:
            df_node_id = f"data_flow:{df.name}"
            graph.add_node(
                GraphNode(
                    id=df_node_id,
                    name=df.name,
                    type=NodeType.DATA_FLOW,
                    description=df.description,
                    properties={
                        "type": df.type,
                        "sources": df.sources,
                        "sinks": df.sinks,
                        "transformations": df.transformations,
                    },
                    annotations=getattr(df, "annotations", []) or [],
                )
            )

            for src in df.sources:
                ds_id = f"dataset:{src}"
                graph.add_edge(df_node_id, ds_id, EdgeType.READS)

            for snk in df.sinks:
                ds_id = f"dataset:{snk}"
                graph.add_edge(df_node_id, ds_id, EdgeType.WRITES)

        # 6. Expression-level Reference Edges (high-confidence data dependencies)
        expr_analyzer = ExpressionAnalyzer()
        expr_refs = expr_analyzer.analyze_factory(factory_meta)
        graph.expr_analyzer = expr_analyzer
        for ref in expr_refs:
            if ref.reference_type == "OUTPUT_REFERENCE":
                # Activity references another activity's output → REFERENCES_OUTPUT_OF
                src_id = f"activity:{ref.source_name}" if "." in ref.source_name else f"activity:{ref.target_name.rsplit('.', 1)[0]}.{ref.source_name}"
                tgt_id = f"activity:{ref.target_name}" if "." in ref.target_name else f"activity:{ref.target_name}"
                if src_id in graph.nodes and tgt_id in graph.nodes:
                    graph.add_edge(tgt_id, src_id, EdgeType.REFERENCES_OUTPUT_OF, {
                        "expression": ref.expression,
                        "confidence": ref.confidence.value,
                    })
            elif ref.reference_type == "DATASET_REFERENCE":
                # Activity references a dataset in expression → REFERENCES
                ds_id = f"dataset:{ref.source_name}"
                act_id = f"activity:{ref.target_name}" if "." in ref.target_name else None
                if ds_id in graph.nodes and act_id and act_id in graph.nodes:
                    graph.add_edge(act_id, ds_id, EdgeType.REFERENCES, {
                        "expression": ref.expression,
                        "confidence": ref.confidence.value,
                    })

        logger.info(
            f"[bold green][OK] Knowledge Graph Constructed:[/bold green] "
            f"[bold cyan]{len(graph.nodes)}[/bold cyan] vertices, [bold magenta]{len(graph.edges)}[/bold magenta] edges."
        )
        return graph


# Alias for clean modular access
GraphBuilder = KnowledgeGraphBuilder

