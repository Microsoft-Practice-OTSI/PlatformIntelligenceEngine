"""Detailed Pipeline Storyteller: Inspects minute activity-level parameters, REST endpoints,
SQL procedures, and data transformations to generate clear, structured pipeline walkthroughs.
"""

from typing import Any
from pie.graph.models import NodeType, EdgeType, GraphNode
from pie.graph.builder import KnowledgeGraph


class PipelineStoryteller:
    """Transforms raw activity topologies and parameter mappings into clear, plain-language operational summaries."""

    def __init__(self, graph: KnowledgeGraph):
        self.graph = graph

    def explain_pipeline(self, pipeline_name_or_id: str) -> dict[str, Any]:
        """Deeply inspect every activity, API call, Key Vault secret, Copy source/sink, and child pipeline."""
        # Find pipeline node
        pipe_node = None
        for node in self.graph.nodes.values():
            if node.type == NodeType.PIPELINE:
                if node.name.lower() == pipeline_name_or_id.lower() or node.id.lower() == pipeline_name_or_id.lower():
                    pipe_node = node
                    break

        if not pipe_node:
            return {
                "found": False,
                "error": f"Pipeline '{pipeline_name_or_id}' not found in Knowledge Graph.",
            }

        # Find all contained activities
        activities: list[GraphNode] = []
        for edge in self.graph.get_outgoing_edges(pipe_node.id, EdgeType.CONTAINS):
            act_node = self.graph.get_node(edge.target_id)
            if act_node and act_node.type == NodeType.ACTIVITY:
                activities.append(act_node)

        # Categorize activities and build execution flow
        stages: list[dict[str, Any]] = []
        key_vault_lookups: list[str] = []
        api_calls: list[str] = []
        data_movements: list[str] = []
        sql_operations: list[str] = []
        child_pipelines: list[str] = []
        data_flows: list[str] = []

        for idx, act in enumerate(activities, 1):
            act_type = act.properties.get("type", "Unknown")
            type_props = act.properties.get("type_properties", {}) or {}
            desc = act.description or ""

            # Check Key Vault & Credentials
            if "keyvault" in act.name.lower() or "akv" in act.name.lower() or "secret" in act.name.lower():
                key_vault_lookups.append(act.name)

            # Check Web / REST APIs
            if act_type in ["WebActivity", "RestResource", "WebHook"]:
                url = type_props.get("url") or desc
                api_calls.append(f"{act.name} ({act_type})")

            # Check Copy Data
            if act_type == "Copy":
                src = type_props.get("source", {}).get("type", "Source") if isinstance(type_props.get("source"), dict) else "Source"
                snk = type_props.get("sink", {}).get("type", "Sink") if isinstance(type_props.get("sink"), dict) else "Sink"
                data_movements.append(f"{act.name}: {src} -> {snk}")

            # Check SQL / Stored Procedures / Scripts
            if act_type in ["SqlServerStoredProcedure", "Script", "Lookup"]:
                proc = type_props.get("storedProcedureName") or type_props.get("sqlReaderQuery") or ""
                sql_operations.append(f"{act.name}" + (f" [{proc}]" if proc else ""))

            # Check Child Pipelines (ExecutePipeline)
            if act_type == "ExecutePipeline":
                called = act.properties.get("called_pipeline") or act.name
                child_pipelines.append(called)

            # Check Data Flows
            if act_type in ["ExecuteDataFlow", "DataFlow"]:
                data_flows.append(act.name)

            stages.append({
                "step_number": idx,
                "activity_name": act.name,
                "type": act_type,
                "description": desc,
                "called_pipeline": act.properties.get("called_pipeline"),
                "retry_policy": act.properties.get("retry_policy", {}),
            })

        # Synthesize High-Level Executive Summary
        summary_sentences = []
        summary_sentences.append(f"Pipeline '{pipe_node.name}' (Folder: '{pipe_node.folder or 'Root'}') coordinates a {len(activities)}-step workflow.")

        if key_vault_lookups or api_calls:
            summary_sentences.append(f"It securely authenticates via Azure Key Vault ({len(key_vault_lookups)} secrets) and interfaces with external REST APIs ({', '.join(api_calls[:3])}).")

        if data_movements or data_flows:
            summary_sentences.append(f"It performs data staging and transformation across storage accounts and databases ({len(data_movements)} copy operations, {len(data_flows)} mapping data flows).")

        if child_pipelines:
            summary_sentences.append(f"It triggers {len(child_pipelines)} child execution pipelines ({', '.join(child_pipelines[:3])}).")

        if sql_operations:
            summary_sentences.append(f"It runs {len(sql_operations)} database lookups and SQL procedure scripts.")

        return {
            "found": True,
            "pipeline_name": pipe_node.name,
            "folder": pipe_node.folder,
            "total_activities": len(activities),
            "executive_summary": " ".join(summary_sentences),
            "auth_and_secrets": key_vault_lookups,
            "api_endpoints": api_calls,
            "data_movements": data_movements,
            "data_flows": data_flows,
            "child_pipelines": child_pipelines,
            "sql_operations": sql_operations,
            "execution_steps": stages,
        }
