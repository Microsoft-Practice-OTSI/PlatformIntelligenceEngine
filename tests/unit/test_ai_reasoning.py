"""Unit tests for PIE AI Reasoning Engine, Intent Classification, and Conversational Chat."""

import json
import pytest
from pie.discovery.models import (
    FactoryMetadata,
    PipelineMetadata,
    ActivityMetadata,
    DatasetMetadata,
    LinkedServiceMetadata,
    TriggerMetadata,
)
from pie.graph.builder import KnowledgeGraphBuilder
from pie.ai.models import QueryIntent, ReasoningResponse, LLMConfig, LLMProviderType
from pie.ai.router import QueryIntentRouter
from pie.ai.engine import PIEReasoningEngine
from pie.ai.providers import BaseLLMProvider


class _StubLLMProvider(BaseLLMProvider):
    """Test double that replays scripted `complete` responses in order."""

    def __init__(self, responses):
        self.responses = list(responses)
        super().__init__(LLMConfig(provider=LLMProviderType.MOCK))

    def complete(self, prompt, system_prompt="", factory_name=None):
        return self.responses.pop(0)

    def stream_complete(self, prompt, system_prompt="", factory_name=None):
        yield self.responses.pop(0)


@pytest.fixture
def ai_test_factory() -> FactoryMetadata:
    """Fixture providing a rich data factory for AI reasoning tests."""
    return FactoryMetadata(
        factory_name="adf-ai-test-factory",
        resource_group="rg-ai-test",
        subscription_id="sub-ai-123",
        location="centralus",
        pipelines=[
            PipelineMetadata(
                name="PL_Customer_Ingestion",
                id="/subscriptions/sub-ai-123/resourceGroups/rg-ai-test/providers/Microsoft.DataFactory/factories/adf-ai-test-factory/pipelines/PL_Customer_Ingestion",
                folder="Sales",
                activities=[
                    ActivityMetadata(
                        name="Copy_Csv_To_Sql",
                        type="Copy",
                        inputs=["DS_OnPrem_Customer_Csv"],
                        outputs=["DS_Cloud_Customer_Table"],
                    )
                ],
            )
        ],
        datasets=[
            DatasetMetadata(
                name="DS_OnPrem_Customer_Csv",
                id="/subscriptions/sub-ai-123/resourceGroups/rg-ai-test/providers/Microsoft.DataFactory/factories/adf-ai-test-factory/datasets/DS_OnPrem_Customer_Csv",
                type="DelimitedText",
                linked_service_name="LS_OnPrem_FileStore",
                schema_fields=[{"name": "CustomerID", "type": "string"}],
            ),
            DatasetMetadata(
                name="DS_Cloud_Customer_Table",
                id="/subscriptions/sub-ai-123/resourceGroups/rg-ai-test/providers/Microsoft.DataFactory/factories/adf-ai-test-factory/datasets/DS_Cloud_Customer_Table",
                type="AzureSqlTable",
                linked_service_name="LS_AzureSql",
                schema_fields=[{"name": "CustomerID", "type": "string"}],
            ),
        ],
        linked_services=[
            LinkedServiceMetadata(
                name="LS_OnPrem_FileStore",
                id="/subscriptions/sub-ai-123/resourceGroups/rg-ai-test/providers/Microsoft.DataFactory/factories/adf-ai-test-factory/linkedservices/LS_OnPrem_FileStore",
                type="FileServer",
                connection_properties={"host": "\\\\fileshare\\etl"},
            ),
            LinkedServiceMetadata(
                name="LS_AzureSql",
                id="/subscriptions/sub-ai-123/resourceGroups/rg-ai-test/providers/Microsoft.DataFactory/factories/adf-ai-test-factory/linkedservices/LS_AzureSql",
                type="AzureSqlDatabase",
                connection_properties={"server": "sql.database.windows.net"},
            ),
        ],
        triggers=[
            TriggerMetadata(
                name="TR_Daily_Customer",
                id="/subscriptions/sub-ai-123/resourceGroups/rg-ai-test/providers/Microsoft.DataFactory/factories/adf-ai-test-factory/triggers/TR_Daily_Customer",
                type="ScheduleTrigger",
                runtime_state="Started",
                recurrence_schedule="Every 1 Day(s) at 06:00 AM",
                pipelines=["PL_Customer_Ingestion"],
            )
        ],
        data_flows=[],
    )


