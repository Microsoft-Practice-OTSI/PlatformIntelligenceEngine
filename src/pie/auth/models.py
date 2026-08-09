"""Data models for Azure Authentication, Entra ID, and RBAC Discovery."""

from datetime import datetime
from pydantic import BaseModel, Field


class TenantContext(BaseModel):
    """Microsoft Entra ID Tenant Context."""
    tenant_id: str = Field(description="Directory / Tenant ID")
    display_name: str | None = Field(default=None, description="Tenant Display Name")
    default_domain: str | None = Field(default=None, description="Default domain name")


class SubscriptionMetadata(BaseModel):
    """Metadata representing an accessible Azure Subscription under Reader role."""
    id: str = Field(description="Fully qualified ARM resource ID")
    subscription_id: str = Field(description="GUID subscription ID")
    display_name: str = Field(description="Human readable subscription name")
    state: str = Field(default="Enabled", description="Subscription lifecycle state (Enabled, Suspended)")
    tenant_id: str | None = Field(default=None, description="Associated Tenant ID")
    tags: dict[str, str] = Field(default_factory=dict, description="Resource tags assigned to subscription")


class DataFactoryBrief(BaseModel):
    """Brief metadata of a Data Factory discovered inside a Resource Group."""
    id: str
    name: str
    location: str
    resource_group: str
    subscription_id: str
    public_network_access: str | None = None
    tags: dict[str, str] = Field(default_factory=dict)


class ResourceGroupMetadata(BaseModel):
    """Metadata representing an Azure Resource Group discovered under Reader role."""
    id: str = Field(description="Fully qualified ARM ID")
    name: str = Field(description="Resource Group name")
    location: str = Field(description="Azure Region")
    subscription_id: str = Field(description="Parent Subscription ID")
    provisioning_state: str = Field(default="Succeeded")
    tags: dict[str, str] = Field(default_factory=dict)
    data_factories: list[DataFactoryBrief] = Field(
        default_factory=list,
        description="ADF instances detected within this Resource Group",
    )


class AuthContext(BaseModel):
    """Summary of the active authenticated session."""
    auth_mode: str
    tenant_id: str | None = None
    authenticated_at: datetime = Field(default_factory=datetime.utcnow)
    token_acquired: bool = True
    reader_role_validated: bool = True
    principal_type: str = Field(default="User / Interactive", description="User, ServicePrincipal, or ManagedIdentity")


class Spike1Result(BaseModel):
    """Standardized output schema for Spike 1 (Azure Auth & RBAC Discovery)."""
    spike_id: str = "spike_1_azure_auth_rbac"
    status: str = "SUCCESS"
    executed_at: datetime = Field(default_factory=datetime.utcnow)
    auth_context: AuthContext
    subscriptions: list[SubscriptionMetadata]
    resource_groups: list[ResourceGroupMetadata]
    data_factories_discovered: list[DataFactoryBrief]
    summary: dict[str, int] = Field(
        description="Summary counts of discovered infrastructure",
    )
