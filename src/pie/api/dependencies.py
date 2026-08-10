"""FastAPI dependency injection providers for tenant context, repository, and AI services."""

from typing import Optional
from fastapi import Header, Query, Depends, Request

from pie.core.config import get_settings, Settings
from pie.discovery.repository import MetadataRepository, get_repository
from pie.graph.builder import KnowledgeGraph, KnowledgeGraphBuilder
from pie.graph.traversal import GraphTraversalService
from pie.graph.storyteller import PipelineStoryteller
from pie.graph.deletion_simulator import AssetDeletionSimulator
from pie.graph.audit_engine import AssetAuditEngine
from pie.context.intent_builder import MultiIntentContextBuilder
from pie.ai.engine import PIEReasoningEngine
from pie.ai.chat_session import ChatSessionStore, get_chat_session_store as _get_chat_session_store



def get_current_tenant_id(
    x_tenant_id: Optional[str] = Header(default=None, alias="X-Tenant-ID"),
) -> str:
    """Extract and validate tenant ID from incoming header or default."""
    return (x_tenant_id or "default-tenant").strip().lower()


def get_current_subscription_id(
    x_subscription_id: Optional[str] = Header(default=None, alias="X-Subscription-ID"),
) -> Optional[str]:
    """Extract optional subscription scope from header."""
    return x_subscription_id.strip().lower() if x_subscription_id else None


def get_meta_repository() -> MetadataRepository:
    """Provide singleton MetadataRepository instance."""
    return get_repository()


def get_graph_repository(
    repo: MetadataRepository = Depends(get_meta_repository),
    tenant_id: str = Depends(get_current_tenant_id),
    subscription_id: Optional[str] = Depends(get_current_subscription_id),
) -> KnowledgeGraph:
    """Build or retrieve in-memory directed Knowledge Graph for the tenant."""
    factories = repo.list_factories(tenant_id=tenant_id, subscription_id=subscription_id)
    
    # Only use synced factories - no preload_defaults
    if factories:
        def _recency(f):
            return repo.get_last_refreshed_at(
                f.factory_name, subscription_id=f.subscription_id, tenant_id=tenant_id
            ) or ""

        # Prefer REAL (ARM-synced / cache-restored) factories over mock/demo ones,
        # then pick the most recently synced so demo data can never shadow real data.
        real = [f for f in factories if repo.get_provenance(
            f.factory_name, subscription_id=f.subscription_id, tenant_id=tenant_id
        ) in ("arm", "cache")]
        candidates = real or factories
        return KnowledgeGraphBuilder.build(max(candidates, key=_recency))
    
    # Return empty graph if no factories synced (user must sync first)
    return KnowledgeGraph(factory_name="empty")



def get_traversal_service(
    graph: KnowledgeGraph = Depends(get_graph_repository),
) -> GraphTraversalService:
    """Provide graph traversal service."""
    return GraphTraversalService(graph)


def get_storyteller_service(
    graph: KnowledgeGraph = Depends(get_graph_repository),
) -> PipelineStoryteller:
    """Provide pipeline execution storyteller service."""
    return PipelineStoryteller(graph)


def get_deletion_simulator(
    graph: KnowledgeGraph = Depends(get_graph_repository),
) -> AssetDeletionSimulator:
    """Provide what-if asset deletion simulator."""
    return AssetDeletionSimulator(graph)


def get_audit_engine(
    graph: KnowledgeGraph = Depends(get_graph_repository),
) -> AssetAuditEngine:
    """Provide enterprise security and governance audit engine."""
    return AssetAuditEngine(graph)


def get_context_builder(
    graph: KnowledgeGraph = Depends(get_graph_repository),
) -> MultiIntentContextBuilder:
    """Provide token-optimized context builder."""
    return MultiIntentContextBuilder(graph)


def get_reasoning_engine(
    graph: KnowledgeGraph = Depends(get_graph_repository),
) -> PIEReasoningEngine:
    """Provide unified PIE reasoning engine with provider routing."""
    return PIEReasoningEngine(graph=graph)


def get_chat_session_store() -> ChatSessionStore:
    """Provide the process-wide shared in-memory chat session store."""
    return _get_chat_session_store()

