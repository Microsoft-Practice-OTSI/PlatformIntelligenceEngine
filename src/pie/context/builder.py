"""Context Builder Engine: Extracts localized subgraphs, applies schema compression,
enforces strict token budgeting, and formats rich markdown for LLM consumption.
"""

import json
from typing import Any
from pie.core.logging import get_logger
from pie.graph.models import NodeType, EdgeType, GraphNode
from pie.graph.builder import KnowledgeGraph
from pie.graph.traversal import GraphTraversalService
from pie.graph.storyteller import PipelineStoryteller
from pie.graph.deletion_simulator import AssetDeletionSimulator
from pie.context.models import TokenBudget, ContextPackage
from pie.context.compressor import SchemaCompressor
from pie.context.budgeter import TokenBudgeter

logger = get_logger(__name__)


class ContextBuilder:
    """Intelligently extracts and budgets localized subgraphs into dense, LLM-ready context packages."""

    def __init__(self, graph: KnowledgeGraph):
        self.graph = graph
        self.traversal = GraphTraversalService(graph)
        self.storyteller = PipelineStoryteller(graph)
        self.deletion_simulator = AssetDeletionSimulator(graph)

    def build_context_package(
        self,
        target_asset_name: str,
        budget: TokenBudget | None = None,
        max_hops: int = 2,
    ) -> ContextPackage:
        """Construct a complete, token-budgeted, LLM-ready context package for any asset."""
        budget = budget or TokenBudget()
        resolved_id = self.traversal.resolve_node_id(target_asset_name)

        if not resolved_id or resolved_id not in self.graph.nodes:
            raise ValueError(f"Asset '{target_asset_name}' not found in Knowledge Graph.")

        target_node = self.graph.nodes[resolved_id]
        logger.info(f"Building LLM Context Package for [bold cyan]{target_node.name}[/bold cyan] ({target_node.type.value})...")

        # 1. Calculate Uncompressed Raw Volume (Simulating raw ADF JSON payload)
        subgraph = self.traversal.extract_k_hop_subgraph(resolved_id, k=max_hops)
        raw_json_str = json.dumps([n.model_dump() for n in subgraph.nodes.values()], default=str)
        raw_tokens = TokenBudgeter.estimate_tokens(raw_json_str)

        # 2. Executive Summary (15% of budget)
        exec_budget = int(budget.max_tokens * 0.15)
        story = self.storyteller.explain_pipeline(target_node.name) if target_node.type == NodeType.PIPELINE else {}
        if story.get("found"):
            exec_summary_text = (
                f"### Executive Summary\n"
                f"Summary: `{target_node.name}` ({target_node.folder or 'Root'})\n"
                f"Arch: {story.get('executive_summary', '')}\n"
                f"Secrets: {len(story.get('auth_and_secrets', []))} KV credentials\n"
                f"ChildPipes: {','.join(story.get('child_pipelines', [])) if story.get('child_pipelines') else 'None'}"
            )
        else:
            exec_summary_text = (
                f"### Executive Summary\n"
                f"Summary: `{target_node.name}` ({target_node.type.value})\n"
                f"Folder: `{target_node.folder or 'Root'}`\n"
                f"Desc: {target_node.description or 'ADF Asset'}"
            )

        # 3. Activity Execution Sequence (40% of budget)
        flow_budget = int(budget.max_tokens * budget.flow_allocation_pct)
        activity_lines: list[str] = []
        if target_node.type == NodeType.PIPELINE:
            step_idx = 1
            for edge in self.graph.get_outgoing_edges(target_node.id, EdgeType.CONTAINS):
                act_node = self.graph.get_node(edge.target_id)
                if act_node:
                    activity_lines.append(SchemaCompressor.compress_activity_node(act_node, step_num=step_idx))
                    step_idx += 1

        activity_flow_md = "### Minute Activity Execution Sequence\n" + TokenBudgeter.fit_lines_to_budget(
            activity_lines, max_tokens=flow_budget, section_name="activity"
        )

        # 4. Datasets & Schemas (25% of budget)
        schema_budget = int(budget.max_tokens * budget.schema_allocation_pct)
        dataset_lines: list[str] = []
        relevant_datasets: set[str] = set()

        # Find datasets directly connected to this asset or contained activities
        for edge in self.graph.get_outgoing_edges(target_node.id):
            if edge.type in [EdgeType.READS, EdgeType.WRITES]:
                relevant_datasets.add(edge.target_id)

        for edge in self.graph.get_incoming_edges(target_node.id):
            if edge.type in [EdgeType.READS, EdgeType.WRITES]:
                relevant_datasets.add(edge.source_id)

        # If target itself is a dataset, add it
        if target_node.type == NodeType.DATASET:
            relevant_datasets.add(target_node.id)

        for ds_id in sorted(list(relevant_datasets)):
            ds_node = self.graph.get_node(ds_id)
            if ds_node and ds_node.type == NodeType.DATASET:
                dataset_lines.append(SchemaCompressor.compress_dataset_node(ds_node))

        dataset_schemas_md = "### Input / Output Datasets & Schemas\n" + TokenBudgeter.fit_lines_to_budget(
            dataset_lines, max_tokens=schema_budget, section_name="dataset"
        )

        # 5. Lineage, Upstream Sources & Downstream Blast Radius (15% of budget)
        lineage_budget = int(budget.max_tokens * budget.lineage_allocation_pct)
        upstream = self.traversal.get_upstream_lineage(resolved_id, max_hops=3)
        downstream = self.traversal.get_downstream_impact(resolved_id, max_hops=3)
        impact_report = self.traversal.compute_impact_report(target_node.name)

        lineage_lines: list[str] = []
        lineage_lines.append(f"- Risk: `{impact_report.risk_level}` ({impact_report.risk_score}/100)")
        lineage_lines.append(f"- Blast Radius: `{impact_report.total_downstream_impact_count}` entities")
        if impact_report.affected_pipelines:
            lineage_lines.append(f"- Downstream: {','.join([f'`{p}`' for p in impact_report.affected_pipelines[:5]])}")
        if upstream:
            src_names = [f"`{u['name']}` ({u['type']})" for u in upstream[:4]]
            lineage_lines.append(f"- Upstream: {','.join(src_names)}")

        lineage_md = "Lineage:\n" + TokenBudgeter.fit_lines_to_budget(
            lineage_lines, max_tokens=lineage_budget, section_name="lineage"
        )

        # 6. Linked Services & Compute Endpoints (5% of budget)
        service_budget = int(budget.max_tokens * budget.service_allocation_pct)
        service_lines: list[str] = []
        for node in subgraph.nodes.values():
            if node.type == NodeType.LINKED_SERVICE:
                service_lines.append(SchemaCompressor.compress_linked_service_node(node))

        linked_services_md = "Services:\n" + TokenBudgeter.fit_lines_to_budget(
            service_lines, max_tokens=service_budget, section_name="service"
        )

        # 7. Assemble Full Prompt Payload
        full_md_sections = [
            f"Context: `{target_node.name}` ({target_node.type.value})",
            exec_summary_text,
            activity_flow_md,
            dataset_schemas_md,
            lineage_md,
            linked_services_md,
        ]
        # Filter empty sections
        full_md_sections = [s for s in full_md_sections if s.strip()]
        full_prompt_payload_md = "\n".join(full_md_sections)

        # 8. Compute Compression & Token Metrics
        compressed_tokens = TokenBudgeter.estimate_tokens(full_prompt_payload_md)
        savings_ratio = max(0.0, round(((raw_tokens - compressed_tokens) / max(1, raw_tokens)) * 100.0, 1))

        return ContextPackage(
            target_asset_name=target_node.name,
            target_asset_type=target_node.type.value,
            token_budget=budget.max_tokens,
            raw_uncompressed_tokens=raw_tokens,
            compressed_context_tokens=compressed_tokens,
            compression_ratio=savings_ratio,
            executive_summary_md=exec_summary_text,
            activity_flow_md=activity_flow_md,
            dataset_schemas_md=dataset_schemas_md,
            lineage_and_blast_radius_md=lineage_md,
            linked_services_md=linked_services_md,
            full_prompt_payload_md=full_prompt_payload_md,
            metadata_summary={
                "subgraph_nodes": len(subgraph.nodes),
                "subgraph_edges": len(subgraph.edges),
                "risk_score": impact_report.risk_score,
                "risk_level": impact_report.risk_level,
            },
        )
