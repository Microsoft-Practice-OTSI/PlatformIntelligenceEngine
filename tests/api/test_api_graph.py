"""Integration tests for Knowledge Graph, Lineage Traversal, and Deletion Simulator routes."""

from starlette.testclient import TestClient


def test_graph_topology(client: TestClient):
    """Verify full in-memory graph topology extraction."""
    resp = client.get("/api/v1/graph/topology")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_nodes"] >= 10
    assert data["total_edges"] >= 10
    assert any(n["name"] == "PL_Customer_Daily_Ingestion" for n in data["nodes"])


def test_asset_lineage(client: TestClient):
    """Verify upstream lineage and downstream blast radius traversal."""
    resp = client.get("/api/v1/graph/lineage/DS_Blob_Customer_Raw_CSV")
    assert resp.status_code == 200
    data = resp.json()
    assert data["target_asset"] == "DS_Blob_Customer_Raw_CSV"
    assert "PL_Customer_Daily_Ingestion" in data["downstream_consumers"]


def test_k_hop_subgraph(client: TestClient):
    """Verify localized k-hop directed subgraph extraction."""
    resp = client.get("/api/v1/graph/subgraph/PL_Customer_Daily_Ingestion?k_hops=2")
    assert resp.status_code == 200
    data = resp.json()
    assert data["target_asset"] == "PL_Customer_Daily_Ingestion"
    assert data["k_hops"] == 2
    assert len(data["nodes"]) >= 3


def test_deletion_simulation(client: TestClient):
    """Verify what-if deletion simulation identifies broken readers and affected pipelines."""
    resp = client.post(
        "/api/v1/graph/deletion-simulation",
        json={"target_asset": "DS_Blob_Customer_Raw_CSV"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["target_asset"] == "DS_Blob_Customer_Raw_CSV"
    assert data["risk_score"] >= 70
    assert data["risk_rating"] in ["CRITICAL", "HIGH", "MODERATE", "MEDIUM"]
    assert "PL_Customer_Daily_Ingestion" in data["affected_pipelines"]
    assert len(data["remediation_steps"]) >= 1
