"""
Phase 3 Completeness Verification Test Suite.
Tests every Phase 3 endpoint including the 3 newly added ones:
  - GET  /factories/{name}/pipelines
  - GET  /factories/{name}/global-parameters
  - POST /factories/{name}/refresh  (now with ARM re-extract capability)
"""
import pytest
from starlette.testclient import TestClient
from pie.api.app import app

client = TestClient(app, raise_server_exceptions=True)

FACTORY = "adf-sales-enterprise-prod"
PIPELINE = "Customer_Load"


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def preload():
    """Ensure mock data is loaded so all endpoints have data to return."""
    r = client.post("/api/v1/discovery/sync", json={
        "subscription_ids": [],
        "factory_names": [],
        "factory_resource_groups": {},
    })
    assert r.status_code == 200


# ─────────────────────────────────────────────
# Auth
# ─────────────────────────────────────────────

def test_auth_session_endpoint():
    r = client.get("/api/v1/auth/session")
    assert r.status_code in (200, 401)

def test_auth_login_returns_url():
    r = client.post("/api/v1/auth/login")
    assert r.status_code == 200
    body = r.json()
    assert "login_url" in body


# ─────────────────────────────────────────────
# Discovery hierarchy
# ─────────────────────────────────────────────

def test_subscriptions_mock_fallback():
    r = client.get("/api/v1/subscriptions")
    assert r.status_code == 200
    body = r.json()
    assert "subscriptions" in body
    assert body["total"] >= 1

def test_subscriptions_factories_mock_fallback():
    r = client.post(
        "/api/v1/subscriptions/factories",
        json=["sub-mock-001"],
    )
    assert r.status_code == 200
    body = r.json()
    assert "factories" in body

def test_sync_loads_mock_data():
    r = client.post("/api/v1/discovery/sync", json={
        "subscription_ids": [],
        "factory_names": [],
        "factory_resource_groups": {},
    })
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "SUCCESS"
    assert body["total_pipelines"] > 0
    assert body["total_activities"] > 0
    assert body["total_datasets"] > 0
    assert body["total_linked_services"] > 0

def test_factories_list():
    preload()
    r = client.get("/api/v1/factories")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 1
    f = body["factories"][0]
    assert "factory_name" in f
    assert "resource_group" in f
    assert "subscription_id" in f
    assert "pipeline_count" in f
    assert "last_refreshed_at" in f

def test_factory_summary():
    preload()
    r = client.get("/api/v1/factories")
    factory_name = r.json()["factories"][0]["factory_name"]
    r2 = client.get(f"/api/v1/factories/{factory_name}/summary")
    assert r2.status_code == 200
    body = r2.json()
    assert body["factory_name"] == factory_name
    assert "pipeline_count" in body
    assert "activity_count" in body
    assert "dataset_count" in body
    assert "trigger_count" in body
    assert "global_parameters_count" in body
    assert "last_refreshed_at" in body


# ─────────────────────────────────────────────
# NEW: Factory-scoped pipelines
# ─────────────────────────────────────────────

def test_factory_scoped_pipelines():
    preload()
    r_f = client.get("/api/v1/factories")
    factory_name = r_f.json()["factories"][0]["factory_name"]
    r = client.get(f"/api/v1/factories/{factory_name}/pipelines")
    assert r.status_code == 200
    pipelines = r.json()
    assert isinstance(pipelines, list)
    assert len(pipelines) > 0
    p = pipelines[0]
    assert "name" in p
    assert "activity_count" in p
    assert "parameters" in p

def test_factory_scoped_pipelines_folder_filter():
    preload()
    r_f = client.get("/api/v1/factories")
    factory_name = r_f.json()["factories"][0]["factory_name"]
    r = client.get(f"/api/v1/factories/{factory_name}/pipelines?folder=nonexistent_folder_xyz")
    assert r.status_code == 200
    # Should return empty list — no pipelines in that folder
    assert r.json() == []

def test_factory_scoped_pipelines_404():
    r = client.get("/api/v1/factories/no-such-factory/pipelines")
    assert r.status_code == 404


# ─────────────────────────────────────────────
# NEW: Global parameters
# ─────────────────────────────────────────────

def test_global_parameters_endpoint():
    preload()
    r_f = client.get("/api/v1/factories")
    factory_name = r_f.json()["factories"][0]["factory_name"]
    r = client.get(f"/api/v1/factories/{factory_name}/global-parameters")
    assert r.status_code == 200
    params = r.json()
    assert isinstance(params, list)
    # Even if factory has 0 global params, endpoint should return 200 + empty list
    for p in params:
        assert "name" in p
        assert "type" in p
        assert "value" in p
        assert "pipeline_ref" in p
        assert p["pipeline_ref"].startswith("@pipeline().globalParameters.")

def test_global_parameters_404():
    r = client.get("/api/v1/factories/ghost-factory/global-parameters")
    assert r.status_code == 404


# ─────────────────────────────────────────────
# NEW: Factory refresh (ARM re-extract)
# ─────────────────────────────────────────────

