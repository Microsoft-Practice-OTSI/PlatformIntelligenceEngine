"""Security governance, SaaS vendor mapping, and technical debt auditing endpoints."""

from fastapi import APIRouter, Depends
from pie.api.models import (
    TechnicalDebtReportResponse,
    ConcurrencyHeatmapResponse,
    SaaSVendorMapResponse,
    ParameterAuditResponse,
)
from pie.api.dependencies import get_audit_engine, get_current_tenant_id, get_meta_repository
from pie.graph.audit_engine import AssetAuditEngine
from pie.discovery.repository import MetadataRepository

router = APIRouter(prefix="/audit", tags=["Technical Debt & Governance Auditing"])


@router.get("/technical-debt", response_model=TechnicalDebtReportResponse)
async def get_technical_debt_report(
    auditor: AssetAuditEngine = Depends(get_audit_engine),
) -> TechnicalDebtReportResponse:
    """Detect orphan unreferenced pipelines and fragile zero-retry activities."""
    debt = auditor.audit_technical_debt()
    return TechnicalDebtReportResponse(
        orphan_pipelines=debt.orphan_pipelines,
        zero_retry_activities=debt.zero_retry_activities,
        total_orphan_count=debt.total_orphan_count,
        total_zero_retry_count=debt.total_zero_retry_count,
    )


@router.get("/concurrency-heatmap", response_model=ConcurrencyHeatmapResponse)
async def get_concurrency_heatmap(
    auditor: AssetAuditEngine = Depends(get_audit_engine),
) -> ConcurrencyHeatmapResponse:
    """Analyze trigger schedule collisions across batch execution windows."""
    heatmap = auditor.audit_schedule_concurrency()
    return ConcurrencyHeatmapResponse(
        peak_hour=heatmap.peak_hour,
        peak_concurrency_count=heatmap.peak_concurrency_count,
        hourly_schedule_map=heatmap.hourly_schedule_map,
    )


@router.get("/saas-vendors", response_model=SaaSVendorMapResponse)
async def get_saas_vendor_map(
    auditor: AssetAuditEngine = Depends(get_audit_engine),
) -> SaaSVendorMapResponse:
    """Map external enterprise SaaS vendors (SAP, Dynamics, Databricks, Coupa, RailCarRx)."""
    vendor_map = auditor.audit_saas_vendor_ecosystem()
    return SaaSVendorMapResponse(
        saas_endpoints=vendor_map,
        total_vendors=len(vendor_map),
    )


@router.get("/parameters", response_model=ParameterAuditResponse)
async def get_parameter_audit(
    tenant_id: str = Depends(get_current_tenant_id),
    repo: MetadataRepository = Depends(get_meta_repository),
) -> ParameterAuditResponse:
    """Audit factory-level global parameters and pipeline parameter distributions."""
    factories = repo.list_factories(tenant_id=tenant_id)
    global_params = {}
    pipe_params = {}

    for f in factories:
        global_params.update(f.global_parameters)
        for p in f.pipelines:
            pipe_params[p.name] = len(p.parameters)

    return ParameterAuditResponse(
        global_parameters=global_params,
        pipeline_parameters_summary=pipe_params,
    )
