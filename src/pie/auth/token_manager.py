"""Dedicated Microsoft Entra ID Token Manager with Token Persistence & Direct REST RBAC querying."""

import json
import time
from pathlib import Path
from typing import Any
import requests
import msal
from azure.core.credentials import AccessToken, TokenCredential

from pie.core.logging import get_logger, console
from pie.core.exceptions import PieAuthError, PiePermissionError
from pie.auth.models import (
    SubscriptionMetadata,
    ResourceGroupMetadata,
    DataFactoryBrief,
    AuthContext,
    Spike1Result,
)
from rich.panel import Panel

logger = get_logger(__name__)

# Standard Microsoft Azure CLI multi-tenant client ID (public client)
DEFAULT_CLIENT_ID = "04b07795-8ddb-461a-bbee-02f9e1bf7b46"
ARM_SCOPE = ["https://management.azure.com/.default"]
SESSION_TOKEN_PATH = Path("spikes/spike_1_auth/output/token_session.json")


class BearerTokenCredential(TokenCredential):
    """Direct TokenCredential implementation wrapping a raw Bearer token."""

    def __init__(self, token: str, expires_on: int = 0):
        self.token = token
        self.expires_on = expires_on or int(time.time() + 3600)

    def get_token(self, *scopes, **kwargs) -> AccessToken:
        return AccessToken(self.token, self.expires_on)


