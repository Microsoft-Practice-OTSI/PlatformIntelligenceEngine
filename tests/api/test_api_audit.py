"""Integration tests for Technical Debt, Governance, and SaaS Vendor Audit routes."""

from starlette.testclient import TestClient


def test_audit_technical_debt(client: TestClient):
    """Verify technical debt detection identifies orphan pipelines and fragile activities."""
    resp = client.get("/api/v1/audit/technical-debt")
    assert resp.status_code == 200
    data = resp.json()
    assert "orphan_pipelines" in data
    assert "zero_retry_activities" in data
    assert data["total_orphan_count"] >= 1
    assert data["total_zero_retry_count"] >= 1


def test_audit_concurrency_heatmap(client: TestClient):
    """Verify schedule collision analysis identifies peak batch windows."""
    resp = client.get("/api/v1/audit/concurrency-heatmap")
    assert resp.status_code == 200
    data = resp.json()
    assert data["peak_hour"] is not None
    assert data["peak_concurrency_count"] >= 1
    assert len(data["hourly_schedule_map"]) >= 1


def test_audit_saas_vendors(client: TestClient):
    """Verify external SaaS vendor mapping identifies Azure Databricks, Dynamics, etc."""
    resp = client.get("/api/v1/audit/saas-vendors")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_vendors"] >= 1
    assert "Azure Databricks (Lakehouse / Delta)" in data["saas_endpoints"] or "On-Premises SQL / File Stores" in data["saas_endpoints"]


def test_audit_parameters(client: TestClient):
    """Verify factory global parameters and pipeline parameter distribution."""
    resp = client.get("/api/v1/audit/parameters")
    assert resp.status_code == 200
    data = resp.json()
    assert "global_parameters" in data
    assert "pipeline_parameters_summary" in data
