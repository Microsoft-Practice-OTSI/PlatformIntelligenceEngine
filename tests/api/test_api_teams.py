"""Integration tests for Microsoft Teams Bot webhook and Adaptive Cards."""

from starlette.testclient import TestClient


def test_teams_webhook_deletion_trigger(client: TestClient):
    """Verify Teams Bot webhook generates Adaptive Card for deletion query."""
    resp = client.post(
        "/api/v1/teams/webhook",
        json={"type": "message", "text": "What if I delete DS_Blob_Customer_Raw_CSV?"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["type"] == "message"
    assert len(data["attachments"]) >= 1
    att = data["attachments"][0]
    assert att["contentType"] == "application/vnd.microsoft.card.adaptive"
    card = att["content"]
    assert card["type"] == "AdaptiveCard"
    assert card["version"] == "1.4"


def test_teams_cards_deletion_impact(client: TestClient):
    """Verify dedicated Adaptive Card generation endpoint conforms to Schema 1.4."""
    resp = client.post(
        "/api/v1/teams/cards/deletion-impact",
        json={"target_asset": "DS_Blob_Customer_Raw_CSV"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["type"] == "AdaptiveCard"
    assert data["version"] == "1.4"
    card = data["card"]
    assert card["type"] == "AdaptiveCard"
    assert len(card["body"]) >= 2
    assert len(card["actions"]) >= 1
    assert card["actions"][0]["type"] == "Action.OpenUrl"