class EntraTokenManager:
    """Manages Microsoft Entra ID OAuth flows, captures access tokens, and queries ARM APIs directly."""

    def __init__(
        self,
        tenant_id: str | None = None,
        client_id: str | None = None,
        session_file: Path = SESSION_TOKEN_PATH,
    ):
        self.tenant_id = tenant_id or "organizations"
        self.client_id = client_id or DEFAULT_CLIENT_ID
        self.session_file = session_file
        self.authority = f"https://login.microsoftonline.com/{self.tenant_id}"
        self.app = msal.PublicClientApplication(
            client_id=self.client_id,
            authority=self.authority,
            token_cache=msal.SerializableTokenCache(),
        )

    def save_session(self, token_data: dict[str, Any]) -> Path:
        """Persist captured token and claims to disk for downstream spikes."""
        self.session_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.session_file, "w", encoding="utf-8") as f:
            json.dump(token_data, f, indent=2)
        logger.info(f"[green][OK] Token session securely saved to:[/green] [cyan]{self.session_file.resolve()}[/cyan]")
        return self.session_file

    def load_cached_token(self) -> dict[str, Any] | None:
        """Load active token from disk cache if not expired."""
        if not self.session_file.exists():
            return None
        try:
            with open(self.session_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            expires_at = data.get("expires_at", 0)
            if time.time() < expires_at - 60:
                logger.info("[green][OK] Found valid, unexpired cached Azure session token.[/green]")
                return data
            logger.info("[dim]Cached token is expired. Re-authenticating...[/dim]")
        except Exception as e:
            logger.debug(f"Error loading token cache: {e}")
        return None

    def acquire_token_device_code(self) -> dict[str, Any]:
        """Execute device code flow, log prompt to screen, and capture token."""
        logger.info(f"Initiating Device Code flow against authority: [cyan]{self.authority}[/cyan]")
        flow = self.app.initiate_device_flow(scopes=ARM_SCOPE)
        if "user_code" not in flow:
            raise PieAuthError(f"Failed to initiate device flow: {flow.get('error_description', flow)}")

        # Display rich prompt
        uri = flow.get("verification_uri", "https://microsoft.com/devicelogin")
        code = flow.get("user_code")
        msg = (
            f"[bold white]To authenticate with Microsoft Azure:[/bold white]\n\n"
            f"1. Open your browser: [bold cyan]{uri}[/bold cyan]\n"
            f"2. Enter this code: [bold yellow]{code}[/bold yellow]\n\n"
            f"[dim]Waiting for sign-in completion in your browser...[/dim]"
        )
        console.print(Panel(msg, title="[bold green]Microsoft Entra ID Device Authentication[/bold green]", border_style="green"))

        # Poll MSAL for token
        result = self.app.acquire_token_by_device_flow(flow)
        if "access_token" in result:
            claims = result.get("id_token_claims", {})
            token_payload = {
                "access_token": result["access_token"],
                "token_type": result.get("token_type", "Bearer"),
                "expires_in": result.get("expires_in", 3600),
                "expires_at": int(time.time() + result.get("expires_in", 3600)),
                "tenant_id": claims.get("tid", self.tenant_id),
                "username": claims.get("preferred_username") or claims.get("email") or claims.get("upn"),
                "name": claims.get("name"),
                "auth_method": "device_code",
            }
            self.save_session(token_payload)
            return token_payload

        error_msg = result.get("error_description") or result.get("error") or str(result)
        raise PieAuthError(f"Azure authentication failed: {error_msg}")

    def acquire_token_interactive_browser(self, port: int = 8400) -> dict[str, Any]:
        """Execute interactive browser flow with local HTTP redirect listener."""
        logger.info(f"Opening browser for interactive authentication on port {port}...")
        try:
            result = self.app.acquire_token_interactive(
                scopes=ARM_SCOPE,
                port=port,
            )
            if "access_token" in result:
                claims = result.get("id_token_claims", {})
                token_payload = {
                    "access_token": result["access_token"],
                    "token_type": result.get("token_type", "Bearer"),
                    "expires_in": result.get("expires_in", 3600),
                    "expires_at": int(time.time() + result.get("expires_in", 3600)),
                    "tenant_id": claims.get("tid", self.tenant_id),
                    "username": claims.get("preferred_username") or claims.get("email") or claims.get("upn"),
                    "name": claims.get("name"),
                    "auth_method": "interactive_browser",
                }
                self.save_session(token_payload)
                return token_payload

            error_msg = result.get("error_description") or result.get("error") or str(result)
            raise PieAuthError(f"Interactive browser authentication failed: {error_msg}")
        except Exception as e:
            if isinstance(e, PieAuthError):
                raise
            raise PieAuthError(f"Browser authentication encountered an error: {e}") from e

    def get_token_credential(self, force_refresh: bool = False) -> tuple[TokenCredential, dict[str, Any]]:
        """Retrieve active TokenCredential, reusing valid cached token or acquiring a fresh one."""
        if not force_refresh:
            cached = self.load_cached_token()
            if cached:
                return BearerTokenCredential(cached["access_token"], cached.get("expires_at", 0)), cached

        # Fallback to device code flow
        token_data = self.acquire_token_device_code()
        return BearerTokenCredential(token_data["access_token"], token_data.get("expires_at", 0)), token_data

    @staticmethod
    def query_arm_subscriptions(access_token: str) -> list[SubscriptionMetadata]:
        """Query Azure Resource Manager directly via HTTP REST to list subscriptions."""
        url = "https://management.azure.com/subscriptions?api-version=2020-01-01"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        logger.info("Querying Azure Resource Manager: [cyan]GET /subscriptions[/cyan]")
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code == 401 or resp.status_code == 403:
            raise PiePermissionError(f"ARM Subscriptions API unauthorized ({resp.status_code}): {resp.text}")
        if not resp.ok:
            raise PieAuthError(f"ARM API Error ({resp.status_code}): {resp.text}")

        data = resp.json()
        subs: list[SubscriptionMetadata] = []
        for item in data.get("value", []):
            subs.append(
                SubscriptionMetadata(
                    id=item.get("id"),
                    subscription_id=item.get("subscriptionId"),
                    display_name=item.get("displayName") or item.get("subscriptionId"),
                    state=item.get("state", "Enabled"),
                    tenant_id=item.get("tenantId"),
                    tags=item.get("tags") or {},
                )
            )
            logger.info(f"  [success]✓ Discovered Subscription:[/success] [bold white]{subs[-1].display_name}[/bold white] ({subs[-1].subscription_id})")
        return subs

    @staticmethod
    def query_arm_resource_groups(access_token: str, subscription_id: str) -> list[ResourceGroupMetadata]:
        """Query ARM directly to list resource groups and discover Data Factories via subscription provider."""
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        # 1. Direct subscription-level Data Factory discovery (Fast 1 API call per subscription)
        factories_by_rg: dict[str, list[DataFactoryBrief]] = {}
        adf_sub_url = f"https://management.azure.com/subscriptions/{subscription_id}/providers/Microsoft.DataFactory/factories?api-version=2018-06-01"
        try:
            adf_resp = requests.get(adf_sub_url, headers=headers, timeout=12)
            if adf_resp.ok:
                for f in adf_resp.json().get("value", []):
                    # Extract RG from ID: /subscriptions/.../resourceGroups/<RG>/providers/...
                    f_id = f.get("id", "")
                    rg_name = "unknown"
                    if "/resourceGroups/" in f_id:
                        rg_name = f_id.split("/resourceGroups/")[1].split("/")[0]
                    elif "/resourcegroups/" in f_id:
                        rg_name = f_id.split("/resourcegroups/")[1].split("/")[0]

                    brief = DataFactoryBrief(
                        id=f_id,
                        name=f.get("name"),
                        location=f.get("location", "unknown"),
                        resource_group=rg_name,
                        subscription_id=subscription_id,
                        public_network_access=f.get("properties", {}).get("publicNetworkAccess"),
                        tags=f.get("tags") or {},
                    )
                    factories_by_rg.setdefault(rg_name.lower(), []).append(brief)
                    logger.info(f"    [highlight]🏭 Discovered ADF:[/highlight] [bold white]{brief.name}[/bold white] in [cyan]{rg_name}[/cyan] ({brief.location})")
        except Exception as e:
            logger.debug(f"Error querying subscription ADFs in {subscription_id}: {e}")

        # 2. Query Resource Groups
        url = f"https://management.azure.com/subscriptions/{subscription_id}/resourcegroups?api-version=2021-04-01"
        rgs: list[ResourceGroupMetadata] = []
        try:
            resp = requests.get(url, headers=headers, timeout=12)
            if resp.ok:
                for item in resp.json().get("value", []):
                    rg_name = item.get("name")
                    matched_adfs = factories_by_rg.get(rg_name.lower(), [])
                    rgs.append(
                        ResourceGroupMetadata(
                            id=item.get("id"),
                            name=rg_name,
                            location=item.get("location", "unknown"),
                            subscription_id=subscription_id,
                            provisioning_state=item.get("properties", {}).get("provisioningState", "Succeeded"),
                            tags=item.get("tags") or {},
                            data_factories=matched_adfs,
                        )
                    )
        except Exception as e:
            logger.warning(f"Failed fetching resource groups for {subscription_id}: {e}")

        return rgs
