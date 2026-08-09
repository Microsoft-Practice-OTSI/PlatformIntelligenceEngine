"""Domain models for PIE In-Memory Knowledge Graph and Lineage Traversal."""

from enum import Enum
from typing import Any
from datetime import datetime
from pydantic import BaseModel, Field


class NodeType(str, Enum):
    """ADF entities represented as nodes in the Knowledge Graph."""
    PIPELINE = "Pipeline"
    ACTIVITY = "Activity"
    DATASET = "Dataset"
    LINKED_SERVICE = "LinkedService"
    TRIGGER = "Trigger"
    DATA_FLOW = "DataFlow"


class EdgeType(str, Enum):
    """Directed structural and dependency relationships."""
    CONTAINS = "CONTAINS"          # Pipeline -> Activity
    CALLS = "CALLS"                # Activity -> Child Pipeline (ExecutePipeline)
    READS = "READS"                # Activity / DataFlow -> Input Dataset (Source)
    WRITES = "WRITES"              # Activity / DataFlow -> Output Dataset (Sink)
    USES = "USES"                  # Activity / Dataset -> LinkedService
    DEPENDS_ON = "DEPENDS_ON"      # Activity -> Preceding Activity (Execution Order)
    TRIGGERED_BY = "TRIGGERED_BY"  # Pipeline -> Trigger
    EXECUTES = "EXECUTES"          # Trigger -> Pipeline


class GraphNode(BaseModel):
    """Normalized vertex in the Knowledge Graph."""
    id: str = Field(description="Unique qualified ID, e.g. pipeline:PL_Customer_Daily_Ingestion")
    name: str
    type: NodeType
    folder: str | None = None
    description: str | None = None
    properties: dict[str, Any] = Field(default_factory=dict, description="Normalized entity properties (retry policy, schema, etc.)")
    annotations: list[str] = Field(default_factory=list)


class GraphEdge(BaseModel):
    """Directed edge in the Knowledge Graph."""
    source_id: str
    target_id: str
    type: EdgeType
    properties: dict[str, Any] = Field(default_factory=dict)


class Subgraph(BaseModel):
    """Localized k-hop subgraph extracted around a target asset (Context Builder ready)."""
    root_node_id: str
    max_hops: int
    nodes: dict[str, GraphNode] = Field(default_factory=dict)
    edges: list[GraphEdge] = Field(default_factory=list)


class ImpactReport(BaseModel):
    """Deterministic blast-radius and change-risk assessment for an asset."""
    target_asset_id: str
    target_asset_name: str
    target_asset_type: NodeType
    directly_affected_assets: list[str] = Field(default_factory=list, description="Immediate 1-hop downstream dependents")
    total_downstream_impact_count: int = Field(default=0, description="Total multi-hop downstream assets affected")
    affected_pipelines: list[str] = Field(default_factory=list, description="Pipelines that will fail or be impacted")
    affected_datasets: list[str] = Field(default_factory=list, description="Datasets downstream of this asset")
    affected_triggers: list[str] = Field(default_factory=list, description="Triggers associated with impacted assets")
    upstream_dependencies: list[str] = Field(default_factory=list, description="Upstream assets feeding into this asset")
    risk_level: str = Field(default="LOW", description="LOW | MEDIUM | HIGH | CRITICAL")
    risk_score: int = Field(default=0, description="Score 0-100 based on blast radius and pipeline criticality")


class Spike3Result(BaseModel):
    """Standardized output schema for Spike 3 (Knowledge Graph Prototype)."""
    spike_id: str = "spike_3_knowledge_graph_prototype"
    status: str = "SUCCESS"
    executed_at: datetime = Field(default_factory=datetime.utcnow)
    factory_name: str
    total_nodes: int
    total_edges: int
    node_counts_by_type: dict[str, int]
    edge_counts_by_type: dict[str, int]
    cycles_detected: list[list[str]] = Field(default_factory=list)
    sample_impact_reports: list[ImpactReport] = Field(default_factory=list)
