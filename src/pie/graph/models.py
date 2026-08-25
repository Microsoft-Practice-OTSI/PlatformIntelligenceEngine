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
    INTEGRATION_RUNTIME = "IntegrationRuntime"
    PARAMETER = "Parameter"
    VARIABLE = "Variable"


class EdgeType(str, Enum):
    """Directed structural and dependency relationships."""
    CONTAINS = "CONTAINS"                    # Pipeline -> Activity
    CALLS = "CALLS"                          # Activity -> Child Pipeline (ExecutePipeline)
    READS = "READS"                          # Activity / DataFlow -> Input Dataset (Source)
    WRITES = "WRITES"                        # Activity / DataFlow -> Output Dataset (Sink)
    USES = "USES"                            # Activity / Dataset -> LinkedService
    DEPENDS_ON = "DEPENDS_ON"                # Activity -> Preceding Activity (Execution Order)
    TRIGGERED_BY = "TRIGGERED_BY"            # Pipeline -> Trigger
    EXECUTES = "EXECUTES"                    # Trigger -> Pipeline
    REFERENCES = "REFERENCES"                # Activity -> Dataset/LinkedService (expression ref)
    REFERENCES_OUTPUT_OF = "REFERENCES_OUTPUT_OF"  # Activity -> Activity (output value ref)
    CALLS_API = "CALLS_API"                  # Activity -> LinkedService (Web/REST call)
    USES_INTEGRATION_RUNTIME = "USES_INTEGRATION_RUNTIME"  # LinkedService -> IntegrationRuntime
    ITERATES_OVER = "ITERATES_OVER"          # ForEach Activity -> Activity (loop body)
    CONDITION_DEPENDS_ON = "CONDITION_DEPENDS_ON"  # If Condition -> Activity (condition expr)


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


# ---------------------------------------------------------------------------
# Change Impact Intelligence Engine — Domain Models
# ---------------------------------------------------------------------------


class ChangeType(str, Enum):
    """Supported change scenarios for impact analysis."""
    REMOVE = "REMOVE"
    DELETE = "DELETE"
    DISABLE = "DISABLE"
    MODIFY = "MODIFY"
    REPLACE = "REPLACE"
    RENAME = "RENAME"
    DECOMMISSION = "DECOMMISSION"


class DependencyClassification(str, Enum):
    """How a discovered relationship was classified."""
    DIRECT = "DIRECT"                    # ADF explicitly defines the relationship
    DATA_REFERENCE = "DATA_REFERENCE"    # Activity consumes target's output
    STRUCTURAL = "STRUCTURAL"            # Exists through ADF execution structure
    INDIRECT = "INDIRECT"                # Discovered through graph traversal
    EXTERNAL = "EXTERNAL"                # Crosses into another system
    INFERRED = "INFERRED"               # Based on naming/contextual evidence


class ConfidenceLevel(str, Enum):
    """How confident we are in a discovered dependency."""
    HIGH = "HIGH"      # Explicit technical evidence (ADF dependency, expression ref)
    MEDIUM = "MEDIUM"  # Strongly implied by configuration or graph structure
    LOW = "LOW"        # Inferred from naming, descriptions, or context


class ImpactScope(str, Enum):
    """Scope at which impact is measured."""
    IMMEDIATE = "IMMEDIATE"            # Directly affected object
    PIPELINE = "PIPELINE"              # Other activities within the same pipeline
    WORKFLOW = "WORKFLOW"              # Parent and child pipelines
    PLATFORM = "PLATFORM"             # Other ADF objects
    EXTERNAL_SYSTEM = "EXTERNAL_SYSTEM"  # APIs, databases, SaaS systems
    BUSINESS_PROCESS = "BUSINESS_PROCESS"  # Potential business consequence


class ChangeRequest(BaseModel):
    """Generic change request model — normalized from any NL question."""
    target_object: str = Field(description="Name or ID of the target ADF object")
    object_type: NodeType | None = Field(default=None, description="ADF object type (auto-detected if omitted)")
    parent_context: str | None = Field(default=None, description="Parent pipeline name for activity targets")
    change_type: ChangeType = Field(description="Proposed change action")
    requested_action: str | None = Field(default=None, description="Original NL description of the change")
    scope: str = Field(default="ADF Factory", description="Scope of the analysis")


class ImpactFinding(BaseModel):
    """A single evidence-backed impact finding."""
    asset: str = Field(description="Name of the affected asset")
    asset_type: NodeType = Field(description="Type of the affected asset")
    impact_type: str = Field(description="How this asset is affected (e.g. BROKEN_SOURCE, MISSING_INPUT)")
    relationship: DependencyClassification = Field(description="How the relationship was classified")
    reason: str = Field(description="Human-readable explanation of why this is affected")
    evidence: list[str] = Field(default_factory=list, description="Technical evidence (expressions, edges)")
    confidence: ConfidenceLevel = Field(description="Confidence in this finding")
    severity: str = Field(default="MEDIUM", description="LOW / MEDIUM / HIGH / CRITICAL")


class RiskAssessment(BaseModel):
    """Explainable risk classification for a change request."""
    level: str = Field(description="LOW / MEDIUM / HIGH / CRITICAL")
    score: int = Field(description="Numeric score 0-100")
    reasons: list[str] = Field(default_factory=list, description="Why this risk level was assigned")
    scopes: list[ImpactScope] = Field(default_factory=list, description="Scopes where impact was detected")


class ImpactAnalysis(BaseModel):
    """Complete structured output of a Change Impact Analysis."""
    target: dict[str, str] = Field(description="Target object info: {id, name, objectType}")
    requested_change: ChangeRequest
    risk: RiskAssessment
    direct_impacts: list[ImpactFinding] = Field(default_factory=list)
    indirect_impacts: list[ImpactFinding] = Field(default_factory=list)
    affected_pipelines: list[str] = Field(default_factory=list)
    affected_assets: list[str] = Field(default_factory=list)
    external_systems: list[str] = Field(default_factory=list)
    evidence: list[ImpactFinding] = Field(default_factory=list)
    confidence: ConfidenceLevel = Field(default=ConfidenceLevel.HIGH)
    potential_consequences: list[str] = Field(default_factory=list)
    recommendation: str = Field(default="", description="AI-generated safe next steps")
    impact_chain: list[str] = Field(default_factory=list, description="Ordered chain of affected assets")
    summary_md: str = Field(default="", description="Human-readable markdown summary")
    disambiguation: str | None = Field(default=None, description="Clarification message when multiple objects match the target name")


class ExpressionReference(BaseModel):
    """A reference discovered in an ADF expression."""
    source_name: str = Field(description="The asset being referenced (e.g. activity name)")
    target_name: str = Field(description="The asset containing the reference")
    expression: str = Field(description="The raw ADF expression text")
    reference_type: str = Field(description="OUTPUT_REFERENCE, PARAMETER_REFERENCE, DATASET_REFERENCE")
    confidence: ConfidenceLevel = Field(default=ConfidenceLevel.HIGH)