def test_query_intent_router(ai_test_factory):
    """Verify router accurately classifies user cognitive intents."""
    graph = KnowledgeGraphBuilder.build(ai_test_factory)
    router = QueryIntentRouter(graph)

    # Impact
    assert router.classify_intent("What happens if I delete dataset DS_OnPrem_Customer_Csv?") == QueryIntent.IMPACT
    # Code Gen
    assert router.classify_intent("Write a PySpark script for PL_Customer_Ingestion") == QueryIntent.CODE_GEN
    # Search
    assert router.classify_intent("Find onprem csv datasets") == QueryIntent.SEARCH
    # Security Audit
    assert router.classify_intent("Which pipelines collide at 06:00 AM concurrency window?") == QueryIntent.SECURITY_AUDIT
    # Architecture
    assert router.classify_intent("Explain how PL_Customer_Ingestion works") == QueryIntent.ARCHITECTURE

    # Target Asset Extraction
    assert router.extract_target_asset("Explain PL_Customer_Ingestion") == "PL_Customer_Ingestion"
    assert router.extract_target_asset("What if I remove DS_OnPrem_Customer_Csv?") == "DS_OnPrem_Customer_Csv"
    # Fuzzy partial-name extraction is allowed for single-asset intents...
    assert router.extract_target_asset("Explain Customer Daily Ingestion", allow_fuzzy=True) == "PL_Customer_Ingestion"
    # ...but disabled for list/count queries so they keep their deterministic listing.
    assert router.extract_target_asset("How many customer pipelines are there", allow_fuzzy=False) is None


def test_pie_reasoning_engine_end_to_end(ai_test_factory):
    """Verify PIEReasoningEngine handles queries across intents with 100% grounding."""
    graph = KnowledgeGraphBuilder.build(ai_test_factory)
    engine = PIEReasoningEngine(graph)

    # 1. Architecture Query
    resp_arch = engine.ask("Explain PL_Customer_Ingestion")
    assert isinstance(resp_arch, ReasoningResponse)
    assert resp_arch.detected_intent == QueryIntent.ARCHITECTURE
    assert resp_arch.target_asset == "PL_Customer_Ingestion"
    assert "PL_Customer_Ingestion" in resp_arch.response_markdown
    assert "does" in resp_arch.response_markdown

    # 2. Deletion Impact Query
    resp_impact = engine.ask("What if I delete DS_OnPrem_Customer_Csv?")
    assert resp_impact.detected_intent == QueryIntent.IMPACT
    assert "Systemic Change Risk" in resp_impact.response_markdown

    # 3. Code Generation Query
    resp_code = engine.ask("Write a PySpark script to modernize PL_Customer_Ingestion")
    assert resp_code.detected_intent == QueryIntent.CODE_GEN
    assert "```python" in resp_code.response_markdown
    assert "pyspark" in resp_code.response_markdown

    # 4. Search Query
    resp_search = engine.ask("Find all onprem csv datasets")
    assert resp_search.detected_intent == QueryIntent.SEARCH
    assert "DS_OnPrem_Customer_Csv" in resp_search.response_markdown


def test_how_many_pipelines_with_punctuation(ai_test_factory):
    """Trailing punctuation must not defeat stop-word filtering (regression: 'there?').

    'how many pipelines are there?' must be recognized as a plain count question and
    answered concisely instead of being treated as a keyword filter for 'there?' (which matched 0).
    """
    graph = KnowledgeGraphBuilder.build(ai_test_factory)
    engine = PIEReasoningEngine(graph)

    resp = engine.ask("how many pipelines are there?")
    assert resp.detected_intent == QueryIntent.GENERAL
    assert "has **1** pipelines." in resp.response_markdown
    assert "Matching Pipelines" not in resp.response_markdown
    assert "Pipeline Inventory" not in resp.response_markdown


