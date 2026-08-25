"""Knowledge Graph, Lineage Traversal, What-If Deletion Simulator, and Change Impact Analysis endpoints."""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query

from pie.api.models import (
    TopologyResponse,
    LineageResponse,
    SubgraphResponse,
    DeletionSimulationRequest,
    DeletionSimulationResponse,
    ChangeImpactRequest,
    ChangeImpactResponse,
    ImpactFindingResponse,
    RiskAssessmentResponse,
)
from pie.api.dependencies import (
    get_current_tenant_id,
    get_graph_repository,
    get_traversal_service,
    get_deletion_simulator,
    get_change_impact_engine,
    get_meta_repository,
)
from pie.graph.builder import KnowledgeGraph
from pie.graph.traversal import GraphTraversalService
from pie.graph.deletion_simulator import AssetDeletionSimulator
from pie.graph.change_impact_engine import ChangeImpactEngine
from pie.graph.models import ChangeType
from pie.discovery.repository import MetadataRepository

router = APIRouter(prefix="/graph", tags=["Knowledge Graph & Lineage Traversal"])


@router.get("/topology", response_model=TopologyResponse)
async def get_graph_topology(
    graph: KnowledgeGraph = Depends(get_graph_repository),
) -> TopologyResponse:
    """Retrieve full in-memory graph topology for interactive visual rendering."""
    nodes = [
        {
            "id": n.id,
            "name": n.name,
            "type": n.type.value,
            "folder": n.folder,
            "properties": n.properties,
        }
        for n in graph.nodes.values()
    ]
    edges = [
        {
            "source_id": e.source_id,
            "target_id": e.target_id,
            "type": e.type.value,
            "properties": e.properties,
        }
        for e in graph.edges
    ]
    return TopologyResponse(
        total_nodes=len(nodes),
        total_edges=len(edges),
        nodes=nodes,
        edges=edges,
    )


@router.get("/lineage/{asset_name}", response_model=LineageResponse)
async def get_asset_lineage(
    asset_name: str,
    traversal: GraphTraversalService = Depends(get_traversal_service),
) -> LineageResponse:
    """Compute upstream lineage dependencies and downstream blast radius for a target asset."""
    upstreams = traversal.get_upstream_dependencies(asset_name)
    downstreams = traversal.get_downstream_blast_radius(asset_name)

    return LineageResponse(
        target_asset=asset_name,
        upstream_dependencies=upstreams,
        downstream_consumers=downstreams,
        depth=2,
    )


@router.get("/subgraph/{asset_name}", response_model=SubgraphResponse)
async def get_k_hop_subgraph(
    asset_name: str,
    k_hops: int = Query(default=2, ge=1, le=5),
    traversal: GraphTraversalService = Depends(get_traversal_service),
) -> SubgraphResponse:
    """Extract a localized k-hop directed subgraph around a target asset."""
    subgraph = traversal.get_k_hop_subgraph(asset_name, k_hops=k_hops)

    nodes = [
        {
            "id": n.id,
            "name": n.name,
            "type": n.type.value,
            "folder": n.folder,
        }
        for n in subgraph.nodes.values()
    ]
    edges = [
        {
            "source_id": e.source_id,
            "target_id": e.target_id,
            "type": e.type.value,
        }
        for e in subgraph.edges
    ]
    return SubgraphResponse(
        target_asset=asset_name,
        k_hops=k_hops,
        nodes=nodes,
        edges=edges,
    )


@router.post("/deletion-simulation", response_model=DeletionSimulationResponse)
async def simulate_asset_deletion(
    payload: DeletionSimulationRequest,
    simulator: AssetDeletionSimulator = Depends(get_deletion_simulator),
    tenant_id: str = Depends(get_current_tenant_id),
    repo: MetadataRepository = Depends(get_meta_repository),
) -> DeletionSimulationResponse:
    """Execute what-if deletion simulator, identifying broken entities, impacted pipelines, and remediation steps."""
    report = simulator.simulate_dataset_deletion(payload.target_asset)
    refreshed_at = repo.get_last_refreshed_at("adf-sales-enterprise-prod", tenant_id=tenant_id)
    risk_assessment = report.get("risk_assessment", {})
    immediate = report.get("immediate_failures", {})
    readers = [r.get("activity", "") if isinstance(r, dict) else str(r) for r in immediate.get("broken_readers", [])]
    writers = [w.get("activity", "") if isinstance(w, dict) else str(w) for r in immediate.get("broken_writers", [])]

    return DeletionSimulationResponse(
        target_asset=report.get("target_dataset", payload.target_asset),
        risk_score=risk_assessment.get("risk_score", 0),
        risk_rating=str(risk_assessment.get("risk_level", "LOW")).upper(),
        broken_readers=readers,
        broken_writers=writers,
        affected_pipelines=immediate.get("impacted_pipelines", []),
        remediation_steps=report.get("remediation_plan", []),
        last_refreshed_at=refreshed_at,
    )


@router.post("/change-impact", response_model=ChangeImpactResponse)
async def analyze_change_impact(
    payload: ChangeImpactRequest,
    engine: ChangeImpactEngine = Depends(get_change_impact_engine),
) -> ChangeImpactResponse:
    """Execute a full Change Impact Analysis for any supported ADF object type and change scenario."""
    # Map string change_type to enum
    try:
        change_type = ChangeType(payload.change_type.upper())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported change_type '{payload.change_type}'. "
                   f"Valid types: {', '.join(ct.value for ct in ChangeType)}",
        )

    from pie.graph.models import NodeType
    object_type = None
    if payload.object_type:
        try:
            object_type = NodeType(payload.object_type)
        except ValueError:
            pass

    from pie.graph.models import ChangeRequest
    request = ChangeRequest(
        target_object=payload.target_asset,
        object_type=object_type,
        parent_context=payload.parent_context,
        change_type=change_type,
        requested_action=f"What happens if I {payload.change_type.lower()} {payload.target_asset}?",
        scope="ADF Factory",
    )

    result = engine.analyze(request)

    return ChangeImpactResponse(
        target_name=result.target.get("name", payload.target_asset),
        target_type=result.target.get("objectType", "Unknown"),
        change_type=change_type.value,
        risk=RiskAssessmentResponse(
            level=result.risk.level,
            score=result.risk.score,
            reasons=result.risk.reasons,
            scopes=[s.value for s in result.risk.scopes],
        ),
        direct_impacts=[
            ImpactFindingResponse(
                asset=f.asset,
                asset_type=f.asset_type.value,
                impact_type=f.impact_type,
                relationship=f.relationship.value,
                reason=f.reason,
                evidence=f.evidence,
                confidence=f.confidence.value,
                severity=f.severity,
            )
            for f in result.direct_impacts
        ],
        indirect_impacts=[
            ImpactFindingResponse(
                asset=f.asset,
                asset_type=f.asset_type.value,
                impact_type=f.impact_type,
                relationship=f.relationship.value,
                reason=f.reason,
                evidence=f.evidence,
                confidence=f.confidence.value,
                severity=f.severity,
            )
            for f in result.indirect_impacts
        ],
        affected_pipelines=result.affected_pipelines,
        affected_assets=result.affected_assets,
        external_systems=result.external_systems,
        impact_chain=result.impact_chain,
        confidence=result.confidence.value,
        potential_consequences=result.potential_consequences,
        recommendation=result.recommendation,
        summary_md=result.summary_md,
        disambiguation=result.disambiguation,
    )

