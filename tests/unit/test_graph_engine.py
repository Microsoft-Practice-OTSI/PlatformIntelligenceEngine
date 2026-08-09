"""Unit tests for PIE Knowledge Graph construction, lineage traversal, and impact analysis."""

import pytest
from pie.discovery.models import (
    FactoryMetadata,
    PipelineMetadata,
    ActivityMetadata,
    DatasetMetadata,
    LinkedServiceMetadata,
    TriggerMetadata,
    DataFlowMetadata,
    RetryPolicy,
)
from pie.graph.models import (
    NodeType,
    EdgeType,
    GraphNode,
    GraphEdge,
    ImpactReport,
)
from pie.graph.builder import KnowledgeGraphBuilder, KnowledgeGraph
from pie.graph.traversal import GraphTraversalService
from spikes.spike_2_discovery.mock_adf_fixture import get_mock_spike_2_result


@pytest.fixture
def sample_factory_meta() -> FactoryMetadata:
    """Fixture providing an interconnected enterprise ADF topology."""
    return FactoryMetadata(
        factory_name="adf-unit-test-factory",
        resource_group="rg-test",
        subscription_id="sub-test-123",
        location="centralus",
        pipelines=[
            PipelineMetadata(
                name="PL_Parent_Ingestion",
                id="/subscriptions/sub-test-123/resourceGroups/rg-test/providers/Microsoft.DataFactory/factories/adf-unit-test-factory/pipelines/PL_Parent_Ingestion",
                folder="Ingestion",
                parameters={"batch_id": {"name": "batch_id", "type": "string", "default_value": "batch_001"}},
                activities=[
                    ActivityMetadata(
                        name="Extract_CRM",
                        type="Copy",
                        inputs=["DS_CRM_Source"],
                        outputs=["DS_Raw_DataLake"],
                        depends_on=[],
                    ),
                    ActivityMetadata(
                        name="Trigger_Child_Processing",
                        type="ExecutePipeline",
                        called_pipeline="PL_Child_Processing",
                        depends_on=["Extract_CRM"],
                    ),
                ],
            ),
            PipelineMetadata(
                name="PL_Child_Processing",
                id="/subscriptions/sub-test-123/resourceGroups/rg-test/providers/Microsoft.DataFactory/factories/adf-unit-test-factory/pipelines/PL_Child_Processing",
                folder="Processing",
                activities=[
                    ActivityMetadata(
                        name="Transform_Data",
                        type="DataFlow",
                        inputs=["DS_Raw_DataLake"],
                        outputs=["DS_Curated_SQL"],
                        depends_on=[],
                    )
                ],
            ),
        ],
        datasets=[
            DatasetMetadata(
                name="DS_CRM_Source",
                id="/subscriptions/sub-test-123/resourceGroups/rg-test/providers/Microsoft.DataFactory/factories/adf-unit-test-factory/datasets/DS_CRM_Source",
                type="DynamicsEntity",
                linked_service_name="LS_Dynamics_CRM",
                folder="Sources",
            ),
            DatasetMetadata(
                name="DS_Raw_DataLake",
                id="/subscriptions/sub-test-123/resourceGroups/rg-test/providers/Microsoft.DataFactory/factories/adf-unit-test-factory/datasets/DS_Raw_DataLake",
                type="Parquet",
                linked_service_name="LS_DataLake_Storage",
                folder="Raw",
            ),
            DatasetMetadata(
                name="DS_Curated_SQL",
                id="/subscriptions/sub-test-123/resourceGroups/rg-test/providers/Microsoft.DataFactory/factories/adf-unit-test-factory/datasets/DS_Curated_SQL",
                type="AzureSqlTable",
                linked_service_name="LS_Azure_SQL",
                folder="Curated",
            ),
        ],
        linked_services=[
            LinkedServiceMetadata(
                name="LS_Dynamics_CRM",
                id="/subscriptions/sub-test-123/resourceGroups/rg-test/providers/Microsoft.DataFactory/factories/adf-unit-test-factory/linkedservices/LS_Dynamics_CRM",
                type="Dynamics",
                connection_properties={"serviceUri": "https://test.crm.dynamics.com"},
            ),
            LinkedServiceMetadata(
                name="LS_DataLake_Storage",
                id="/subscriptions/sub-test-123/resourceGroups/rg-test/providers/Microsoft.DataFactory/factories/adf-unit-test-factory/linkedservices/LS_DataLake_Storage",
                type="AzureBlobFS",
                connection_properties={"url": "https://teststorage.dfs.core.windows.net"},
            ),
            LinkedServiceMetadata(
                name="LS_Azure_SQL",
                id="/subscriptions/sub-test-123/resourceGroups/rg-test/providers/Microsoft.DataFactory/factories/adf-unit-test-factory/linkedservices/LS_Azure_SQL",
                type="AzureSqlDatabase",
                connection_properties={"server": "sql-test.database.windows.net"},
            ),
        ],
        triggers=[
            TriggerMetadata(
                name="TR_Hourly_Schedule",
                id="/subscriptions/sub-test-123/resourceGroups/rg-test/providers/Microsoft.DataFactory/factories/adf-unit-test-factory/triggers/TR_Hourly_Schedule",
                type="ScheduleTrigger",
                runtime_state="Started",
                recurrence_schedule="Every 1 Hour(s)",
                pipelines=["PL_Parent_Ingestion"],
            )
        ],
        data_flows=[],
    )


