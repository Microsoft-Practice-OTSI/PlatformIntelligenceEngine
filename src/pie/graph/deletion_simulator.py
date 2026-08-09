"""Asset Deletion Simulator: Deterministically computes the exact breakage, cascade failures,
impacted activities, and remediation steps if a dataset, pipeline, or linked service is deleted.
"""

from typing import Any
from pie.graph.models import NodeType, EdgeType, GraphNode
from pie.graph.builder import KnowledgeGraph
from pie.graph.traversal import GraphTraversalService


class AssetDeletionSimulator:
    """Simulates what happens if any asset is modified, renamed, or deleted."""

    def __init__(self, graph: KnowledgeGraph):
        self.graph = graph
        self.traversal = GraphTraversalService(graph)

    def simulate_dataset_deletion(self, dataset_name: str) -> dict[str, Any]:
        """Simulate deleting a dataset: answers 'What if I delete this dataset?'"""
        resolved_id = self.traversal.resolve_node_id(dataset_name)
        if not resolved_id:
            return {
                "found": False,
                "error": f"Dataset '{dataset_name}' not found in Knowledge Graph.",
            }

        target_node = self.graph.nodes[resolved_id]
        if target_node.type != NodeType.DATASET:
            return {
                "found": False,
                "error": f"Node '{dataset_name}' is of type {target_node.type.value}, not a Dataset.",
            }

        # 1. Direct Broken Activities (Activities that Read from or Write to this dataset)
        broken_read_activities: list[dict[str, str]] = []
        broken_write_activities: list[dict[str, str]] = []
        broken_data_flows: list[str] = []
        impacted_pipelines: set[str] = set()

        for edge in self.graph.get_incoming_edges(resolved_id):
            src_node = self.graph.get_node(edge.source_id)
            if not src_node:
                continue

            if src_node.type == NodeType.ACTIVITY:
                pipe_name = src_node.properties.get("pipeline_name", "Unknown")
                impacted_pipelines.add(pipe_name)

                if edge.type == EdgeType.READS:
                    broken_read_activities.append({
                        "pipeline": pipe_name,
                        "activity": src_node.name,
                        "role": "SOURCE_INPUT",
                        "impact": "Activity will fail immediately (Source dataset not found)",
                    })
                elif edge.type == EdgeType.WRITES:
                    broken_write_activities.append({
                        "pipeline": pipe_name,
                        "activity": src_node.name,
                        "role": "SINK_DESTINATION",
                        "impact": "Activity will fail during data write (Sink dataset missing)",
                    })

            elif src_node.type == NodeType.DATA_FLOW:
                broken_data_flows.append(src_node.name)

        # 2. Downstream Blast Radius
        downstream_impact = self.traversal.get_downstream_impact(resolved_id, max_hops=5)
        impact_report = self.traversal.compute_impact_report(dataset_name)

        # 3. Generate Step-by-Step Remediation Plan
        remediation_steps: list[str] = []
        remediation_steps.append(
            f"1. Refactor {len(broken_read_activities)} source activities reading from '{target_node.name}' across pipelines: {', '.join(sorted(list(impacted_pipelines))[:3])}."
        )
        if broken_write_activities:
            remediation_steps.append(
                f"2. Update {len(broken_write_activities)} sink activities that output data into '{target_node.name}'."
            )
        if broken_data_flows:
            remediation_steps.append(
                f"3. Reconfigure Mapping Data Flows referencing this dataset schema ({', '.join(broken_data_flows[:2])})."
            )
        remediation_steps.append(
            f"4. Verify that downstream datasets ({len(impact_report.affected_datasets)}) receive alternate feeder pipelines."
        )

        return {
            "found": True,
            "target_dataset": target_node.name,
            "linked_service": target_node.properties.get("linked_service_name"),
            "folder": target_node.folder or "Root",
            "risk_assessment": {
                "risk_level": impact_report.risk_level,
                "risk_score": impact_report.risk_score,
                "total_affected_entities": impact_report.total_downstream_impact_count,
            },
            "immediate_failures": {
                "total_broken_activities": len(broken_read_activities) + len(broken_write_activities),
                "broken_readers": broken_read_activities,
                "broken_writers": broken_write_activities,
                "broken_data_flows": broken_data_flows,
                "impacted_pipelines": sorted(list(impacted_pipelines)),
            },
            "remediation_plan": remediation_steps,
        }

    def simulate_linked_service_deletion(self, linked_service_name: str) -> dict[str, Any]:
        """Simulate deleting a linked service: answers 'What if I delete this linked service?'"""
        resolved_id = self.traversal.resolve_node_id(linked_service_name)
        if not resolved_id:
            return {
                "found": False,
                "error": f"Linked Service '{linked_service_name}' not found in Knowledge Graph.",
            }

        target_node = self.graph.nodes[resolved_id]
        broken_datasets: list[str] = []
        broken_activities: list[str] = []
        impacted_pipelines: set[str] = set()

        for edge in self.graph.get_incoming_edges(resolved_id):
            src_node = self.graph.get_node(edge.source_id)
            if not src_node:
                continue

            if src_node.type == NodeType.DATASET:
                broken_datasets.append(src_node.name)
            elif src_node.type == NodeType.ACTIVITY:
                pipe_name = src_node.properties.get("pipeline_name", "Unknown")
                broken_activities.append(f"{pipe_name}.{src_node.name}")
                impacted_pipelines.add(pipe_name)

        impact_report = self.traversal.compute_impact_report(linked_service_name)

        return {
            "found": True,
            "target_linked_service": target_node.name,
            "type": target_node.properties.get("type"),
            "risk_assessment": {
                "risk_level": impact_report.risk_level,
                "risk_score": impact_report.risk_score,
                "total_affected_entities": impact_report.total_downstream_impact_count,
            },
            "immediate_failures": {
                "broken_datasets": sorted(broken_datasets),
                "broken_direct_activities": broken_activities,
                "impacted_pipelines": sorted(list(impacted_pipelines)),
            },
            "remediation_plan": [
                f"1. Replace connection endpoint for {len(broken_datasets)} dependent datasets.",
                f"2. Re-point compute/storage credentials in pipelines: {', '.join(sorted(list(impacted_pipelines))[:3])}.",
            ],
        }