def test_how_many_filter_pipelines_with_punctuation(ai_test_factory):
    """A real keyword filter should still be extracted despite trailing punctuation."""
    graph = KnowledgeGraphBuilder.build(ai_test_factory)
    engine = PIEReasoningEngine(graph)

    resp = engine.ask("how many coupa pipelines are there?")
    assert resp.detected_intent == QueryIntent.GENERAL
    assert "PIE - Pipeline Search" in resp.response_markdown
    assert "Matching Pipelines: 0" in resp.response_markdown

    resp2 = engine.ask("how many Customer pipelines are there?")
    assert "PIE - Pipeline Search" in resp2.response_markdown
    assert "Matching Pipelines: 1" in resp2.response_markdown
    assert "PL_Customer_Ingestion" in resp2.response_markdown


def _add_railcarrx_pipelines(factory: FactoryMetadata) -> FactoryMetadata:
    """Add the real-world RailCarRx pipeline family to the test factory."""
    base_id = "/subscriptions/sub-ai-123/resourceGroups/rg-ai-test/providers/Microsoft.DataFactory/factories/adf-ai-test-factory/pipelines"
    factory.pipelines.append(
        PipelineMetadata(
            name="RailCarRx_InvoiceLoad",
            id=f"{base_id}/RailCarRx_InvoiceLoad",
            folder="RailCarRx",
            activities=[ActivityMetadata(name="Copy_RailCarRx_Invoice", type="Copy")],
        )
    )
    factory.pipelines.append(
        PipelineMetadata(
            name="RailCarRx_Payments",
            id=f"{base_id}/RailCarRx_Payments",
            folder="RailCarRx",
            activities=[ActivityMetadata(name="Copy_RailCarRx_Payments", type="Copy")],
        )
    )
    return factory


def test_railcarrx_pipeline_discovery(ai_test_factory):
    """'What are the RailcarRx pipelines we have?' must list RailCarRx_* pipelines deterministically.

    Regression: previously classified as GENERAL with no target asset, so the LLM answered
    'no pipelines named RailcarRx' instead of listing the similar-sounding family.
    """
    factory = _add_railcarrx_pipelines(ai_test_factory)
    graph = KnowledgeGraphBuilder.build(factory)
    engine = PIEReasoningEngine(graph)

    resp = engine.ask("What are the RailcarRx pipelines we have?")
    assert resp.detected_intent == QueryIntent.SEARCH
    assert "PIE - Pipeline Search" in resp.response_markdown
    assert "Matching Pipelines: 2" in resp.response_markdown
    assert "RailCarRx_InvoiceLoad" in resp.response_markdown
    assert "RailCarRx_Payments" in resp.response_markdown
    assert "no pipelines named" not in resp.response_markdown


def test_fuzzy_similar_sounding_pipeline_fallback(ai_test_factory):
    """A misspelled pipeline keyword falls back to similar-sounding matches."""
    factory = _add_railcarrx_pipelines(ai_test_factory)
    graph = KnowledgeGraphBuilder.build(factory)
    engine = PIEReasoningEngine(graph)

    resp = engine.ask("find RalcarRx pipelines")
    assert resp.detected_intent == QueryIntent.SEARCH
    assert "Similar-sounding pipelines" in resp.response_markdown
    assert "RailCarRx_InvoiceLoad" in resp.response_markdown


def test_router_classifies_railcarrx_query_as_search(ai_test_factory):
    """The pipeline-list phrasing must route to SEARCH rather than the general LLM path."""
    graph = KnowledgeGraphBuilder.build(ai_test_factory)
    router = QueryIntentRouter(graph)
    assert router.classify_intent("What are the RailCarRx pipelines we have?") == QueryIntent.SEARCH
    assert router.classify_intent("which pipelines do we have?") == QueryIntent.SEARCH


