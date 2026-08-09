"""Unit tests for PIE Context Builder, Subgraph Extractor, and Token Budgeting."""

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
from pie.context.models import TokenBudget, ContextPackage
from pie.context.compressor import SchemaCompressor
from pie.context.budgeter import TokenBudgeter
from pie.context.builder import ContextBuilder


@pytest.fixture
def context_test_factory() -> FactoryMetadata:
    """Fixture providing a multi-layer pipeline topology for context testing."""
    return FactoryMetadata(
        factory_name="adf-context-test-factory",
        resource_group="rg-context-test",
        subscription_id="sub-context-123",
        location="centralus",
        pipelines=[
            PipelineMetadata(
                name="PL_Invoice_Processing",
                id="/subscriptions/sub-context-123/resourceGroups/rg-context-test/providers/Microsoft.DataFactory/factories/adf-context-test-factory/pipelines/PL_Invoice_Processing",
                folder="Finance",
                activities=[
                    ActivityMetadata(
                        name="Lookup_Watermark",
                        type="Lookup",
                        inputs=["DS_Invoice_Watermark"],
                        outputs=[],
                        type_properties={"sqlReaderQuery": "SELECT MAX(LastSync) FROM Watermark"},
                    ),
                    ActivityMetadata(
                        name="Copy_Invoices_To_Stage",
                        type="Copy",
                        inputs=["DS_Raw_Invoice_Csv"],
                        outputs=["DS_Staging_SQL_Table"],
                        depends_on=["Lookup_Watermark"],
                        type_properties={
                            "source": {"type": "DelimitedTextSource"},
                            "sink": {"type": "SqlSink"},
                        },
                    ),
                ],
            )
        ],
        datasets=[
            DatasetMetadata(
                name="DS_Invoice_Watermark",
                id="/subscriptions/sub-context-123/resourceGroups/rg-context-test/providers/Microsoft.DataFactory/factories/adf-context-test-factory/datasets/DS_Invoice_Watermark",
                type="AzureSqlTable",
                linked_service_name="LS_Azure_SQL_Watermark",
                schema_fields=[{"name": "LastSync", "type": "datetime"}],
            ),
            DatasetMetadata(
                name="DS_Raw_Invoice_Csv",
                id="/subscriptions/sub-context-123/resourceGroups/rg-context-test/providers/Microsoft.DataFactory/factories/adf-context-test-factory/datasets/DS_Raw_Invoice_Csv",
                type="DelimitedText",
                linked_service_name="LS_DataLake_Storage",
                schema_fields=[
                    {"name": "InvoiceID", "type": "string"},
                    {"name": "Amount", "type": "decimal"},
                    {"name": "VendorName", "type": "string"},
                ],
            ),
            DatasetMetadata(
                name="DS_Staging_SQL_Table",
                id="/subscriptions/sub-context-123/resourceGroups/rg-context-test/providers/Microsoft.DataFactory/factories/adf-context-test-factory/datasets/DS_Staging_SQL_Table",
                type="SqlServerTable",
                linked_service_name="LS_OnPrem_SQL",
                schema_fields=[
                    {"name": "InvoiceID", "type": "string"},
                    {"name": "Amount", "type": "decimal"},
                ],
            ),
        ],
        linked_services=[
            LinkedServiceMetadata(
                name="LS_DataLake_Storage",
                id="/subscriptions/sub-context-123/resourceGroups/rg-context-test/providers/Microsoft.DataFactory/factories/adf-context-test-factory/linkedservices/LS_DataLake_Storage",
                type="AzureBlobFS",
                connection_properties={"url": "https://adls.dfs.core.windows.net"},
            ),
            LinkedServiceMetadata(
                name="LS_OnPrem_SQL",
                id="/subscriptions/sub-context-123/resourceGroups/rg-context-test/providers/Microsoft.DataFactory/factories/adf-context-test-factory/linkedservices/LS_OnPrem_SQL",
                type="SqlServer",
                connection_properties={"server": "sqlonprem01.local"},
            ),
            LinkedServiceMetadata(
                name="LS_Azure_SQL_Watermark",
                id="/subscriptions/sub-context-123/resourceGroups/rg-context-test/providers/Microsoft.DataFactory/factories/adf-context-test-factory/linkedservices/LS_Azure_SQL_Watermark",
                type="AzureSqlDatabase",
                connection_properties={"server": "sqlwatermark.database.windows.net"},
            ),
        ],
        triggers=[
            TriggerMetadata(
                name="TR_Daily_Midnight",
                id="/subscriptions/sub-context-123/resourceGroups/rg-context-test/providers/Microsoft.DataFactory/factories/adf-context-test-factory/triggers/TR_Daily_Midnight",
                type="ScheduleTrigger",
                runtime_state="Started",
                recurrence_schedule="Every 1 Day(s)",
                pipelines=["PL_Invoice_Processing"],
            )
        ],
        data_flows=[],
    )


