"""Multi-Intent Prompt Templates and Context Serialization for AI Reasoning."""

from enum import Enum
from typing import Any
from pie.graph.models import NodeType
from pie.graph.builder import KnowledgeGraph
from pie.graph.traversal import GraphTraversalService
from pie.graph.storyteller import PipelineStoryteller
from pie.graph.deletion_simulator import AssetDeletionSimulator
from pie.context.models import TokenBudget, ContextPackage
from pie.context.compressor import SchemaCompressor
from pie.context.budgeter import TokenBudgeter


class ContextIntent(str, Enum):
    """Target persona and cognitive intent for LLM prompt formatting."""
    ARCHITECTURE = "architecture"          # Executive summary, SaaS touchpoints, schedule
    DEBUGGING = "debugging"                # SQL queries, stored procedures, retries, secrets
    IMPACT_ANALYSIS = "impact_analysis"    # Blast radius, broken readers/writers, remediation
    MODERNIZATION = "modernization"        # Data flows, source-to-sink schemas, PySpark/dbt readiness


class MultiIntentContextBuilder:
    """Constructs persona-tailored, token-budgeted prompt packages for AI reasoning."""

    def __init__(self, graph: KnowledgeGraph):
        self.graph = graph
        self.traversal = GraphTraversalService(graph)
        self.storyteller = PipelineStoryteller(graph)
        self.deletion_simulator = AssetDeletionSimulator(graph)

    def build_intent_package(
        self,
        target_asset: str,
        intent: ContextIntent = ContextIntent.ARCHITECTURE,
        budget: TokenBudget | None = None,
    ) -> ContextPackage:
        """Generate tailored prompt payload matching the specific cognitive intent."""
        budget = budget or TokenBudget()
        resolved_id = self.traversal.resolve_node_id(target_asset)

        if not resolved_id:
            raise ValueError(f"Asset '{target_asset}' not found in Knowledge Graph.")

        target_node = self.graph.nodes[resolved_id]
        subgraph = self.traversal.extract_k_hop_subgraph(resolved_id, k=2)

        # Estimate uncompressed raw volume
        import json
        raw_tokens = TokenBudgeter.estimate_tokens(json.dumps([n.model_dump() for n in subgraph.nodes.values()], default=str))
        sections: list[str] = []
        sections.append(f"Context: `{target_node.name}` ({target_node.type.value}) Intent:{intent.value.upper()}")

        # 1. Architecture Intent — full pipeline walkthrough for business narrative
        if intent == ContextIntent.ARCHITECTURE:
            story = self.storyteller.explain_pipeline(target_node.name) if target_node.type == NodeType.PIPELINE else {}
            sections.append(f"### Executive Architectural Overview\nArch: {story.get('executive_summary', target_node.description or 'Asset')}")
            sections.append(f"KV: {len(story.get('auth_and_secrets', []))} secrets")
            sections.append(f"ChildPipes: {','.join(story.get('child_pipelines', [])) or 'None'}")
            sections.append(f"SaaS: {','.join(story.get('api_endpoints', [])) or 'Internal'}")

            # Full activity execution sequence for step-by-step business narration
            execution_steps = story.get("execution_steps", [])
            if execution_steps:
                step_lines = []
                for step in execution_steps:
                    step_lines.append(
                        f"S{step['step_number']}: {step['activity_name']} [{step['type']}]"
                        + (f" - {step['description']}" if step.get('description') else "")
                        + (f" -> calls pipeline: {step['called_pipeline']}" if step.get('called_pipeline') else "")
                    )
                sections.append("### Activity Execution Sequence (IN ORDER)\n" + "\n".join(step_lines))

            # Data movements (Copy source → sink)
            data_movements = story.get("data_movements", [])
            if data_movements:
                sections.append("### Data Movements\n" + "\n".join(f"- {dm}" for dm in data_movements))

            # SQL operations
            sql_operations = story.get("sql_operations", [])
            if sql_operations:
                sections.append("### SQL / Stored Procedure Operations\n" + "\n".join(f"- {op}" for op in sql_operations))

            # Data flows
            data_flows = story.get("data_flows", [])
            if data_flows:
                sections.append("### Data Flows\n" + "\n".join(f"- {df}" for df in data_flows))

        # 2. Debugging & Troubleshooting Intent
        elif intent == ContextIntent.DEBUGGING:
            if target_node.type == NodeType.PIPELINE:
                story = self.storyteller.explain_pipeline(target_node.name)
                act_lines = []
                for step in story.get("execution_steps", []):
                    act_lines.append(
                        f"S{step['step_number']}:{step['activity_name']}[{step['type']}] "
                        f"Retry:{step.get('retry_policy', {}).get('count', 0)}x Called:{step.get('called_pipeline') or '-'}"
                    )
                sections.append("### Technical Debugging & Execution Specification\n" + TokenBudgeter.fit_lines_to_budget(act_lines, max_tokens=int(budget.max_tokens * 0.6), section_name="activities"))

        # 3. Impact & Deletion Analysis Intent
        elif intent == ContextIntent.IMPACT_ANALYSIS:
            sim = self.deletion_simulator.simulate_dataset_deletion(target_node.name) if target_node.type == NodeType.DATASET else {}
            impact = self.traversal.compute_impact_report(target_node.name)
            sections.append("### Systemic Change Risk & Blast Radius Assessment")
            sections.append(f"- Risk: `{impact.risk_level}` ({impact.risk_score}/100)")
            sections.append(f"- Blast Radius: {impact.total_downstream_impact_count}")
            sections.append(f"- Downstream: {','.join(impact.affected_pipelines[:5]) or 'None'}")
            if sim.get("found"):
                sections.append(f"- Broken: {sim['immediate_failures']['total_broken_activities']}")
                sections.append("Remediation:\n" + "\n".join([f"- {s}" for s in sim.get("remediation_plan", [])]))

        # 4. Modernization / Code Generation Intent
        elif intent == ContextIntent.MODERNIZATION:
            schema_lines = []
            for node in subgraph.nodes.values():
                if node.type == NodeType.DATASET:
                    schema_lines.append(SchemaCompressor.compress_dataset_node(node))
            sections.append("Schemas:\n" + TokenBudgeter.fit_lines_to_budget(schema_lines, max_tokens=int(budget.max_tokens * 0.5), section_name="schemas"))

        full_md = "\n\n".join(sections)
        compressed_tokens = TokenBudgeter.estimate_tokens(full_md)
        savings = max(0.0, round(((raw_tokens - compressed_tokens) / max(1, raw_tokens)) * 100.0, 1))

        return ContextPackage(
            target_asset_name=target_node.name,
            target_asset_type=target_node.type.value,
            token_budget=budget.max_tokens,
            raw_uncompressed_tokens=raw_tokens,
            compressed_context_tokens=compressed_tokens,
            compression_ratio=savings,
            executive_summary_md=sections[2] if len(sections) > 2 else "",
            activity_flow_md="",
            dataset_schemas_md="",
            lineage_and_blast_radius_md="",
            linked_services_md="",
            full_prompt_payload_md=full_md,
            metadata_summary={"intent": intent.value},
        )