def test_fuzzy_single_asset_target_extraction(ai_test_factory):
    """Partial asset references on single-asset intents must resolve to the exact asset.

    Regression: 'Explain the railcarrx invoiceload pipeline' previously returned no
    target asset (exact-match only), so it fell through to a generic LLM answer.
    """
    factory = _add_railcarrx_pipelines(ai_test_factory)
    graph = KnowledgeGraphBuilder.build(factory)
    engine = PIEReasoningEngine(graph)

    resp = engine.ask("Explain the railcarrx invoiceload pipeline")
    assert resp.detected_intent == QueryIntent.ARCHITECTURE
    assert resp.target_asset == "RailCarRx_InvoiceLoad"


def test_fuzzy_asset_does_not_hijack_list_queries(ai_test_factory):
    """Count/list queries must keep their deterministic listing, not be rerouted to a single asset."""
    factory = _add_railcarrx_pipelines(ai_test_factory)
    graph = KnowledgeGraphBuilder.build(factory)
    engine = PIEReasoningEngine(graph)

    resp = engine.ask("How many railcarrx pipelines are there?")
    assert resp.detected_intent == QueryIntent.GENERAL
    assert "PIE - Pipeline Search" in resp.response_markdown
    assert "Matching Pipelines: 2" in resp.response_markdown
    assert "RailCarRx_InvoiceLoad" in resp.response_markdown
    assert "RailCarRx_Payments" in resp.response_markdown


def test_pipeline_search_indexes_description(ai_test_factory):
    """Pipeline keyword search must also match descriptions/annotations, not just names."""
    factory = _add_railcarrx_pipelines(ai_test_factory)
    factory.pipelines.append(
        PipelineMetadata(
            name="PL_GL_Reconciliation",
            id="/subscriptions/sub-ai-123/resourceGroups/rg-ai-test/providers/Microsoft.DataFactory/factories/adf-ai-test-factory/pipelines/PL_GL_Reconciliation",
            folder="Finance",
            description="Reconciles Coupa invoice records against RailCarRx billing statements",
            activities=[ActivityMetadata(name="Copy_GL_Recon", type="Copy")],
        )
    )
    graph = KnowledgeGraphBuilder.build(factory)
    engine = PIEReasoningEngine(graph)

    resp = engine.ask("find invoice pipelines")
    assert resp.detected_intent == QueryIntent.SEARCH
    assert "PL_GL_Reconciliation" in resp.response_markdown
    assert "matched on description" in resp.response_markdown
    assert "RailCarRx_InvoiceLoad" in resp.response_markdown


def test_pipeline_typos_and_conversational_framing(ai_test_factory):
    """Misspellings like 'piplines' must still route to pipeline search, and the listing
    should be framed with an intro line and a closing follow-up question."""
    factory = _add_railcarrx_pipelines(ai_test_factory)
    factory.pipelines.append(
        PipelineMetadata(
            name="PL_GL_Reconciliation",
            id="/subscriptions/sub-ai-123/resourceGroups/rg-ai-test/providers/Microsoft.DataFactory/factories/adf-ai-test-factory/pipelines/PL_GL_Reconciliation",
            folder="Finance",
            description="Reconciles Coupa invoice records against RailCarRx billing statements",
            activities=[ActivityMetadata(name="Copy_GL_Recon", type="Copy")],
        )
    )
    graph = KnowledgeGraphBuilder.build(factory)
    engine = PIEReasoningEngine(graph)

    resp = engine.ask("list out invoice piplines")
    assert resp.detected_intent == QueryIntent.GENERAL
    assert "Here is the list of all `invoice` pipelines I found" in resp.response_markdown
    assert "PIE - Pipeline Search" in resp.response_markdown
    assert "RailCarRx_InvoiceLoad" in resp.response_markdown
    assert "PL_GL_Reconciliation" in resp.response_markdown
    assert "Want me to explore any of these pipelines in detail?" in resp.response_markdown

    resp2 = engine.ask("find invoice piplines")
    assert resp2.detected_intent == QueryIntent.SEARCH
    assert "PIE - Pipeline Search" in resp2.response_markdown
    assert "RailCarRx_InvoiceLoad" in resp2.response_markdown
    assert "Discovered Datasets" not in resp2.response_markdown
    assert "Want me to explore any of these pipelines in detail?" in resp2.response_markdown

    resp3 = engine.ask("list all piplines")
    assert resp3.detected_intent == QueryIntent.SEARCH
    assert "complete pipeline inventory" in resp3.response_markdown
    assert "PIE - Pipeline Search: `all`" in resp3.response_markdown
    assert "Want me to explore any of these pipelines in detail?" in resp3.response_markdown


