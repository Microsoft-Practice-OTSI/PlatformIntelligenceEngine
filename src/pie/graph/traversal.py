"""Deterministic Graph Traversal Engine: Lineage, Blast Radius, Subgraph Extraction, and Cycle Detection."""

from collections import deque
from typing import Any
from pie.core.logging import get_logger
from pie.graph.models import (
    NodeType,
    EdgeType,
    GraphNode,
    GraphEdge,
    Subgraph,
    ImpactReport,
)
from pie.graph.builder import KnowledgeGraph

logger = get_logger(__name__)


class GraphTraversalService:
    """Provides lineage tracing, blast-radius calculation, cycle detection, and subgraph extraction."""

    def __init__(self, graph: KnowledgeGraph):
        self.graph = graph

    def resolve_node_id(self, identifier: str) -> str | None:
        """Resolve a friendly name or qualified ID to a canonical graph node ID."""
        if identifier in self.graph.nodes:
            return identifier

        # Try prefix matching
        for prefix in ["pipeline:", "dataset:", "linked_service:", "trigger:", "activity:", "data_flow:"]:
            candidate = f"{prefix}{identifier}"
            if candidate in self.graph.nodes:
                return candidate

        # Try case-insensitive name match
        node = self.graph.get_node_by_name(identifier)
        if node:
            return node.id

        return None

    def get_upstream_lineage(self, start_id: str, max_hops: int = 6) -> list[dict[str, Any]]:
        """Trace upstream incoming dependencies (Sources, parent pipelines, input datasets, triggers)."""
        resolved_id = self.resolve_node_id(start_id)
        if not resolved_id:
            logger.warning(f"Node '{start_id}' not found in Knowledge Graph.")
            return []

        visited: set[str] = {resolved_id}
        queue: deque[tuple[str, int, list[str]]] = deque([(resolved_id, 0, [])])
        lineage: list[dict[str, Any]] = []

        while queue:
            curr_id, depth, path = queue.popleft()
            if depth >= max_hops:
                continue

            # Check incoming edges (who feeds or controls curr_id)
            for edge in self.graph.get_incoming_edges(curr_id):
                src_id = edge.source_id
                src_node = self.graph.get_node(src_id)
                current_path = path + [f"{src_id} -[{edge.type}]-> {curr_id}"]

                if src_id not in visited:
                    visited.add(src_id)
                    lineage.append(
                        {
                            "hop": depth + 1,
                            "node_id": src_id,
                            "name": src_node.name if src_node else src_id,
                            "type": src_node.type.value if src_node else "Unknown",
                            "relationship": edge.type.value,
                            "path": current_path,
                        }
                    )
                    queue.append((src_id, depth + 1, current_path))

        return lineage

    def get_downstream_impact(self, start_id: str, max_hops: int = 6) -> list[dict[str, Any]]:
        """Trace downstream outgoing dependencies (Blast radius: consumers, sinks, child pipelines, and dependent assets)."""
        resolved_id = self.resolve_node_id(start_id)
        if not resolved_id:
            logger.warning(f"Node '{start_id}' not found in Knowledge Graph.")
            return []

        visited: set[str] = {resolved_id}
        queue: deque[tuple[str, int, list[str]]] = deque([(resolved_id, 0, [])])
        impacts: list[dict[str, Any]] = []

        while queue:
            curr_id, depth, path = queue.popleft()
            if depth >= max_hops:
                continue

            # Check outgoing edges (who curr_id calls, writes to, or executes)
            for edge in self.graph.get_outgoing_edges(curr_id):
                tgt_id = edge.target_id
                tgt_node = self.graph.get_node(tgt_id)
                current_path = path + [f"{curr_id} -[{edge.type}]-> {tgt_id}"]

                if tgt_id not in visited:
                    visited.add(tgt_id)
                    impacts.append(
                        {
                            "hop": depth + 1,
                            "node_id": tgt_id,
                            "name": tgt_node.name if tgt_node else tgt_id,
                            "type": tgt_node.type.value if tgt_node else "Unknown",
                            "relationship": edge.type.value,
                            "path": current_path,
                        }
                    )
                    queue.append((tgt_id, depth + 1, current_path))

            # Also check incoming USES / READS edges (e.g. if a Linked Service or Dataset is modified, assets that use it are directly impacted)
            for edge in self.graph.get_incoming_edges(curr_id):
                if edge.type in [EdgeType.USES, EdgeType.READS, EdgeType.DEPENDS_ON]:
                    src_id = edge.source_id
                    src_node = self.graph.get_node(src_id)
                    current_path = path + [f"{src_id} depends on {curr_id}"]

                    if src_id not in visited:
                        visited.add(src_id)
                        impacts.append(
                            {
                                "hop": depth + 1,
                                "node_id": src_id,
                                "name": src_node.name if src_node else src_id,
                                "type": src_node.type.value if src_node else "Unknown",
                                "relationship": f"DEPENDS_ON_{edge.type.value}",
                                "path": current_path,
                            }
                        )
                        queue.append((src_id, depth + 1, current_path))

        return impacts

    def extract_k_hop_subgraph(self, start_id: str, k: int = 2) -> Subgraph:
        """Extract a localized bidirectional subgraph within k hops of start_id (for Context Builder)."""
        resolved_id = self.resolve_node_id(start_id)
        if not resolved_id or resolved_id not in self.graph.nodes:
            return Subgraph(root_node_id=start_id, max_hops=k)

        sub_nodes: dict[str, GraphNode] = {resolved_id: self.graph.nodes[resolved_id]}
        sub_edges: list[GraphEdge] = []
        visited: set[str] = {resolved_id}
        queue: deque[tuple[str, int]] = deque([(resolved_id, 0)])

        while queue:
            curr_id, depth = queue.popleft()
            if depth >= k:
                continue

            # Explore both incoming and outgoing edges for complete local context
            neighbor_edges = self.graph.get_outgoing_edges(curr_id) + self.graph.get_incoming_edges(curr_id)

            for edge in neighbor_edges:
                other_id = edge.target_id if edge.source_id == curr_id else edge.source_id
                if edge not in sub_edges:
                    sub_edges.append(edge)

                if other_id in self.graph.nodes and other_id not in visited:
                    visited.add(other_id)
                    sub_nodes[other_id] = self.graph.nodes[other_id]
                    queue.append((other_id, depth + 1))

        return Subgraph(root_node_id=resolved_id, max_hops=k, nodes=sub_nodes, edges=sub_edges)

    def detect_cycles(self) -> list[list[str]]:
        """Detect circular dependencies or recursion loops across the knowledge graph."""
        visited: set[str] = set()
        rec_stack: set[str] = set()
        cycles: list[list[str]] = []
        current_path: list[str] = []

        def dfs(node_id: str):
            visited.add(node_id)
            rec_stack.add(node_id)
            current_path.append(node_id)

            # Focus cycle detection on pipeline calling and dependency edges
            for edge in self.graph.get_outgoing_edges(node_id):
                if edge.type in [EdgeType.CALLS, EdgeType.DEPENDS_ON, EdgeType.WRITES]:
                    neighbor = edge.target_id
                    if neighbor not in visited:
                        dfs(neighbor)
                    elif neighbor in rec_stack:
                        # Cycle found
                        cycle_start_idx = current_path.index(neighbor)
                        cycle = current_path[cycle_start_idx:] + [neighbor]
                        cycles.append(cycle)

            rec_stack.remove(node_id)
            current_path.pop()

        for node_id in self.graph.nodes:
            if node_id not in visited:
                dfs(node_id)

        return cycles

    def compute_impact_report(self, target_identifier: str) -> ImpactReport:
        """Calculate complete blast radius and change risk for an asset."""
        resolved_id = self.resolve_node_id(target_identifier)
        if not resolved_id or resolved_id not in self.graph.nodes:
            return ImpactReport(
                target_asset_id=target_identifier,
                target_asset_name=target_identifier,
                target_asset_type=NodeType.PIPELINE,
                risk_level="UNKNOWN",
                risk_score=0,
            )

        target_node = self.graph.nodes[resolved_id]
        downstream = self.get_downstream_impact(resolved_id, max_hops=6)
        upstream = self.get_upstream_lineage(resolved_id, max_hops=6)

        directly_affected = [item["name"] for item in downstream if item["hop"] == 1]
        affected_pipelines = list({item["name"] for item in downstream if item["type"] == NodeType.PIPELINE.value})
        affected_datasets = list({item["name"] for item in downstream if item["type"] == NodeType.DATASET.value})
        affected_triggers = list({item["name"] for item in upstream if item["type"] == NodeType.TRIGGER.value})
        upstream_sources = list({item["name"] for item in upstream})

        # Deterministic Risk Scoring Formula:
        # LinkedServices & Shared Datasets carry higher systemic risk
        base_score = 10
        if target_node.type == NodeType.LINKED_SERVICE:
            base_score = 35
        elif target_node.type == NodeType.DATASET:
            base_score = 25
        elif target_node.type == NodeType.TRIGGER:
            base_score = 15

        pipe_weight = len(affected_pipelines) * 12
        ds_weight = len(affected_datasets) * 8
        total_weight = len(downstream) * 4
        risk_score = min(100, base_score + pipe_weight + ds_weight + total_weight)

        if risk_score >= 75:
            risk_level = "CRITICAL"
        elif risk_score >= 50:
            risk_level = "HIGH"
        elif risk_score >= 25:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"

        return ImpactReport(
            target_asset_id=resolved_id,
            target_asset_name=target_node.name,
            target_asset_type=target_node.type,
            directly_affected_assets=directly_affected,
            total_downstream_impact_count=len(downstream),
            affected_pipelines=affected_pipelines,
            affected_datasets=affected_datasets,
            affected_triggers=affected_triggers,
            upstream_dependencies=upstream_sources,
            risk_level=risk_level,
            risk_score=risk_score,
        )

    def get_upstream_dependencies(self, asset_name: str, max_hops: int = 6) -> list[str]:
        """Convenience helper returning names of upstream dependencies."""
        lineage = self.get_upstream_lineage(asset_name, max_hops=max_hops)
        return sorted(list({item["name"] for item in lineage}))

    def get_downstream_blast_radius(self, asset_name: str, max_hops: int = 6) -> list[str]:
        """Convenience helper returning names of downstream impacted assets."""
        impact = self.get_downstream_impact(asset_name, max_hops=max_hops)
        return sorted(list({item["name"] for item in impact}))

    def get_k_hop_subgraph(self, asset_name: str, k_hops: int = 2) -> Subgraph:
        """Convenience alias for extract_k_hop_subgraph."""
        return self.extract_k_hop_subgraph(asset_name, k=k_hops)

