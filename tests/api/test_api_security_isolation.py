"""Security and Multi-Tenant Data Isolation integration tests."""

from starlette.testclient import TestClient
from pie.discovery.repository import get_repository
from pie.discovery.models import FactoryMetadata


def test_tenant_data_isolation(client: TestClient):
    """Verify Tenant A cannot access Tenant B's factory or pipeline metadata."""
    repo = get_repository()
    
    # Store a private factory under Tenant-B
    private_factory = FactoryMetadata(
        factory_name="adf-confidential-tenant-b",
        resource_group="rg-tenant-b-private",
        subscription_id="sub-b-1111",
        location="eastus",
        pipelines=[],
        datasets=[],
        linked_services=[],
        triggers=[],
        data_flows=[],
        global_parameters={},
        summary={},
    )
    repo.save_factory(private_factory, tenant_id="tenant-b-secret", subscription_id="sub-b-1111")

    # Request as Tenant A
    resp_tenant_a = client.get("/api/v1/factories", headers={"X-Tenant-ID": "tenant-a-public"})
    assert resp_tenant_a.status_code == 200
    factories_a = [f["factory_name"] for f in resp_tenant_a.json()["factories"]]
    assert "adf-confidential-tenant-b" not in factories_a

    # Request as Tenant B
    resp_tenant_b = client.get("/api/v1/factories", headers={"X-Tenant-ID": "tenant-b-secret"})
    assert resp_tenant_b.status_code == 200
    factories_b = [f["factory_name"] for f in resp_tenant_b.json()["factories"]]
    assert "adf-confidential-tenant-b" in factories_b


def test_last_refreshed_at_timestamp_integrity(client: TestClient):
    """Verify last_refreshed_at timestamp is captured and returned."""
    resp = client.get("/api/v1/factories", headers={"X-Tenant-ID": "default-tenant"})
    assert resp.status_code == 200
    factories = resp.json()["factories"]
    assert len(factories) >= 1
    assert factories[0]["last_refreshed_at"] is not None