def test_give_list_of_keyword_pipelines(ai_test_factory):
    """'give a list of X pipelines' must extract X as the keyword, not the verb 'give'."""
    factory = _add_railcarrx_pipelines(ai_test_factory)
    base_id = "/subscriptions/sub-ai-123/resourceGroups/rg-ai-test/providers/Microsoft.DataFactory/factories/adf-ai-test-factory/pipelines"
    factory.pipelines.append(
        PipelineMetadata(
            name="PL_DATEX_Integration_Invoice_Load",
            id=f"{base_id}/PL_DATEX_Integration_Invoice_Load",
            folder="Datex",
            activities=[ActivityMetadata(name="Copy_DATEX_Invoice", type="Copy")],
        )
    )
    graph = KnowledgeGraphBuilder.build(factory)
    engine = PIEReasoningEngine(graph)

    resp = engine.ask("give a list of datex pipelines")
    assert resp.detected_intent == QueryIntent.SEARCH
    assert "Here is the list of all `datex` pipelines I found" in resp.response_markdown
    assert "PL_DATEX_Integration_Invoice_Load" in resp.response_markdown
    assert "Matching Pipelines: 1" in resp.response_markdown
    assert "I couldn't find any pipelines matching `give`" not in resp.response_markdown

    resp2 = engine.ask("give a list of railcar pipelines")
    assert resp2.detected_intent == QueryIntent.SEARCH
    assert "Here is the list of all `railcar` pipelines I found" in resp2.response_markdown
    assert "RailCarRx_InvoiceLoad" in resp2.response_markdown
    assert "RailCarRx_Payments" in resp2.response_markdown
    assert "Matching Pipelines: 2" in resp2.response_markdown

    resp3 = engine.ask("search around datex pipelines")
    assert resp3.detected_intent == QueryIntent.SEARCH
    assert "Here is the list of all `datex` pipelines I found" in resp3.response_markdown
    assert "PL_DATEX_Integration_Invoice_Load" in resp3.response_markdown

    resp4 = engine.ask("give  a list of datex pipelines")
    assert "Here is the list of all `datex` pipelines I found" in resp4.response_markdown


def test_llm_guide_skipped_when_mock(ai_test_factory):
    """The hybrid LLM guide must be a no-op when the mock/offline provider is active."""
    factory = _add_railcarrx_pipelines(ai_test_factory)
    graph = KnowledgeGraphBuilder.build(factory)
    engine = PIEReasoningEngine(graph)
    assert engine._llm_extract_query_intent("list railcar pipelines") is None


def test_llm_guided_intent_and_keyword(ai_test_factory):
    """The LLM's intent + search keyword must be honored and drive a grounded listing."""
    factory = _add_railcarrx_pipelines(ai_test_factory)
    graph = KnowledgeGraphBuilder.build(factory)
    stub = _StubLLMProvider([
        json.dumps({"intent": "search", "search_keyword": "railcarrx", "target_asset": None, "confidence": 0.97}),
        json.dumps({"intent": "search", "search_keyword": "railcarrx", "target_asset": None, "confidence": 0.97}),
    ])
    engine = PIEReasoningEngine(graph, llm_provider=stub)

    guide = engine._llm_extract_query_intent("show me the railcar ones")
    assert guide is not None
    assert guide.intent == QueryIntent.SEARCH
    assert guide.search_keyword == "railcarrx"

    engine._resolve_llm_provider = lambda model: engine.llm
    resp = engine.ask("give me the railcar pipelines")
    assert resp.detected_intent == QueryIntent.SEARCH
    assert "Matching Pipelines: 2" in resp.response_markdown
    assert "RailCarRx_InvoiceLoad" in resp.response_markdown
    assert "RailCarRx_Payments" in resp.response_markdown