def test_schema_compressor(context_test_factory):
    """Verify SchemaCompressor removes raw JSON noise and outputs dense markdown."""
    graph = KnowledgeGraphBuilder.build(context_test_factory)
    act_node = graph.get_node("activity:PL_Invoice_Processing.Copy_Invoices_To_Stage")
    assert act_node is not None

    compressed_act = SchemaCompressor.compress_activity_node(act_node, step_num=2)
    assert "Step 2" in compressed_act
    assert "Copy_Invoices_To_Stage" in compressed_act
    assert "Data Movement" in compressed_act

    ds_node = graph.get_node("dataset:DS_Raw_Invoice_Csv")
    assert ds_node is not None
    compressed_ds = SchemaCompressor.compress_dataset_node(ds_node)
    assert "InvoiceID" in compressed_ds
    assert "LS_DataLake_Storage" in compressed_ds


def test_token_budgeter():
    """Verify token estimation and budget truncation."""
    text = "Hello world! This is a test token estimation string."
    tokens = TokenBudgeter.estimate_tokens(text)
    assert tokens > 0

    lines = [f"Item {i}: Sample configuration detail description line" for i in range(50)]
    fitted = TokenBudgeter.fit_lines_to_budget(lines, max_tokens=100, section_name="test_items")
    assert "Item 0" in fitted
    # Ensure truncation notice is added if budget exceeded
    assert "additional test_items items compressed" in fitted


def test_context_builder_end_to_end(context_test_factory):
    """Verify complete ContextPackage generation with token reduction metrics."""
    graph = KnowledgeGraphBuilder.build(context_test_factory)
    builder = ContextBuilder(graph)
    budget = TokenBudget(max_tokens=2000)

    pkg = builder.build_context_package("PL_Invoice_Processing", budget=budget)
    assert isinstance(pkg, ContextPackage)
    assert pkg.target_asset_name == "PL_Invoice_Processing"
    assert pkg.target_asset_type == "Pipeline"
    assert pkg.raw_uncompressed_tokens > 0
    assert pkg.compressed_context_tokens > 0
    # Token savings should be substantial (typically 70% to 95%+)
    assert pkg.compression_ratio > 40.0
    assert "### Executive Summary" in pkg.full_prompt_payload_md
    assert "### Minute Activity Execution Sequence" in pkg.full_prompt_payload_md
    assert "### Input / Output Datasets & Schemas" in pkg.full_prompt_payload_md


def test_multi_intent_context_builder(context_test_factory):
    """Verify context builder generates distinct payloads for Architecture, Debugging, and Impact intents."""
    from pie.context.intent_builder import MultiIntentContextBuilder, ContextIntent
    graph = KnowledgeGraphBuilder.build(context_test_factory)
    intent_builder = MultiIntentContextBuilder(graph)

    # 1. Architecture intent
    arch_pkg = intent_builder.build_intent_package("PL_Invoice_Processing", intent=ContextIntent.ARCHITECTURE)
    assert "Executive Architectural Overview" in arch_pkg.full_prompt_payload_md

    # 2. Debugging intent
    debug_pkg = intent_builder.build_intent_package("PL_Invoice_Processing", intent=ContextIntent.DEBUGGING)
    assert "Technical Debugging & Execution Specification" in debug_pkg.full_prompt_payload_md
    assert "Lookup_Watermark" in debug_pkg.full_prompt_payload_md

    # 3. Impact Analysis intent on dataset
    impact_pkg = intent_builder.build_intent_package("DS_Invoice_Watermark", intent=ContextIntent.IMPACT_ANALYSIS)
    assert "Systemic Change Risk & Blast Radius Assessment" in impact_pkg.full_prompt_payload_md

