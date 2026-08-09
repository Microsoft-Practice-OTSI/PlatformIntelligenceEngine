"""Synthetic offline Azure tenant and subscription fixture for Spike 1."""

from datetime import datetime
from pie.auth.models import (
    SubscriptionMetadata,
    ResourceGroupMetadata,
    DataFactoryBrief,
    AuthContext,
    Spike1Result,
)


def get_mock_spike_1_result() -> Spike1Result:
    """Generate high-fidelity synthetic Azure environment for offline validation."""
    sub1_id = "00000000-0000-0000-0000-000000000001"
    sub2_id = "00000000-0000-0000-0000-000000000002"
    tenant_id = "72f988bf-86f1-41af-91ab-2d7cd011db47"

    sub1 = SubscriptionMetadata(
        id=f"/subscriptions/{sub1_id}",
        subscription_id=sub1_id,
        display_name="Enterprise-Production-Data-Platform",
        state="Enabled",
        tenant_id=tenant_id,
        tags={"Environment": "Production", "CostCenter": "DataEng-101", "Compliance": "SOC2"},
    )

    sub2 = SubscriptionMetadata(
        id=f"/subscriptions/{sub2_id}",
        subscription_id=sub2_id,
        display_name="Analytics-Sandbox-NonProd",
        state="Enabled",
        tenant_id=tenant_id,
        tags={"Environment": "Development", "CostCenter": "DataEng-102"},
    )

    # Factories
    adf_sales = DataFactoryBrief(
        id=f"/subscriptions/{sub1_id}/resourceGroups/rg-enterprise-sales-prod/providers/Microsoft.DataFactory/factories/adf-sales-prod-eastus",
        name="adf-sales-prod-eastus",
        location="eastus",
        resource_group="rg-enterprise-sales-prod",
        subscription_id=sub1_id,
        public_network_access="Disabled",
        tags={"Tier": "MissionCritical", "Workload": "SalesIngestion"},
    )

    adf_c360 = DataFactoryBrief(
        id=f"/subscriptions/{sub1_id}/resourceGroups/rg-customer-360-prod/providers/Microsoft.DataFactory/factories/adf-customer360-westeurope",
        name="adf-customer360-westeurope",
        location="westeurope",
        resource_group="rg-customer-360-prod",
        subscription_id=sub1_id,
        public_network_access="Enabled",
        tags={"Tier": "Tier1", "Workload": "Customer360"},
    )

    adf_finance = DataFactoryBrief(
        id=f"/subscriptions/{sub1_id}/resourceGroups/rg-finance-reporting-prod/providers/Microsoft.DataFactory/factories/adf-finance-reporting-centralus",
        name="adf-finance-reporting-centralus",
        location="centralus",
        resource_group="rg-finance-reporting-prod",
        subscription_id=sub1_id,
        public_network_access="Disabled",
        tags={"Tier": "Tier1", "Workload": "FinanceGL"},
    )

    adf_dev = DataFactoryBrief(
        id=f"/subscriptions/{sub2_id}/resourceGroups/rg-data-analytics-dev/providers/Microsoft.DataFactory/factories/adf-analytics-dev-eastus2",
        name="adf-analytics-dev-eastus2",
        location="eastus2",
        resource_group="rg-data-analytics-dev",
        subscription_id=sub2_id,
        public_network_access="Enabled",
        tags={"Tier": "NonProd", "Workload": "SandboxETL"},
    )

    # Resource Groups
    rg1 = ResourceGroupMetadata(
        id=f"/subscriptions/{sub1_id}/resourceGroups/rg-enterprise-sales-prod",
        name="rg-enterprise-sales-prod",
        location="eastus",
        subscription_id=sub1_id,
        provisioning_state="Succeeded",
        tags={"Workload": "Sales", "ManagedBy": "Terraform"},
        data_factories=[adf_sales],
    )

    rg2 = ResourceGroupMetadata(
        id=f"/subscriptions/{sub1_id}/resourceGroups/rg-customer-360-prod",
        name="rg-customer-360-prod",
        location="westeurope",
        subscription_id=sub1_id,
        provisioning_state="Succeeded",
        tags={"Workload": "Customer", "ManagedBy": "Terraform"},
        data_factories=[adf_c360],
    )

    rg3 = ResourceGroupMetadata(
        id=f"/subscriptions/{sub1_id}/resourceGroups/rg-finance-reporting-prod",
        name="rg-finance-reporting-prod",
        location="centralus",
        subscription_id=sub1_id,
        provisioning_state="Succeeded",
        tags={"Workload": "Finance", "ManagedBy": "Bicep"},
        data_factories=[adf_finance],
    )

    rg4 = ResourceGroupMetadata(
        id=f"/subscriptions/{sub2_id}/resourceGroups/rg-data-analytics-dev",
        name="rg-data-analytics-dev",
        location="eastus2",
        subscription_id=sub2_id,
        provisioning_state="Succeeded",
        tags={"Environment": "Dev"},
        data_factories=[adf_dev],
    )

    rg5 = ResourceGroupMetadata(
        id=f"/subscriptions/{sub2_id}/resourceGroups/rg-sandbox-playground",
        name="rg-sandbox-playground",
        location="eastus2",
        subscription_id=sub2_id,
        provisioning_state="Succeeded",
        tags={"Purpose": "Scratchpad"},
        data_factories=[],
    )

    all_subs = [sub1, sub2]
    all_rgs = [rg1, rg2, rg3, rg4, rg5]
    all_factories = [adf_sales, adf_c360, adf_finance, adf_dev]

    return Spike1Result(
        spike_id="spike_1_azure_auth_rbac",
        status="SUCCESS",
        executed_at=datetime.utcnow(),
        auth_context=AuthContext(
            auth_mode="Mock Offline Credential (Synthetic)",
            tenant_id=tenant_id,
            token_acquired=True,
            reader_role_validated=True,
            principal_type="Synthetic Test Fixture",
        ),
        subscriptions=all_subs,
        resource_groups=all_rgs,
        data_factories_discovered=all_factories,
        summary={
            "total_subscriptions": len(all_subs),
            "scanned_subscriptions": len(all_subs),
            "total_resource_groups": len(all_rgs),
            "total_data_factories": len(all_factories),
        },
    )