def test_graph_builder_construction(sample_factory_meta):
    """Verify graph builder adds all vertices and directed edges accurately."""
    graph = KnowledgeGraphBuilder.build(sample_factory_meta)

    # Vertices check
    assert "pipeline:PL_Parent_Ingestion" in graph.nodes
    assert "pipeline:PL_Child_Processing" in graph.nodes
    assert "dataset:DS_CRM_Source" in graph.nodes
    assert "dataset:DS_Raw_DataLake" in graph.nodes
    assert "linked_service:LS_Dynamics_CRM" in graph.nodes
    assert "trigger:TR_Hourly_Schedule" in graph.nodes

    # Node types
    assert graph.nodes["pipeline:PL_Parent_Ingestion"].type == NodeType.PIPELINE
    assert graph.nodes["dataset:DS_CRM_Source"].type == NodeType.DATASET
    assert graph.nodes["trigger:TR_Hourly_Schedule"].type == NodeType.TRIGGER

    # Check relationships
    # Trigger -[EXECUTES]-> Pipeline
    exec_edges = graph.get_outgoing_edges("trigger:TR_Hourly_Schedule", EdgeType.EXECUTES)
    assert len(exec_edges) == 1
    assert exec_edges[0].target_id == "pipeline:PL_Parent_Ingestion"

    # Dataset -[USES]-> LinkedService
    ls_edges = graph.get_outgoing_edges("dataset:DS_CRM_Source", EdgeType.USES)
    assert len(ls_edges) == 1
    assert ls_edges[0].target_id == "linked_service:LS_Dynamics_CRM"


def test_upstream_lineage_traversal(sample_factory_meta):
    """Verify upstream lineage traces backward from child pipeline or sink to sources and triggers."""
    graph = KnowledgeGraphBuilder.build(sample_factory_meta)
    traversal = GraphTraversalService(graph)

    # Trace upstream of PL_Child_Processing
    upstream = traversal.get_upstream_lineage("PL_Child_Processing", max_hops=4)
    assert len(upstream) > 0
    upstream_names = [item["name"] for item in upstream]
    # Parent pipeline and preceding activity should be detected
    assert "PL_Parent_Ingestion" in upstream_names or "Trigger_Child_Processing" in upstream_names


def test_downstream_blast_radius(sample_factory_meta):
    """Verify downstream impact calculation from source/linked service to consumers."""
    graph = KnowledgeGraphBuilder.build(sample_factory_meta)
    traversal = GraphTraversalService(graph)

    # If LS_Dynamics_CRM is modified/deleted, check what is affected
    impacts = traversal.get_downstream_impact("LS_Dynamics_CRM", max_hops=4)
    # DS_CRM_Source uses LS_Dynamics_CRM
    assert len(impacts) >= 1
    impact_names = [item["name"] for item in impacts]
    assert "DS_CRM_Source" in impact_names


def test_k_hop_subgraph_extraction(sample_factory_meta):
    """Verify localized k-hop subgraph extraction isolates relevant neighbors without full graph bloat."""
    graph = KnowledgeGraphBuilder.build(sample_factory_meta)
    traversal = GraphTraversalService(graph)

    subgraph = traversal.extract_k_hop_subgraph("pipeline:PL_Parent_Ingestion", k=1)
    assert subgraph.root_node_id == "pipeline:PL_Parent_Ingestion"
    assert "pipeline:PL_Parent_Ingestion" in subgraph.nodes
    # 1-hop should include activities, input datasets, and triggers
    assert len(subgraph.nodes) > 1
    assert len(subgraph.edges) > 0


def test_cycle_detection():
    """Verify cycle detector identifies circular recursion loops."""
    graph = KnowledgeGraph("cyclic-test")
    # Build cycle: PipeA -[CALLS]-> PipeB -[CALLS]-> PipeC -[CALLS]-> PipeA
    graph.add_node(GraphNode(id="pipeline:PipeA", name="PipeA", type=NodeType.PIPELINE))
    graph.add_node(GraphNode(id="pipeline:PipeB", name="PipeB", type=NodeType.PIPELINE))
    graph.add_node(GraphNode(id="pipeline:PipeC", name="PipeC", type=NodeType.PIPELINE))

    graph.add_edge("pipeline:PipeA", "pipeline:PipeB", EdgeType.CALLS)
    graph.add_edge("pipeline:PipeB", "pipeline:PipeC", EdgeType.CALLS)
    graph.add_edge("pipeline:PipeC", "pipeline:PipeA", EdgeType.CALLS)

    traversal = GraphTraversalService(graph)
    cycles = traversal.detect_cycles()

    assert len(cycles) > 0
    cycle_nodes = cycles[0]
    assert "pipeline:PipeA" in cycle_nodes
    assert "pipeline:PipeB" in cycle_nodes
    assert "pipeline:PipeC" in cycle_nodes


