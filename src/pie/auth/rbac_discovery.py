"""Azure Subscription and Resource Group RBAC discovery under Reader role."""

from azure.core.credentials import TokenCredential
from azure.core.exceptions import HttpResponseError, ClientAuthenticationError
from azure.mgmt.subscription import SubscriptionClient
from azure.mgmt.resource.resources import ResourceManagementClient
from azure.mgmt.datafactory import DataFactoryManagementClient

from pie.auth.models import (
    SubscriptionMetadata,
    ResourceGroupMetadata,
    DataFactoryBrief,
    AuthContext,
    Spike1Result,
)
from pie.core.exceptions import PieAuthError, PiePermissionError
from pie.core.logging import get_logger, console

logger = get_logger(__name__)


class AzureRbacDiscovery:
    """Discovers accessible Subscriptions, Resource Groups, and ADF instances under Reader role."""

    def __init__(self, credential: TokenCredential, auth_desc: str = "Default"):
        self.credential = credential
        self.auth_desc = auth_desc
        self.subscription_client = SubscriptionClient(credential=self.credential)

    def discover_subscriptions(self) -> list[SubscriptionMetadata]:
        """Enumerate all Azure Subscriptions accessible with current credentials."""
        discovered: list[SubscriptionMetadata] = []
        logger.info("Enumerating accessible Azure Subscriptions under Reader RBAC...")

        try:
            sub_pages = self.subscription_client.subscriptions.list()
            for sub in sub_pages:
                sub_meta = SubscriptionMetadata(
                    id=sub.id or f"/subscriptions/{sub.subscription_id}",
                    subscription_id=sub.subscription_id,
                    display_name=sub.display_name or sub.subscription_id,
                    state=sub.state.value if hasattr(sub.state, "value") else str(sub.state),
                    tenant_id=getattr(sub, "tenant_id", None),
                    tags=getattr(sub, "tags", {}) or {},
                )
                discovered.append(sub_meta)
                logger.info(
                    f"  [success]✓[/success] Discovered Subscription: [bold cyan]{sub_meta.display_name}[/bold cyan] "
                    f"([dim]{sub_meta.subscription_id}[/dim]) - State: {sub_meta.state}"
                )

        except ClientAuthenticationError as e:
            raise PieAuthError(f"Azure Entra ID Authentication failed: {e.message}") from e
        except HttpResponseError as e:
            if e.status_code == 403:
                raise PiePermissionError(
                    f"Insufficient permissions to list subscriptions. Ensure Reader role is assigned: {e.message}"
                ) from e
            raise PieAuthError(f"Failed to query Azure Subscription API: {e.message}") from e
        except Exception as e:
            raise PieAuthError(f"Unexpected error enumerating subscriptions: {e}") from e

        return discovered

    def discover_resource_groups(
        self, subscription_id: str, scan_data_factories: bool = True
    ) -> list[ResourceGroupMetadata]:
        """Enumerate all Resource Groups within a specific Subscription and detect ADF instances."""
        discovered_rgs: list[ResourceGroupMetadata] = []
        rg_client = ResourceManagementClient(
            credential=self.credential,
            subscription_id=subscription_id,
        )

        try:
            adf_client = None
            if scan_data_factories:
                try:
                    adf_client = DataFactoryManagementClient(
                        credential=self.credential,
                        subscription_id=subscription_id,
                    )
                except Exception as e:
                    logger.warning(f"Could not initialize ADF client for subscription {subscription_id}: {e}")

            rg_pages = rg_client.resource_groups.list()
            for rg in rg_pages:
                data_factories: list[DataFactoryBrief] = []

                if adf_client:
                    try:
                        factories = adf_client.factories.list_by_resource_group(rg.name)
                        for f in factories:
                            data_factories.append(
                                DataFactoryBrief(
                                    id=f.id or f"{rg.id}/providers/Microsoft.DataFactory/factories/{f.name}",
                                    name=f.name,
                                    location=f.location or rg.location,
                                    resource_group=rg.name,
                                    subscription_id=subscription_id,
                                    public_network_access=getattr(f, "public_network_access", None),
                                    tags=getattr(f, "tags", {}) or {},
                                )
                            )
                    except HttpResponseError as err:
                        if err.status_code == 403:
                            logger.debug(f"Access to list factories in RG {rg.name} was forbidden (403).")
                    except Exception as err:
                        logger.debug(f"Failed scanning ADFs in RG {rg.name}: {err}")

                rg_meta = ResourceGroupMetadata(
                    id=rg.id or f"/subscriptions/{subscription_id}/resourceGroups/{rg.name}",
                    name=rg.name,
                    location=rg.location,
                    subscription_id=subscription_id,
                    provisioning_state=rg.properties.provisioning_state if rg.properties else "Succeeded",
                    tags=rg.tags or {},
                    data_factories=data_factories,
                )
                discovered_rgs.append(rg_meta)

        except HttpResponseError as e:
            if e.status_code == 403:
                logger.warning(f"Access forbidden (403) listing resource groups in subscription {subscription_id}")
            else:
                logger.error(f"Error querying resource groups in {subscription_id}: {e.message}")
        except Exception as e:
            logger.error(f"Failed to list resource groups for subscription {subscription_id}: {e}")

        return discovered_rgs

    def run_discovery(self, target_subscription_id: str | None = None) -> Spike1Result:
        """Run full end-to-end RBAC discovery."""
        subscriptions = self.discover_subscriptions()

        if not subscriptions:
            logger.warning("[warning]No accessible subscriptions found under current credentials.[/warning]")

        all_rgs: list[ResourceGroupMetadata] = []
        all_adfs: list[DataFactoryBrief] = []

        # Filter target subscription if specified
        target_subs = (
            [s for s in subscriptions if s.subscription_id.lower() == target_subscription_id.lower()]
            if target_subscription_id
            else subscriptions
        )

        for sub in target_subs:
            logger.info(f"Scanning Resource Groups in subscription: [bold cyan]{sub.display_name}[/bold cyan]...")
            rgs = self.discover_resource_groups(sub.subscription_id)
            all_rgs.extend(rgs)
            for rg in rgs:
                if rg.data_factories:
                    all_adfs.extend(rg.data_factories)
                    for adf in rg.data_factories:
                        logger.info(
                            f"    [highlight]🏭 Discovered ADF:[/highlight] [bold white]{adf.name}[/bold white] "
                            f"(RG: [cyan]{rg.name}[/cyan], Region: {adf.location})"
                        )

        summary = {
            "total_subscriptions": len(subscriptions),
            "scanned_subscriptions": len(target_subs),
            "total_resource_groups": len(all_rgs),
            "total_data_factories": len(all_adfs),
        }

        return Spike1Result(
            auth_context=AuthContext(
                auth_mode=self.auth_desc,
                tenant_id=subscriptions[0].tenant_id if subscriptions else None,
                token_acquired=True,
                reader_role_validated=True,
            ),
            subscriptions=subscriptions,
            resource_groups=all_rgs,
            data_factories_discovered=all_adfs,
            summary=summary,
        )
