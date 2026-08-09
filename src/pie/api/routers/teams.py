"""Microsoft Teams Bot webhook and interactive Adaptive Card endpoints."""

from fastapi import APIRouter, Depends
from pie.api.models import TeamsWebhookRequest, TeamsCardResponse, DeletionSimulationRequest
from pie.api.dependencies import get_deletion_simulator, get_meta_repository, get_current_tenant_id
from pie.teams.adaptive_cards import TeamsAdaptiveCardBuilder
from pie.graph.deletion_simulator import AssetDeletionSimulator
from pie.discovery.repository import MetadataRepository

router = APIRouter(prefix="/teams", tags=["Microsoft Teams Bot & Webhooks"])


@router.post("/webhook", response_model=dict)
async def handle_teams_webhook(
    payload: TeamsWebhookRequest,
    simulator: AssetDeletionSimulator = Depends(get_deletion_simulator),
) -> dict:
    """Handle incoming Bot Framework webhook from Microsoft Teams DevOps channels."""
    text = payload.text.lower()

    if "delete" in text or "what if" in text:
        target = "DS_Blob_Customer_Raw_CSV" if ("csv" in text or "blob" in text) else "DS_AzureSql_CustomerStaging"
        report = simulator.simulate_dataset_deletion(target)
        risk_assessment = report.get("risk_assessment", {})
        immediate = report.get("immediate_failures", {})
        readers = [r.get("activity", "") if isinstance(r, dict) else str(r) for r in immediate.get("broken_readers", [])]
        writers = [w.get("activity", "") if isinstance(w, dict) else str(w) for r in immediate.get("broken_writers", [])]
        card = TeamsAdaptiveCardBuilder.build_deletion_risk_card(
            target_asset=report.get("target_dataset", target),
            risk_rating=str(risk_assessment.get("risk_level", "LOW")),
            risk_score=risk_assessment.get("risk_score", 0),
            broken_readers=readers,
            broken_writers=writers,
            affected_pipelines=immediate.get("impacted_pipelines", []),
        )
        return {
            "type": "message",
            "attachments": [
                {
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "content": card,
                }
            ],
        }

    # Default welcome / help card
    summary_card = TeamsAdaptiveCardBuilder.build_architecture_summary_card(
        pipeline_name="PL_Customer_Daily_Ingestion",
        activity_count=2,
        saas_vendors=["Azure SQL", "On-Prem File Server"],
        schedule="Every Day at Midnight (00:00 UTC)",
    )
    return {
        "type": "message",
        "attachments": [
            {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": summary_card,
            }
        ],
    }


@router.post("/cards/deletion-impact", response_model=TeamsCardResponse)
async def generate_deletion_impact_card(
    payload: DeletionSimulationRequest,
    simulator: AssetDeletionSimulator = Depends(get_deletion_simulator),
    tenant_id: str = Depends(get_current_tenant_id),
    repo: MetadataRepository = Depends(get_meta_repository),
) -> TeamsCardResponse:
    """Generate rich Adaptive Card v1.4 JSON payload for deletion risk assessment."""
    report = simulator.simulate_dataset_deletion(payload.target_asset)
    refreshed_at = repo.get_last_refreshed_at("adf-sales-enterprise-prod", tenant_id=tenant_id)
    risk_assessment = report.get("risk_assessment", {})
    immediate = report.get("immediate_failures", {})
    readers = [r.get("activity", "") if isinstance(r, dict) else str(r) for r in immediate.get("broken_readers", [])]
    writers = [w.get("activity", "") if isinstance(w, dict) else str(w) for r in immediate.get("broken_writers", [])]
    card = TeamsAdaptiveCardBuilder.build_deletion_risk_card(
        target_asset=report.get("target_dataset", payload.target_asset),
        risk_rating=str(risk_assessment.get("risk_level", "LOW")),
        risk_score=risk_assessment.get("risk_score", 0),
        broken_readers=readers,
        broken_writers=writers,
        affected_pipelines=immediate.get("impacted_pipelines", []),
        last_refreshed_at=refreshed_at,
    )
    return TeamsCardResponse(card=card)

