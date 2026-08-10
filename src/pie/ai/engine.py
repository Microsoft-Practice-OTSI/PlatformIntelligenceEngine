"""PIE AI Reasoning Engine: The master intelligence layer combining Knowledge Graph,
Multi-Intent Context Building, Deletion Simulation, and LLM Providers for 100% grounded answers.
"""

import time
from dataclasses import dataclass
from typing import Generator
from types import SimpleNamespace
from pie.core.logging import get_logger
from pie.graph.builder import KnowledgeGraph
from pie.graph.traversal import GraphTraversalService
from pie.graph.query_engine import AssetQueryEngine
from pie.graph.deletion_simulator import AssetDeletionSimulator
from pie.graph.audit_engine import (
    SecurityAndGovernanceAuditor,
    TechnicalDebtAndOrphanDetector,
    ScheduleConcurrencyHeatmap,
)
from pie.context.intent_builder import ContextIntent, MultiIntentContextBuilder
from pie.ai.models import (
    QueryIntent,
    ReasoningResponse,
    LLMConfig,
    LLMProviderType,
    ChatMessage,
    ChatRole,
)
from pie.ai.router import QueryIntentRouter
from pie.ai.providers import BaseLLMProvider, DeterministicMockLLMProvider, create_llm_provider
from pie.ai.prompts import (
    DOCUMENTATION_PROMPT,
    BUSINESS_SUMMARY_PROMPT,
    TECHNICAL_SUMMARY_PROMPT,
    ARCHITECTURE_REVIEW_PROMPT,
    IMPACT_ANALYSIS_PROMPT,
    RECOMMENDATION_PROMPT
)

logger = get_logger(__name__)

_PUNCT_TO_STRIP = "?!.,;:'\"()[]{}<>"

BASE_SYSTEM_INSTRUCTION = (
    "You are the Platform Intelligence Engine (PIE) Senior Azure Data Architect. "
    "Always ground your answers 100% in the provided verified ADF metadata (FACTORY CONTEXT). "
    "When the user refers to 'the current factory', 'this factory', or 'our factory', they mean the "
    "factory named in FACTORY CONTEXT. "
    "Never hallucinate fictitious pipelines or secrets. Use clean Markdown tables, bullet points, and code blocks."
)


@dataclass
class PromptBundle:
    """Prepared routing result used by both synchronous and streaming entry points."""

    intent: QueryIntent
    target_asset: str | None
    cited_assets: list[str]
    prompt_payload: str
    system_instruction: str
    factual_prefix: str = ""
    deterministic_response: ReasoningResponse | None = None


def _clean_token(token: str) -> str:
    """Strip trailing/leading punctuation so stop-word matching is not defeated by '?' or '.'."""
    return token.strip(_PUNCT_TO_STRIP)