def test_llm_target_asset_must_exist_in_graph(ai_test_factory):
    """LLM-suggested asset names that are not in the graph must be discarded (grounding)."""
    factory = _add_railcarrx_pipelines(ai_test_factory)
    graph = KnowledgeGraphBuilder.build(factory)
    stub = _StubLLMProvider([
        json.dumps({"intent": "explain", "search_keyword": None, "target_asset": "Fabricated_Pipeline_XYZ", "confidence": 0.9})
    ])
    engine = PIEReasoningEngine(graph, llm_provider=stub)

    guide = engine._llm_extract_query_intent("explain the loader pipeline")
    assert guide is not None
    assert guide.intent == QueryIntent.ARCHITECTURE
    assert guide.target_asset is None


def test_llm_malformed_intent_json_falls_back(ai_test_factory):
    """Malformed LLM output must fall back to deterministic routing, never crash."""
    factory = _add_railcarrx_pipelines(ai_test_factory)
    graph = KnowledgeGraphBuilder.build(factory)
    stub = _StubLLMProvider(["sure, here you go: {oops not valid json"])
    engine = PIEReasoningEngine(graph, llm_provider=stub)
    assert engine._llm_extract_query_intent("list pipelines") is None


def test_parse_intent_json_strips_fences():
    """Code-fenced JSON from the LLM must be parsed cleanly."""
    parsed = PIEReasoningEngine._parse_intent_json(
        '```json\n{"intent": "search", "search_keyword": "datex"}\n```'
    )
    assert parsed == {"intent": "search", "search_keyword": "datex"}


def test_llm_guide_cannot_hijack_explain_into_search(ai_test_factory):
    """'explore X' must stay an explain query even if the LLM guide would say SEARCH."""
    factory = _add_railcarrx_pipelines(ai_test_factory)
    graph = KnowledgeGraphBuilder.build(factory)
    stub = _StubLLMProvider([
        json.dumps({"intent": "search", "search_keyword": None, "target_asset": None, "confidence": 0.95})
    ])
    engine = PIEReasoningEngine(graph, llm_provider=stub)
    engine._resolve_llm_provider = lambda model: engine.llm

    bundle = engine._prepare("Yes. lets explore RailCarRx_InvoiceLoad")
    assert bundle.intent == QueryIntent.ARCHITECTURE
    assert bundle.target_asset == "RailCarRx_InvoiceLoad"
    assert bundle.deterministic_response is None
    assert "Asset Search Results" not in bundle.prompt_payload


def test_llm_keyword_preference_is_grounded(ai_test_factory):
    """A multi-word LLM keyword like 'railcarr x' must be grounded to 'railcarr'."""
    factory = _add_railcarrx_pipelines(ai_test_factory)
    graph = KnowledgeGraphBuilder.build(factory)
    engine = PIEReasoningEngine(graph)

    assert engine._extract_pipeline_keyword("list me railcarr x pipelines") == "railcarr"
    assert engine._extract_pipeline_keyword("list me railcarr x pipelines", prefer="railcarr x") == "railcarr"
    assert engine._extract_pipeline_keyword("give a list of datex pipelines", prefer="datex ones") == "datex"


def test_mock_provider_narrates_activities():
    """Offline mock explanations must narrate the actual activity sequence, not boilerplate."""
    from pie.ai.providers import DeterministicMockLLMProvider

    mock = DeterministicMockLLMProvider(LLMConfig(provider=LLMProviderType.MOCK))
    prompt = (
        "Context: `RailCarRx_InvoiceLoad` (pipeline)\n"
        "### Executive Summary\n"
        "How the data flows through it\n"
        "Step 1: Copy_Invoice[Copy] Retry:2x (Data Movement:RestSource->AzureSqlTable) - pulls invoices\n"
        "Step 2: Update_Flags[Script] Retry:0x (SQL:update flags set processed=1)\n"
    )
    text = mock.complete(prompt)
    assert "copies data from" in text
    assert "updates the records" in text


