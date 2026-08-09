"""Domain models for PIE Context Builder, Subgraph Extractor, and Token Budgeting."""

from typing import Any
from datetime import datetime
from pydantic import BaseModel, Field


class TokenBudget(BaseModel):
    """Token budget configuration and allocation policy."""
    max_tokens: int = Field(default=4000, description="Maximum total tokens allowed in context payload")
    flow_allocation_pct: float = Field(default=0.40, description="40% budget for Activity flow & operations")
    schema_allocation_pct: float = Field(default=0.30, description="30% budget for Dataset schemas & tables")
    lineage_allocation_pct: float = Field(default=0.20, description="20% budget for Upstream/downstream lineage")
    service_allocation_pct: float = Field(default=0.10, description="10% budget for Linked services & credentials")


class ContextPackage(BaseModel):
    """Structured, token-budgeted, LLM-ready context payload for AI reasoning."""
    target_asset_name: str
    target_asset_type: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    token_budget: int
    raw_uncompressed_tokens: int
    compressed_context_tokens: int
    compression_ratio: float = Field(description="Percentage token reduction (e.g. 96.5%)")
    executive_summary_md: str
    activity_flow_md: str
    dataset_schemas_md: str
    lineage_and_blast_radius_md: str
    linked_services_md: str
    full_prompt_payload_md: str
    metadata_summary: dict[str, Any] = Field(default_factory=dict)


class Spike4Result(BaseModel):
    """Standardized result schema for Spike 4."""
    spike_id: str = "spike_4_context_builder_and_token_budgeting"
    status: str = "SUCCESS"
    executed_at: datetime = Field(default_factory=datetime.utcnow)
    target_asset: str
    budget_configured: int
    raw_tokens: int
    compressed_tokens: int
    token_savings_pct: float
    context_package: ContextPackage
