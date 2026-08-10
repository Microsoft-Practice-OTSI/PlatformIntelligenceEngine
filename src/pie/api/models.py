"""Pydantic v2 DTO schemas and API request/response models for PIE Core REST API."""

from typing import Any, Optional
from pydantic import BaseModel, Field


# --- Auth & Session Models ---

class SessionInfo(BaseModel):
    authenticated: bool = True
    tenant_id: Optional[str] = None
    subscription_id: Optional[str] = None
    user_id: Optional[str] = "engineer@company.com"
    auth_mode: str = "default"
    claims: dict[str, Any] = Field(default_factory=dict)


class TokenExchangeRequest(BaseModel):
    auth_code: Optional[str] = None
    teams_token: Optional[str] = None
    redirect_uri: Optional[str] = None


class LoginUrlResponse(BaseModel):
    login_url: str
    auth_mode: str
    tenant_id: str


class DeviceCodeResponse(BaseModel):
    user_code: str
    verification_uri: str
    message: str
    expires_in_seconds: int = 900


# --- Discovery & Hierarchy Models ---

class SubscriptionItem(BaseModel):
    subscription_id: str
    subscription_name: str
    state: str = "Enabled"


class SubscriptionListResponse(BaseModel):
    subscriptions: list[SubscriptionItem]
    total: int


class FactoryItem(BaseModel):
    factory_name: str
    resource_group: str
    subscription_id: str
    location: str = "centralus"
    pipeline_count: Optional[int] = 0
    is_synced: bool = True
    last_refreshed_at: Optional[str] = None


class FactoryListResponse(BaseModel):
    factories: list[FactoryItem]
    total: int


class SyncRequest(BaseModel):
    subscription_ids: list[str] = Field(default_factory=list, description="Target subscriptions to sync.")
    factory_names: list[str] = Field(default_factory=list, description="Specific factory names to sync.")
    factory_resource_groups: dict[str, str] = Field(
        default_factory=dict,
        description="Mapping of factory_name → resource_group. Taken from POST /subscriptions/factories response.",
        json_schema_extra={"example": {"adf-watco-prod": "rg-data-platform-prod"}},
    )
    force_refresh: bool = Field(default=False, description="Re-download latest ARM metadata if True.")


class SyncResponse(BaseModel):
    status: str = "SUCCESS"
    synced_factories: list[str]
    total_pipelines: int
    total_activities: int
    total_datasets: int
    total_linked_services: int
    total_triggers: int
    last_refreshed_at: str


class FactorySummaryResponse(BaseModel):
    factory_name: str
    resource_group: str
    subscription_id: str
    location: str
    pipeline_count: int
    activity_count: int
    dataset_count: int
    linked_service_count: int
    trigger_count: int
    data_flow_count: int
    global_parameters_count: int
    last_refreshed_at: Optional[str] = None


class PipelineDetailResponse(BaseModel):
    name: str
    folder: Optional[str] = None
    description: Optional[str] = None
    activities: list[dict[str, Any]]
    parameters: dict[str, Any] = Field(default_factory=dict)
    variables: dict[str, Any] = Field(default_factory=dict)
    annotations: list[str] = Field(default_factory=list)
    referenced_datasets: list[str] = Field(default_factory=list)
    referenced_linked_services: list[str] = Field(default_factory=list)
    child_pipelines: list[str] = Field(default_factory=list)
    trigger_names: list[str] = Field(default_factory=list)


class DatasetSummaryResponse(BaseModel):
    name: str
    type: str
    linked_service: str
    folder: Optional[str] = None
    is_onprem: bool = False
    schema_fields_count: int = 0
    consumed_by_pipelines: list[str] = Field(default_factory=list)
    produced_by_pipelines: list[str] = Field(default_factory=list)


# --- Graph & Lineage Models ---

class TopologyResponse(BaseModel):
    total_nodes: int
    total_edges: int
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]


class LineageResponse(BaseModel):
    target_asset: str
    upstream_dependencies: list[str]
    downstream_consumers: list[str]
    depth: int = 2


class SubgraphResponse(BaseModel):
    target_asset: str
    k_hops: int
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]


class DeletionSimulationRequest(BaseModel):
    target_asset: str


class DeletionSimulationResponse(BaseModel):
    target_asset: str
    risk_score: int
    risk_rating: str
    broken_readers: list[str]
    broken_writers: list[str]
    affected_pipelines: list[str]
    remediation_steps: list[str]
    last_refreshed_at: Optional[str] = None


# --- Audit & Security Models ---

class TechnicalDebtReportResponse(BaseModel):
    orphan_pipelines: list[str]
    zero_retry_activities: list[dict[str, Any]]
    total_orphan_count: int
    total_zero_retry_count: int


class ConcurrencyHeatmapResponse(BaseModel):
    peak_hour: str
    peak_concurrency_count: int
    hourly_schedule_map: dict[str, list[str]]


class SaaSVendorMapResponse(BaseModel):
    saas_endpoints: dict[str, list[str]]
    total_vendors: int


class ParameterAuditResponse(BaseModel):
    global_parameters: dict[str, Any]
    pipeline_parameters_summary: dict[str, int]


# --- AI Reasoning Models ---

class AIAskRequest(BaseModel):
    query: str
    factory_name: Optional[str] = None
    model: str = "azure-openai"
    session_id: Optional[str] = None


class ChatStreamRequest(BaseModel):
    query: str
    factory_name: Optional[str] = None
    model: str = "nvidia-nim"
    session_id: Optional[str] = None


class AIAskResponse(BaseModel):
    query: str
    detected_intent: str
    target_asset: Optional[str] = None
    grounding_score: float = 100.0
    response_markdown: str
    latency_ms: float
    cited_assets: list[str] = Field(default_factory=list)


class CodeGenRequest(BaseModel):
    pipeline_name: str
    target_framework: str = "pyspark"


class CodeGenResponse(BaseModel):
    pipeline_name: str
    target_framework: str
    generated_code: str
    explanation: str


# --- Teams Bot Models ---

class TeamsWebhookRequest(BaseModel):
    type: str = "message"
    text: str = ""
    channel_data: dict[str, Any] = Field(default_factory=dict)
    value: dict[str, Any] = Field(default_factory=dict)


class TeamsCardResponse(BaseModel):
    type: str = "AdaptiveCard"
    version: str = "1.4"
    card: dict[str, Any]