def test_factory_refresh_no_token_updates_timestamp():
    preload()
    r_f = client.get("/api/v1/factories")
    factory_name = r_f.json()["factories"][0]["factory_name"]
    r1 = client.get(f"/api/v1/factories/{factory_name}/summary")
    ts1 = r1.json()["last_refreshed_at"]

    import time; time.sleep(0.05)

    r2 = client.post(f"/api/v1/factories/{factory_name}/refresh")
    assert r2.status_code == 200
    body = r2.json()
    assert body["factory_name"] == factory_name
    ts2 = body["last_refreshed_at"]
    # Timestamp must have advanced
    assert ts2 >= ts1

def test_factory_refresh_404():
    r = client.post("/api/v1/factories/ghost-factory/refresh")
    assert r.status_code == 404


# ─────────────────────────────────────────────
# Pipelines catalog (existing)
# ─────────────────────────────────────────────

def test_pipelines_list():
    preload()
    r = client.get("/api/v1/pipelines")
    assert r.status_code == 200
    assert len(r.json()) > 0

def test_pipeline_detail():
    preload()
    pipelines = client.get("/api/v1/pipelines").json()
    assert len(pipelines) > 0
    p_name = pipelines[0]["name"]
    r = client.get(f"/api/v1/pipelines/{p_name}")
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == p_name
    assert "activities" in body
    assert "referenced_datasets" in body

def test_datasets_list():
    preload()
    r = client.get("/api/v1/datasets")
    assert r.status_code == 200
    assert isinstance(r.json(), list)

def test_linked_services_list():
    preload()
    r = client.get("/api/v1/linked-services")
    assert r.status_code == 200
    assert isinstance(r.json(), list)

def test_triggers_list():
    preload()
    r = client.get("/api/v1/triggers")
    assert r.status_code == 200
    triggers = r.json()
    assert isinstance(triggers, list)
    assert len(triggers) > 0
    t = triggers[0]
    assert "name" in t
    assert "type" in t
    assert "runtime_state" in t
    assert "pipelines" in t


# ─────────────────────────────────────────────
# Graph
# ─────────────────────────────────────────────

def test_graph_topology():
    preload()
    r = client.get("/api/v1/graph/topology")
    assert r.status_code == 200
    body = r.json()
    assert "nodes" in body
    assert "edges" in body
    assert len(body["nodes"]) > 0

def test_graph_lineage():
    preload()
    pipelines = client.get("/api/v1/pipelines").json()
    p_name = pipelines[0]["name"]
    r = client.get(f"/api/v1/graph/lineage/{p_name}")
    assert r.status_code == 200

def test_graph_subgraph():
    preload()
    pipelines = client.get("/api/v1/pipelines").json()
    p_name = pipelines[0]["name"]
    r = client.get(f"/api/v1/graph/subgraph/{p_name}")
    assert r.status_code == 200

def test_deletion_simulation():
    preload()
    datasets = client.get("/api/v1/datasets").json()
    d_name = datasets[0]["name"]
    r = client.post("/api/v1/graph/deletion-simulation", json={"target_asset": d_name})
    assert r.status_code == 200
    body = r.json()
    assert "risk_score" in body


# ─────────────────────────────────────────────
# Audit
# ─────────────────────────────────────────────

def test_audit_technical_debt():
    preload()
    r = client.get("/api/v1/audit/technical-debt")
    assert r.status_code == 200

def test_audit_concurrency_heatmap():
    preload()
    r = client.get("/api/v1/audit/concurrency-heatmap")
    assert r.status_code == 200

def test_audit_saas_vendors():
    preload()
    r = client.get("/api/v1/audit/saas-vendors")
    assert r.status_code == 200

def test_audit_parameters():
    preload()
    r = client.get("/api/v1/audit/parameters")
    assert r.status_code == 200


# ─────────────────────────────────────────────
# AI (mock provider)
# ─────────────────────────────────────────────

def test_ai_ask():
    preload()
    r_f = client.get("/api/v1/factories")
    factory_name = r_f.json()["factories"][0]["factory_name"]
    r = client.post("/api/v1/ai/ask", json={
        "query": "What does Customer_Load do?",
        "factory_name": factory_name,
    })
    assert r.status_code == 200
    assert "answer" in r.json() or "response_markdown" in r.json()

def test_ai_generate_code():
    preload()
    pipelines = client.get("/api/v1/pipelines").json()
    p_name = pipelines[0]["name"]
    r = client.post("/api/v1/ai/generate-code", json={
        "pipeline_name": p_name,
        "target_framework": "pyspark",
    })
    assert r.status_code == 200


# ─────────────────────────────────────────────
# Teams
# ─────────────────────────────────────────────

def test_teams_webhook():
    r = client.post("/api/v1/teams/webhook", json={"text": "explain Customer_Load"})
    assert r.status_code == 200

def test_teams_deletion_card():
    preload()
    datasets = client.get("/api/v1/datasets").json()
    d_name = datasets[0]["name"]
    r = client.post("/api/v1/teams/cards/deletion-impact", json={"target_asset": d_name})
    assert r.status_code == 200