def test_strip_reasoning_preamble_removes_cot_noise():
    """Chain-of-thought / echo preamble must be cut before the final answer."""
    from pie.ai.engine import _strip_reasoning_preamble

    noisy = (
        "We need to explain pipeline RailCarRx_InvoiceLoad in plain language.\n"
        "From context: Pipeline ... Activities list ...\n"
        "But note order: The list appears not strictly sequential.\n"
        "Thus overall flow: start with setting variables and fetching secrets.\n\n"
        "**What this pipeline does**\n"
        "This pipeline pulls railcar invoice records from the RailCarRx API into staging.\n"
    )
    clean = _strip_reasoning_preamble(noisy)
    assert clean.startswith("**What this pipeline does**")
    assert "We need to explain" not in clean
    assert "But note order" not in clean
    assert clean == (
        "**What this pipeline does**\n"
        "This pipeline pulls railcar invoice records from the RailCarRx API into staging.\n"
    )


def test_strip_reasoning_preamble_leaves_clean_answers_untouched():
    """Output that already starts with the answer must be unchanged."""
    from pie.ai.engine import _strip_reasoning_preamble

    clean = "### What `RailCarRx_InvoiceLoad` does\n\nEverything looks good.\n"
    assert _strip_reasoning_preamble(clean) == clean


def test_filter_reasoning_stream_drops_preamble_then_streams():
    """The streaming filter must suppress the preamble and emit from the answer onward."""
    from pie.ai.engine import _filter_reasoning_stream

    chunks = [
        "We need to explain ", "the pipeline. From context: ", "activities... ", "reconstruct ",
        "deps... ", "**What this pipeline does**", "\nIt loads invoices.", " Done.",
    ]
    streamed = list(_filter_reasoning_stream(chunks))
    joined = "".join(streamed)
    assert joined.startswith("**What this pipeline does**\nIt loads invoices. Done.")
    assert "We need to explain" not in joined


# ---------------------------------------------------------------------------
# Change Impact Disambiguation Tests
# ---------------------------------------------------------------------------

def _build_multi_trigger_factory():
    """Factory with multiple triggers for disambiguation tests."""
    return FactoryMetadata(
        factory_name="adf-multi-trigger-factory",
        resource_group="rg-test",
        subscription_id="sub-test",
        location="centralus",
        pipelines=[
            PipelineMetadata(
                name="PL_Ingestion",
                id="/sub/rg/test/pipelines/PL_Ingestion",
                activities=[
                    ActivityMetadata(name="Copy_1", type="Copy", inputs=["DS_1"]),
                ],
            ),
            PipelineMetadata(
                name="PL_Reporting",
                id="/sub/rg/test/pipelines/PL_Reporting",
                activities=[
                    ActivityMetadata(name="Copy_2", type="Copy", inputs=["DS_2"]),
                ],
            ),
        ],
        datasets=[
            DatasetMetadata(
                name="DS_1", id="/sub/rg/test/datasets/DS_1",
                type="AzureSqlTable", linked_service_name="LS_Sql",
            ),
            DatasetMetadata(
                name="DS_2", id="/sub/rg/test/datasets/DS_2",
                type="AzureSqlTable", linked_service_name="LS_Sql",
            ),
        ],
        linked_services=[
            LinkedServiceMetadata(
                name="LS_Sql", id="/sub/rg/test/linkedservices/LS_Sql",
                type="AzureSqlDatabase",
                connection_properties={"server": "sql.database.windows.net"},
            ),
        ],
        triggers=[
            TriggerMetadata(
                name="TR_Daily_Ingest",
                id="/sub/rg/test/triggers/TR_Daily_Ingest",
                type="ScheduleTrigger", runtime_state="Started",
                recurrence_schedule="Every 1 Day(s) at 06:00 AM",
                pipelines=["PL_Ingestion"],
            ),
            TriggerMetadata(
                name="TR_Weekly_Report",
                id="/sub/rg/test/triggers/TR_Weekly_Report",
                type="ScheduleTrigger", runtime_state="Started",
                recurrence_schedule="Every 1 Week(s) at Monday 08:00 AM",
                pipelines=["PL_Reporting"],
            ),
            TriggerMetadata(
                name="TR_Monthly_Archive",
                id="/sub/rg/test/triggers/TR_Monthly_Archive",
                type="ScheduleTrigger", runtime_state="Stopped",
                recurrence_schedule="Every 1 Month(s) at 1st 02:00 AM",
                pipelines=["PL_Ingestion"],
            ),
        ],
        data_flows=[],
    )


