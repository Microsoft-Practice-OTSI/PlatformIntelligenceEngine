"""Integration tests for Discovery, Scoped Sync, and Asset Hierarchy routes."""

from starlette.testclient import TestClient


def test_list_subscriptions(client: TestClient):
    """Verify listing accessible Azure subscriptions."""
    resp = client.get("/api/v1/subscriptions")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert any(s["subscription_name"] == "Azure Enterprise - EIM Team" for s in data["subscriptions"])


def test_list_factories_in_subscriptions(client: TestClient):
    """Verify enumerating Data Factories for selected subscriptions."""
    sub_ids = ["60a58917-1a0c-4902-a24d-ab97dd75f0ab"]
    resp = client.post("/api/v1/subscriptions/factories", json=sub_ids)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert any(f["factory_name"] == "adf-sales-enterprise-prod" for f in data["factories"])


def test_sync_factories_with_timestamp(client: TestClient):
    """Verify scoped sync updates in-memory cache and records last_refreshed_at."""
    sync_payload = {
        "subscription_ids": ["60a58917-1a0c-4902-a24d-ab97dd75f0ab"],
        "factory_names": ["adf-sales-enterprise-prod"],
        "force_refresh": True,
    }
    resp = client.post("/api/v1/discovery/sync", json=sync_payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "SUCCESS"
    assert "adf-sales-enterprise-prod" in data["synced_factories"]
    assert data["total_pipelines"] >= 4
    assert data["last_refreshed_at"] is not None


def test_get_factory_summary_and_refresh(client: TestClient):
    """Verify factory summary metrics and explicit refresh endpoint."""
    resp = client.get("/api/v1/factories/adf-sales-enterprise-prod/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["factory_name"] == "adf-sales-enterprise-prod"
    assert data["pipeline_count"] >= 4
    assert data["activity_count"] >= 8
    assert data["last_refreshed_at"] is not None

    # Test explicit refresh endpoint
    refresh_resp = client.post("/api/v1/factories/adf-sales-enterprise-prod/refresh")
    assert refresh_resp.status_code == 200
    ref_data = refresh_resp.json()
    assert ref_data["last_refreshed_at"] is not None


def test_pipelines_catalog_and_detail(client: TestClient):
    """Verify pipeline catalog filtering and detailed 24-step breakdown."""
    resp = client.get("/api/v1/pipelines")
    assert resp.status_code == 200
    pipes = resp.json()
    assert len(pipes) >= 4
    assert any(p["name"] == "PL_Customer_Daily_Ingestion" for p in pipes)

    # Test detail breakdown
    detail_resp = client.get("/api/v1/pipelines/PL_Customer_Daily_Ingestion")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["name"] == "PL_Customer_Daily_Ingestion"
    assert len(detail["activities"]) >= 2
    assert "DS_Blob_Customer_Raw_CSV" in detail["referenced_datasets"]
    assert "LS_BlobStorage_RawDataLake" in detail["referenced_linked_services"]


def test_datasets_and_linked_services(client: TestClient):
    """Verify dataset search and linked services retrieval."""
    resp_ds = client.get("/api/v1/datasets")
    assert resp_ds.status_code == 200
    datasets = resp_ds.json()
    assert len(datasets) >= 5
    assert any(ds["name"] == "DS_Blob_Customer_Raw_CSV" for ds in datasets)

    resp_ls = client.get("/api/v1/linked-services")
    assert resp_ls.status_code == 200
    services = resp_ls.json()
    assert any(s["name"] == "LS_AzureSql_EnterpriseDWH" for s in services)

    resp_tr = client.get("/api/v1/triggers")
    assert resp_tr.status_code == 200
    triggers = resp_tr.json()
    assert any(t["name"] == "TR_Daily_Midnight_Schedule" for t in triggers)
