"""Unit tests for Auth domain models and schema validation."""

import pytest
from datetime import datetime
from pie.auth.models import (
    TenantContext,
    SubscriptionMetadata,
    ResourceGroupMetadata,
    DataFactoryBrief,
    AuthContext,
    Spike1Result,
)
from spikes.spike_1_auth.mock_auth_fixture import get_mock_spike_1_result


def test_subscription_metadata_serialization():
    """Verify subscription model initialization and tags."""
    sub = SubscriptionMetadata(
        id="/subscriptions/sub-12345",
        subscription_id="sub-12345",
        display_name="Test Subscription",
        state="Enabled",
        tenant_id="tenant-xyz",
        tags={"Env": "Dev", "Owner": "DataPlatform"},
    )
    assert sub.subscription_id == "sub-12345"
    assert sub.display_name == "Test Subscription"
    assert sub.tags["Env"] == "Dev"
    assert sub.state == "Enabled"


def test_resource_group_metadata_with_adf():
    """Verify resource group and nested ADF instances."""
    adf = DataFactoryBrief(
        id="/subscriptions/sub-1/resourceGroups/rg-1/providers/Microsoft.DataFactory/factories/adf-test",
        name="adf-test",
        location="eastus",
        resource_group="rg-1",
        subscription_id="sub-1",
        public_network_access="Disabled",
    )
    rg = ResourceGroupMetadata(
        id="/subscriptions/sub-1/resourceGroups/rg-1",
        name="rg-1",
        location="eastus",
        subscription_id="sub-1",
        data_factories=[adf],
    )
    assert rg.name == "rg-1"
    assert len(rg.data_factories) == 1
    assert rg.data_factories[0].name == "adf-test"
    assert rg.data_factories[0].public_network_access == "Disabled"


def test_mock_fixture_validity():
    """Verify mock fixture generates valid Spike1Result conforming to contract."""
    result = get_mock_spike_1_result()
    assert isinstance(result, Spike1Result)
    assert result.status == "SUCCESS"
    assert len(result.subscriptions) == 2
    assert len(result.resource_groups) == 5
    assert len(result.data_factories_discovered) == 4
    assert result.summary["total_data_factories"] == 4
    assert result.auth_context.reader_role_validated is True

    # JSON serialization check
    json_data = result.model_dump_json()
    assert "adf-sales-prod-eastus" in json_data
    assert "Enterprise-Production-Data-Platform" in json_data
