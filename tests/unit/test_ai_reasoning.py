"""Unit tests for PIE AI Reasoning Engine, Intent Classification, and Conversational Chat."""

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
from pie.ai.models import QueryIntent, ReasoningResponse
from pie.ai.router import QueryIntentRouter
from pie.ai.engine import PIEReasoningEngine


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


def test_pie_reasoning_engine_end_to_end(ai_test_factory):
    """Verify PIEReasoningEngine handles queries across intents with 100% grounding."""
    graph = KnowledgeGraphBuilder.build(ai_test_factory)
    engine = PIEReasoningEngine(graph)

    # 1. Architecture Query
    resp_arch = engine.ask("Explain PL_Customer_Ingestion")
    assert isinstance(resp_arch, ReasoningResponse)
    assert resp_arch.detected_intent == QueryIntent.ARCHITECTURE
    assert resp_arch.target_asset == "PL_Customer_Ingestion"
    assert "Architectural Overview" in resp_arch.response_markdown

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