def test_impact_disambiguation_lists_multiple_triggers():
    """Vague IMPACT query with type hint should list all matching objects."""
    factory = _build_multi_trigger_factory()
    graph = KnowledgeGraphBuilder.build(factory)
    engine = PIEReasoningEngine(graph)

    resp = engine.ask("what happens if I disable a trigger?")
    assert resp.detected_intent == QueryIntent.IMPACT
    assert resp.target_asset is None
    assert "3" in resp.response_markdown  # 3 triggers found
    assert "TR_Daily_Ingest" in resp.response_markdown
    assert "TR_Weekly_Report" in resp.response_markdown
    assert "TR_Monthly_Archive" in resp.response_markdown
    assert "Please specify" in resp.response_markdown
    assert resp.grounding_score == 100.0


def test_impact_disambiguation_single_match_auto_resolves():
    """When only one object of the hinted type exists, auto-resolve to it."""
    factory = _build_multi_trigger_factory()
    # Remove 2 of 3 triggers so only one remains
    factory.triggers = [t for t in factory.triggers if t.name == "TR_Daily_Ingest"]
    graph = KnowledgeGraphBuilder.build(factory)
    engine = PIEReasoningEngine(graph)

    resp = engine.ask("what happens if I disable a trigger?")
    assert resp.detected_intent == QueryIntent.IMPACT
    assert resp.target_asset == "TR_Daily_Ingest"
    assert len(resp.response_markdown) > 0
    assert resp.grounding_score == 100.0


def test_impact_disambiguation_no_type_hint_falls_through():
    """Vague IMPACT query with no type hint should fall through to generic LLM."""
    factory = _build_multi_trigger_factory()
    graph = KnowledgeGraphBuilder.build(factory)
    engine = PIEReasoningEngine(graph)

    resp = engine.ask("what happens if I change something?")
    assert resp.detected_intent == QueryIntent.IMPACT
    assert resp.target_asset is None
    # Should go to LLM (generic), not deterministic — response is non-empty
    assert len(resp.response_markdown) > 0


def test_impact_disambiguation_no_objects_of_type():
    """Vague IMPACT query when no objects of the hinted type exist."""
    factory = _build_multi_trigger_factory()
    factory.triggers = []  # Remove all triggers
    graph = KnowledgeGraphBuilder.build(factory)
    engine = PIEReasoningEngine(graph)

    resp = engine.ask("what happens if I disable a trigger?")
    assert resp.detected_intent == QueryIntent.IMPACT
    assert resp.target_asset is None
    assert "No" in resp.response_markdown
    assert "Trigger" in resp.response_markdown
    assert "found" in resp.response_markdown


def test_impact_disambiguation_works_for_pipelines():
    """Vague IMPACT query with pipeline type hint should list all pipelines."""
    factory = _build_multi_trigger_factory()
    graph = KnowledgeGraphBuilder.build(factory)
    engine = PIEReasoningEngine(graph)

    resp = engine.ask("what if I delete a pipeline?")
    assert resp.detected_intent == QueryIntent.IMPACT
    assert resp.target_asset is None
    assert "2" in resp.response_markdown  # 2 pipelines
    assert "PL_Ingestion" in resp.response_markdown
    assert "PL_Reporting" in resp.response_markdown
    assert "Please specify" in resp.response_markdown
