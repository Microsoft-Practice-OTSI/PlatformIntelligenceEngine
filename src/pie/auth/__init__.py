"""Azure Authentication and RBAC Discovery module for PIE."""

from pie.auth.credentials import CredentialFactory, MockTokenCredential
from pie.auth.rbac_discovery import AzureRbacDiscovery
from pie.auth.token_manager import EntraTokenManager, BearerTokenCredential
from pie.auth.session_store import SessionStore, PieSession, get_session_store
from pie.auth.models import (
    TenantContext,
    SubscriptionMetadata,
    ResourceGroupMetadata,
    DataFactoryBrief,
    AuthContext,
    Spike1Result,
)

__all__ = [
    "CredentialFactory",
    "MockTokenCredential",
    "AzureRbacDiscovery",
    "EntraTokenManager",
    "BearerTokenCredential",
    "TenantContext",
    "SubscriptionMetadata",
    "ResourceGroupMetadata",
    "DataFactoryBrief",
    "AuthContext",
    "Spike1Result",
    "SessionStore",
    "PieSession",
    "get_session_store",
]