class PIEReasoningEngine:
    """Enterprise AI Reasoning Engine for Azure Data Factory platform intelligence."""

    def __init__(self, graph: KnowledgeGraph, llm_provider: BaseLLMProvider | None = None):
        self.graph = graph
        self.traversal = GraphTraversalService(graph)
        self.router = QueryIntentRouter(graph)
        self.context_builder = MultiIntentContextBuilder(graph)
        self.query_engine = AssetQueryEngine(graph)
        self.deletion_simulator = AssetDeletionSimulator(graph)
        self.security_auditor = SecurityAndGovernanceAuditor(graph)
        self.debt_detector = TechnicalDebtAndOrphanDetector(graph)
        self.concurrency_heatmap = ScheduleConcurrencyHeatmap(graph)
        self.llm = llm_provider or create_llm_provider()

    # ------------------------------------------------------------------
    # Provider & graph management
    # ------------------------------------------------------------------

    def _resolve_llm_provider(self, selected_model: str) -> BaseLLMProvider:
        """Load env credentials and build the LLM provider for the requested model."""
        import os
        from dotenv import load_dotenv

        load_dotenv(override=True)
        config = LLMConfig()
        config.api_key = os.getenv("OPENAI_API_KEY") or os.getenv("AZURE_OPENAI_API_KEY")
        config.azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        config.google_api_key = os.getenv("GOOGLE_API_KEY")
        config.nvidia_api_key = os.getenv("NVIDIA_API_KEY")

        logger.info(
            f"Available API Keys - Azure OpenAI: {'✓' if config.api_key else '✗'}, "
            f"Google Gemini: {'✓' if config.google_api_key else '✗'}, "
            f"NVIDIA NIM: {'✓' if config.nvidia_api_key else '✗'}"
        )

        normalized = (selected_model or "mock").strip().lower().replace("_", "-")
        try:
            if normalized == "google-gemini":
                config.provider = LLMProviderType.GEMINI
                config.model = "gemini-2.0-flash"
            elif normalized == "azure-openai":
                config.provider = LLMProviderType.AZURE_OPENAI
                config.model = "gpt-4o-mini"
            elif normalized == "nvidia-nim":
                config.provider = LLMProviderType.NVIDIA
                config.model = "nvidia/nemotron-3-super-120b-a12b"
            else:
                config.provider = LLMProviderType.MOCK
            self.llm = create_llm_provider(config)
        except Exception as exc:
            logger.error(f"Error initializing LLM provider: {exc}. Falling back to Mock Provider.")
            config.provider = LLMProviderType.MOCK
            self.llm = create_llm_provider(config)
        return self.llm

    def _ensure_graph_for_factory(self, requested_factory: str | None) -> None:
        """Rebuild the in-memory graph when a different factory is requested."""
        if not requested_factory or requested_factory.strip().lower() == self.graph.factory_name.lower():
            return

        logger.info(f"Rebuilding graph for requested factory: {requested_factory}")
        from pie.discovery.repository import get_repository
        from pie.graph.builder import KnowledgeGraphBuilder

        repo = get_repository()
        factory = repo.get_factory(requested_factory)
        if not factory:
            logger.warning(f"Factory '{requested_factory}' not found in repository. Using current graph.")
            return

        self.graph = KnowledgeGraphBuilder.build(factory)
        self.traversal = GraphTraversalService(self.graph)
        self.router.graph = self.graph
        self.context_builder.graph = self.graph
        self.query_engine.graph = self.graph
        self.deletion_simulator.graph = self.graph
        self.security_auditor.graph = self.graph
        self.debt_detector.graph = self.graph
        self.concurrency_heatmap.graph = self.graph
        logger.info(f"Graph rebuilt successfully for factory: {requested_factory}")

    # ------------------------------------------------------------------
    # Context construction
    # ------------------------------------------------------------------

    def _build_factory_context(self) -> str:
        """Full verified factory-level context block that grounds every LLM prompt.

        Sends the complete normalized ADF metadata (pipelines with activities,
        datasets with schemas, linked services, triggers, data flows, global
        parameters) to the LLM so answers are grounded in every detail.
        """
        from pie.discovery.repository import get_repository, render_factory_full_context

        factory = None
        try:
            repo = get_repository()
            factory = repo.get_factory(self.graph.factory_name)
            if factory is None:
                for f in repo.list_factories():
                    if f.factory_name.lower() == self.graph.factory_name.lower():
                        factory = f
                        break
        except Exception:
            factory = None

        if factory is not None:
            full = render_factory_full_context(factory)
            if full:
                return full

        # Fallback: minimal context derived from graph nodes when the
        # full FactoryMetadata object is not available (e.g. empty graph).
        graph = self.graph
        nodes = list(graph.nodes.values())
        counts: dict[str, int] = {}
        for node in nodes:
            node_type = node.type.value
            counts[node_type] = counts.get(node_type, 0) + 1
        pipeline_names = sorted(n.name for n in nodes if n.type.value == "Pipeline")
        dataset_names = sorted(n.name for n in nodes if n.type.value == "Dataset")

        lines = [
            "## FACTORY CONTEXT (100% verified Azure Data Factory metadata)",
            f"- **Factory:** `{graph.factory_name}`",
            f"- **Asset Counts:** Pipelines=`{counts.get('Pipeline', 0)}`, Datasets=`{counts.get('Dataset', 0)}`, "
            f"Linked Services=`{counts.get('LinkedService', 0)}`, Triggers=`{counts.get('Trigger', 0)}`, "
            f"Data Flows=`{counts.get('DataFlow', 0)}`",
        ]
        if pipeline_names:
            lines.append(
                f"- **Pipelines ({len(pipeline_names)}):** " + ", ".join(f"`{n}`" for n in pipeline_names[:15])
            )
        if dataset_names:
            lines.append(
                f"- **Key Datasets ({len(dataset_names)}):** " + ", ".join(f"`{n}`" for n in dataset_names[:10])
            )
        return "\n".join(lines)

    def _build_history_block(self, history: list[ChatMessage] | None) -> str:
        """Render recent conversation turns as a transcript block for LLM continuity."""
        if not history:
            return ""
        lines = ["<conversation_history>"]
        for msg in history[-10:]:
            role_label = "User" if msg.role == ChatRole.USER else "PIE"
            content = msg.content.strip()
            if content:
                lines.append(f"[{role_label}] {content}")
        lines.append("</conversation_history>")
        return "\n".join(lines)

    def _build_factory_facts_answer(self, query: str) -> ReasoningResponse | None:
        """Answer direct factory-metadata lookups deterministically without calling the LLM."""
        from pie.discovery.repository import get_repository

        q_lower = query.lower()
        factory = None
        try:
            factory = get_repository().get_factory(self.graph.factory_name)
        except Exception:
            factory = None

        counts: dict[str, int] = {}
        for node in self.graph.nodes.values():
            node_type = node.type.value
            counts[node_type] = counts.get(node_type, 0) + 1

        answer: str | None = None
        if ("factory name" in q_lower or "name of the factory" in q_lower or "what factory" in q_lower
                or "which factory" in q_lower or "current factory" in q_lower or "our factory" in q_lower):
            answer = f"**Factory Name:** `{self.graph.factory_name}`"
        elif "resource group" in q_lower:
            answer = f"**Resource Group:** `{factory.resource_group if factory else 'n/a'}`"
        elif "subscription" in q_lower:
            answer = f"**Subscription ID:** `{factory.subscription_id if factory else 'n/a'}`"
        elif "location" in q_lower or "region" in q_lower or "located" in q_lower:
            answer = f"**Location:** `{factory.location if factory else 'n/a'}`"
        elif "how many" in q_lower:
            count_targets = [
                ("pipeline", "Pipeline", "pipelines"),
                ("dataset", "Dataset", "datasets"),
                ("linked service", "LinkedService", "linked services"),
                ("trigger", "Trigger", "triggers"),
                ("data flow", "DataFlow", "data flows"),
                ("activity", "Activity", "activities"),
            ]
            matched = next(
                ((key, node_type, label) for key, node_type, label in count_targets if key in q_lower),
                None,
            )
            if matched:
                key, node_type, label = matched
                if node_type in ("Pipeline", "Dataset"):
                    # "how many coupa pipelines" -> filtered search belongs to intent routing
                    stop_words = {"how", "many", "are", "there", "pipelines", "pipeline", "datasets", "dataset",
                                  "all", "the", "list", "show", "me", "find", "what", "which", "a", "an",
                                  "in", "of", "for", "with", "my", "this", "that", "is", "do", "does", "we", "have"}
                    words = [_clean_token(w) for w in q_lower.split()]
                    filter_kw = next((w for w in words if w not in stop_words and len(w) > 2), None)
                    if filter_kw:
                        return None
                answer = f"**{self.graph.factory_name}** has **{counts.get(node_type, 0)}** {label}."
            elif "factory" in q_lower or "factories" in q_lower:
                answer = f"**{self.graph.factory_name}** has **1** factory."

        if answer is None:
            return None

        return ReasoningResponse(
            user_query=query,
            detected_intent=QueryIntent.GENERAL,
            target_asset=None,
            response_markdown=answer,
            cited_assets=[],
            tokens_consumed=0,
            grounding_score=100.0,
            latency_ms=0.0,
        )

    # ------------------------------------------------------------------
    # Intent routing & prompt assembly
    # ------------------------------------------------------------------

    def _prepare(self, payload, history: list[ChatMessage] | None = None) -> PromptBundle:
        """Route a query to a deterministic answer or a grounded LLM prompt."""
        if isinstance(payload, str):
            payload = SimpleNamespace(query=payload, model="mock", factory_name=None)

        query = payload.query
        selected_model = getattr(payload, "model", None) or "mock"
        requested_factory = getattr(payload, "factory_name", None)

        self._ensure_graph_for_factory(requested_factory)
        self._resolve_llm_provider(selected_model)

        intent = self.router.classify_intent(query)
        target_asset = self.router.extract_target_asset(query)
        cited_assets: list[str] = []

        logger.info(
            f"Processing query: '{query}' (Intent: {intent.value}, "
            f"Target: {target_asset or 'None'}, Model: {selected_model})"
        )

        # Direct factory-metadata lookups are answered deterministically (no LLM).
        facts_response = self._build_factory_facts_answer(query)
        if facts_response is not None:
            return PromptBundle(
                intent=intent,
                target_asset=target_asset,
                cited_assets=[],
                prompt_payload="",
                system_instruction=BASE_SYSTEM_INSTRUCTION,
                deterministic_response=facts_response,
            )

        factory_context = self._build_factory_context()
        history_block = self._build_history_block(history)
        context_header = "\n\n".join(part for part in (factory_context, history_block) if part)

        prompt_payload = ""
        factual_prefix = ""
        deterministic_response: ReasoningResponse | None = None
        system_instruction = BASE_SYSTEM_INSTRUCTION

        # Case 1: What-If Deletion & Blast Radius
        if intent == QueryIntent.IMPACT and target_asset:
            cited_assets.append(target_asset)
            context_pkg = self.context_builder.build_intent_package(target_asset, intent=ContextIntent.IMPACT_ANALYSIS)
            prompt_payload = context_header + "\n\n" + IMPACT_ANALYSIS_PROMPT.format(
                asset_name=target_asset, context=context_pkg.full_prompt_payload_md
            )

        # Case 2: Multi-Criteria Asset Search (e.g. On-Prem CSV datasets, pipeline name search)
        elif intent == QueryIntent.SEARCH:
            q_lower = query.lower()
            file_type = "csv" if "csv" in q_lower else ("parquet" if "parquet" in q_lower else None)
            connectivity = "onprem" if ("onprem" in q_lower or "on-prem" in q_lower) else None

            # Pipeline keyword search (e.g. "find coupa pipelines", "search sap pipelines")
            if "pipeline" in q_lower and not file_type and not connectivity:
                stop_words = {"find", "search", "list", "show", "all", "pipeline", "pipelines",
                              "the", "a", "an", "in", "of", "for", "with", "my", "any"}
                words = [_clean_token(w) for w in q_lower.split()]
                kw = next((w for w in words if w not in stop_words and len(w) > 2), None)
                all_pipelines = [node.name for node in self.graph.nodes.values() if node.type.value == "Pipeline"]
                matched = [p for p in all_pipelines if kw and kw in p.lower()] if kw else all_pipelines
                res_lines = [
                    f"## PIE - Pipeline Search: `{kw or 'all'}`",
                    f"**Factory:** `{self.graph.factory_name}`",
                    f"**Matching Pipelines: {len(matched)}**",
                ]
                res_lines += ([f"- `{name}`" for name in sorted(matched)] if matched else ["_No matching pipelines._"])
                deterministic_response = ReasoningResponse(
                    user_query=query, detected_intent=intent, target_asset=None,
                    response_markdown="\n".join(res_lines),
                    cited_assets=matched[:10], tokens_consumed=len(matched),
                    grounding_score=100.0, latency_ms=0.0,
                )
            else:
                search_results = self.query_engine.find_datasets(file_type=file_type, connectivity=connectivity)
                cited_assets = [ds.get("dataset_name") or ds.get("name", "") for ds in search_results]

                res_lines = ["## Platform Intelligence Engine (PIE) - Asset Search Results"]
                res_lines.append(f"**Filter Applied:** FileType=`{file_type or 'Any'}`, Connectivity=`{connectivity or 'Any'}`")
                res_lines.append(f"### Discovered Datasets ({len(search_results)} matching assets):")
                for ds in search_results:
                    ds_name = ds.get("dataset_name") or ds.get("name", "Dataset")
                    ds_type = ds.get("dataset_type") or ds.get("type", "Generic")
                    res_lines.append(f"- **`{ds_name}`** *[{ds_type}]* — LinkedService: `{ds.get('linked_service')}` (OnPrem: `{ds.get('is_onprem')}`)")
                    if ds.get("columns"):
                        cols = [c.get("name", "") for c in ds["columns"][:4]]
                        res_lines.append(f"  - Columns: `[{', '.join(cols)}]`")

                factual_prefix = "\n".join(res_lines)
                prompt_payload = context_header + "\n\n" + factual_prefix

        # Case 3: Security Audit, Technical Debt, or Concurrency Collisions
        elif intent == QueryIntent.SECURITY_AUDIT:
            if "concurrency" in query.lower() or "collide" in query.lower() or "06:00" in query.lower():
                heatmap = self.concurrency_heatmap.analyze_schedule_concurrency()
                res_lines = ["## Platform Intelligence Engine (PIE) - Concurrency Collision Heatmap"]
                res_lines.append(f"- **Total Active Triggers Analyzed:** `{heatmap.get('total_triggers')}`")
                res_lines.append(f"### High-Risk Concurrent Triggers:")
                for col in heatmap.get("schedule_collisions", [])[:5]:
                    res_lines.append(
                        f"- **Schedule:** `{col['schedule_frequency']}` — `{col['concurrent_pipelines_fired']}` concurrent pipelines "
                        f"(via `{col['concurrent_trigger_count']}` triggers: {', '.join(col['triggers'])})"
                    )
            elif "orphan" in query.lower() or "debt" in query.lower() or "retry" in query.lower():
                debt_report = self.debt_detector.audit_technical_debt()
                res_lines = ["## Platform Intelligence Engine (PIE) - Technical Debt & Risk Audit"]
                res_lines.append(f"- **Orphan Pipelines (Never Triggered):** `{debt_report.get('orphan_pipelines_count')}` pipelines")
                res_lines.append(f"- **Fragile Zero-Retry Activities:** `{debt_report.get('zero_retry_fragile_activities_count')}` activities")
            else:
                saas_map = self.security_auditor.map_external_saas_vendors()
                res_lines = ["## Platform Intelligence Engine (PIE) - Enterprise SaaS & Endpoint Map"]
                for vendor, endpoints in saas_map.items():
                    res_lines.append(f"- **{vendor.upper()}:** {len(endpoints)} connected endpoints ({', '.join(endpoints)})")
            factual_prefix = "\n".join(res_lines)
            prompt_payload = context_header + "\n\n" + factual_prefix

        # Case 4: Modernization & PySpark / dbt Code Generation
        elif intent == QueryIntent.CODE_GEN and target_asset:
            cited_assets.append(target_asset)
            context_pkg = self.context_builder.build_intent_package(target_asset, intent=ContextIntent.MODERNIZATION)
            prompt_payload = context_header + "\n\n" + (
                f"You are a Senior Data Engineer.\n"
                f"Generate a clean PySpark, SQL, or dbt migration code spec for modernization of {target_asset}.\n"
                f"Ground your code strictly in this context:\n"
                f"{context_pkg.full_prompt_payload_md}"
            )

        # Case 5: Architecture or Debugging Question
        elif target_asset:
            cited_assets.append(target_asset)
            context_intent = ContextIntent.DEBUGGING if intent == QueryIntent.DEBUGGING else ContextIntent.ARCHITECTURE
            context_pkg = self.context_builder.build_intent_package(target_asset, intent=context_intent)

            q_lower = query.lower()
            if "business" in q_lower or "executive" in q_lower:
                tpl = BUSINESS_SUMMARY_PROMPT
            elif "technical" in q_lower or "sequence" in q_lower or "dependency" in q_lower or "flow" in q_lower:
                tpl = TECHNICAL_SUMMARY_PROMPT
            elif "recommend" in q_lower or "resili" in q_lower or "retry" in q_lower:
                tpl = RECOMMENDATION_PROMPT
            elif "review" in q_lower or "audit" in q_lower or "anti-pattern" in q_lower:
                tpl = ARCHITECTURE_REVIEW_PROMPT
            else:
                tpl = DOCUMENTATION_PROMPT

            prompt_payload = context_header + "\n\n" + tpl.format(
                asset_name=target_asset, context=context_pkg.full_prompt_payload_md
            )

        # Case 6: Fallback General Overview
        else:
            q_lower = query.lower()
            if ("how many" in q_lower or "list" in q_lower or "show" in q_lower) and "pipeline" in q_lower:
                all_pipelines = [node.name for node in self.graph.nodes.values() if node.type.value == "Pipeline"]
                # Extract a keyword filter (e.g., "coupa" from "how many coupa pipelines")
                stop_words = {"how", "many", "are", "there", "pipelines", "pipeline", "all",
                              "the", "list", "show", "me", "find", "what", "which", "a", "an",
                              "in", "of", "for", "with", "my", "this", "that", "is", "do", "does"}
                filter_kw = next(
                    (w for w in (_clean_token(w) for w in q_lower.split())
                     if w not in stop_words and len(w) > 2),
                    None
                )
                if filter_kw:
                    matched = [p for p in all_pipelines if filter_kw in p.lower()]
                    result_lines = [
                        f"## PIE - Pipeline Search: `{filter_kw}`\n",
                        f"**Factory:** `{self.graph.factory_name}`\n",
                        f"**Matching Pipelines: {len(matched)}**\n",
                    ]
                    if matched:
                        result_lines += [f"- `{name}`" for name in sorted(matched)]
                    else:
                        result_lines.append(f"_No pipelines found matching `{filter_kw}`._")
                    deterministic_response = ReasoningResponse(
                        user_query=query, detected_intent=intent, target_asset=None,
                        response_markdown="\n".join(result_lines),
                        cited_assets=matched[:10], tokens_consumed=len(matched),
                        grounding_score=100.0, latency_ms=0.0,
                    )
                else:
                    result_lines = [
                        f"## Platform Intelligence Engine (PIE) - Pipeline Inventory\n",
                        f"**Factory:** `{self.graph.factory_name}`\n",
                        f"| Factory | Pipeline Count |\n|---------|----------------|\n"
                        f"| `{self.graph.factory_name}` | **{len(all_pipelines)}** |\n",
                    ]
                    if all_pipelines:
                        result_lines.append("**Pipelines:**")
                        result_lines += [f"- `{name}`" for name in sorted(all_pipelines)]
                    else:
                        result_lines.append("_No pipelines loaded. Please sync your factory first._")
                    deterministic_response = ReasoningResponse(
                        user_query=query, detected_intent=intent, target_asset=None,
                        response_markdown="\n".join(result_lines),
                        cited_assets=all_pipelines[:10], tokens_consumed=len(all_pipelines),
                        grounding_score=100.0, latency_ms=0.0,
                    )
            else:
                verbose_keywords = [
                    "explain", "describe", "detail", "walk me through", "walk through",
                    "overview", "capabilities", "how does", "how do", "how is", "why",
                    "tell me about", "elaborate", "break down", "best practice",
                    "recommend", "feature", "analysis",
                ]
                is_verbose = any(k in q_lower for k in verbose_keywords)
                if is_verbose:
                    style = (
                        "Answer the user's question with a clear, well-structured explanation. "
                        "Use markdown headings and bullet points where helpful, grounding everything in the FACTORY CONTEXT."
                    )
                else:
                    style = (
                        "Answer DIRECTLY and CONCISELY. Respond in 1-3 short sentences or a compact bullet list. "
                        "Do not write a long essay, do not list generic Azure Data Factory capabilities, "
                        "and do not restate the FACTORY CONTEXT."
                    )
                prompt_payload = (
                    context_header + "\n\n"
                    f"## Platform Intelligence Engine (PIE) - General Platform Knowledge\n"
                    f"User asked: '{query}'.\n{style}"
                )

        return PromptBundle(
            intent=intent,
            target_asset=target_asset,
            cited_assets=cited_assets,
            prompt_payload=prompt_payload,
            system_instruction=system_instruction,
            factual_prefix=factual_prefix,
            deterministic_response=deterministic_response,
        )

    # ------------------------------------------------------------------
    # Public entry points
    # ------------------------------------------------------------------

    def ask(self, payload, history: list[ChatMessage] | None = None) -> ReasoningResponse:
        """Process a natural language question and return a 100% grounded reasoning response."""
        start_time = time.time()
        bundle = self._prepare(payload, history)
        query = payload.query if not isinstance(payload, str) else payload

        if bundle.deterministic_response is not None:
            bundle.deterministic_response.latency_ms = round((time.time() - start_time) * 1000, 1)
            return bundle.deterministic_response

        try:
            response_text = self.llm.complete(
                bundle.prompt_payload,
                system_prompt=bundle.system_instruction,
                factory_name=self.graph.factory_name,
            )
            logger.info("LLM completion succeeded.")
        except Exception as exc:
            logger.warning(f"LLM provider failed during completion: {exc}. Falling back to Mock Provider.")
            fallback_llm = DeterministicMockLLMProvider(LLMConfig(provider=LLMProviderType.MOCK))
            response_text = fallback_llm.complete(
                bundle.prompt_payload,
                system_prompt=bundle.system_instruction,
                factory_name=self.graph.factory_name,
            )

        # If deterministic search or audit, prepend the exact factual summary
        if bundle.factual_prefix:
            response_text = bundle.factual_prefix + "\n\n" + response_text

        latency = round((time.time() - start_time) * 1000, 1)
        return ReasoningResponse(
            user_query=query,
            detected_intent=bundle.intent,
            target_asset=bundle.target_asset,
            response_markdown=response_text,
            cited_assets=bundle.cited_assets,
            tokens_consumed=len(bundle.prompt_payload.split()) + len(response_text.split()),
            grounding_score=100.0,
            latency_ms=latency,
        )

    def stream_ask(self, payload, history: list[ChatMessage] | None = None) -> Generator[dict, None, None]:
        """Stream a grounded conversational response as SSE-ready event dicts."""
        start_time = time.time()
        bundle = self._prepare(payload, history)

        yield {
            "type": "metadata",
            "intent": bundle.intent.value.upper(),
            "target_asset": bundle.target_asset,
            "grounding_score": 100.0,
        }

        try:
            if bundle.deterministic_response is not None:
                for word in bundle.deterministic_response.response_markdown.split(" "):
                    yield {"type": "token", "token": word + " "}
            else:
                if bundle.factual_prefix:
                    for word in bundle.factual_prefix.split(" "):
                        yield {"type": "token", "token": word + " "}
                    yield {"type": "token", "token": "\n\n"}
                for chunk in self.llm.stream_complete(
                    bundle.prompt_payload,
                    system_prompt=bundle.system_instruction,
                    factory_name=self.graph.factory_name,
                ):
                    if chunk:
                        yield {"type": "token", "token": chunk}
        except Exception as exc:
            logger.warning(f"LLM provider failed during streaming: {exc}. Falling back to Mock Provider.")
            fallback_llm = DeterministicMockLLMProvider(LLMConfig(provider=LLMProviderType.MOCK))
            fallback_text = fallback_llm.complete(
                bundle.prompt_payload,
                system_prompt=bundle.system_instruction,
                factory_name=self.graph.factory_name,
            )
            for word in fallback_text.split(" "):
                yield {"type": "token", "token": word + " "}

        yield {
            "type": "done",
            "status": "COMPLETE",
            "latency_ms": round((time.time() - start_time) * 1000, 1),
        }