def test_impact_report_scoring(sample_factory_meta):
    """Verify deterministic risk scoring and impact assessment."""
    graph = KnowledgeGraphBuilder.build(sample_factory_meta)
    traversal = GraphTraversalService(graph)

    report = traversal.compute_impact_report("LS_Dynamics_CRM")
    assert isinstance(report, ImpactReport)
    assert report.target_asset_name == "LS_Dynamics_CRM"
    assert report.target_asset_type == NodeType.LINKED_SERVICE
    assert report.risk_score >= 25
    assert report.risk_level in ["MEDIUM", "HIGH", "CRITICAL"]


def test_pipeline_storyteller(sample_factory_meta):
    """Verify deep minute activity extraction and plain language pipeline walkthrough."""
    from pie.graph.storyteller import PipelineStoryteller
    graph = KnowledgeGraphBuilder.build(sample_factory_meta)
    storyteller = PipelineStoryteller(graph)

    story = storyteller.explain_pipeline("PL_Parent_Ingestion")
    assert story["found"] is True
    assert story["pipeline_name"] == "PL_Parent_Ingestion"
    assert story["total_activities"] == 2
    assert "PL_Child_Processing" in story["child_pipelines"]
    assert len(story["execution_steps"]) == 2
    assert story["execution_steps"][0]["activity_name"] == "Extract_CRM"
    assert story["execution_steps"][1]["activity_name"] == "Trigger_Child_Processing"


def test_asset_query_engine(sample_factory_meta):
    """Verify multi-criteria asset search (e.g. file_type='parquet', 'onprem')."""
    from pie.graph.query_engine import AssetQueryEngine
    graph = KnowledgeGraphBuilder.build(sample_factory_meta)
    query_engine = AssetQueryEngine(graph)

    # Search parquet datasets
    parquet_matches = query_engine.find_datasets(file_type="parquet")
    assert len(parquet_matches) >= 1
    assert parquet_matches[0]["dataset_name"] == "DS_Raw_DataLake"

    # Search datasets in 'Sources' folder
    source_matches = query_engine.find_datasets(folder="sources")
    assert len(source_matches) >= 1
    assert source_matches[0]["dataset_name"] == "DS_CRM_Source"


def test_asset_deletion_simulator(sample_factory_meta):
    """Verify simulation of deleting a dataset and cascade failure detection."""
    from pie.graph.deletion_simulator import AssetDeletionSimulator
    graph = KnowledgeGraphBuilder.build(sample_factory_meta)
    simulator = AssetDeletionSimulator(graph)

    # Simulate deleting DS_CRM_Source
    sim = simulator.simulate_dataset_deletion("DS_CRM_Source")
    assert sim["found"] is True
    assert sim["target_dataset"] == "DS_CRM_Source"
    assert sim["immediate_failures"]["total_broken_activities"] >= 1
    # Activity Extract_CRM reads from DS_CRM_Source
    assert len(sim["immediate_failures"]["broken_readers"]) >= 1
    assert len(sim["remediation_plan"]) > 0


def test_security_and_governance_auditor(sample_factory_meta):
    """Verify vendor mapping and Key Vault security compliance."""
    from pie.graph.audit_engine import SecurityAndGovernanceAuditor
    graph = KnowledgeGraphBuilder.build(sample_factory_meta)
    auditor = SecurityAndGovernanceAuditor(graph)

    audit = auditor.audit_security_and_vendors()
    assert "Microsoft Dynamics CRM" in audit["external_saas_vendors"]
    assert audit["total_vendor_integrations"] >= 1


def test_technical_debt_and_orphan_detector(sample_factory_meta):
    """Verify detection of orphan pipelines and zero-retry activities."""
    from pie.graph.audit_engine import TechnicalDebtAndOrphanDetector
    graph = KnowledgeGraphBuilder.build(sample_factory_meta)
    detector = TechnicalDebtAndOrphanDetector(graph)

    debt = detector.detect_technical_debt()
    # PL_Child_Processing is called by PL_Parent_Ingestion, TR_Hourly_Schedule executes PL_Parent_Ingestion
    assert isinstance(debt["orphan_pipelines"], list)
    assert debt["zero_retry_fragile_activities_count"] >= 1


def test_schedule_concurrency_and_deep_search(sample_factory_meta):
    """Verify schedule concurrency heatmap and full-text global search."""
    from pie.graph.audit_engine import ScheduleConcurrencyHeatmap, DeepPropertySearchEngine
    graph = KnowledgeGraphBuilder.build(sample_factory_meta)
    heatmap = ScheduleConcurrencyHeatmap(graph)
    searcher = DeepPropertySearchEngine(graph)

    # Concurrency
    concurrency = heatmap.analyze_schedule_concurrency()
    assert concurrency["total_triggers"] == 1
    assert "Every 1 Hour(s)" in concurrency["schedule_distribution"]

    # Deep Search
    results = searcher.search_properties("CRM")
    assert len(results) >= 1
    matched_names = [r["name"] for r in results]
    assert "DS_CRM_Source" in matched_names or "Extract_CRM" in matched_names



