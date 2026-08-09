"""Azure Identity Credential Factory supporting multiple authentication flows."""

from azure.core.credentials import TokenCredential
from azure.identity import (
    DefaultAzureCredential,
    InteractiveBrowserCredential,
    DeviceCodeCredential,
    AzureCliCredential,
    ClientSecretCredential,
)
from pie.core.config import AuthMode, Settings
from pie.core.exceptions import PieAuthError
from pie.core.logging import get_logger, console
from rich.panel import Panel

logger = get_logger(__name__)


def _device_code_prompt_callback(verification_uri: str, user_code: str, expires_on: str | None = None):
    """Render high-visibility prompt for Azure Device Code authentication."""
    msg = (
        f"[bold white]To sign in to Microsoft Azure:[/bold white]\n\n"
        f"1. Open your browser: [bold cyan]{verification_uri}[/bold cyan]\n"
        f"2. Enter the code: [bold yellow]{user_code}[/bold yellow]\n\n"
        f"[dim]Waiting for sign-in completion in your browser...[/dim]"
    )
    console.print(Panel(msg, title="[bold green]Microsoft Entra ID Device Authentication[/bold green]", border_style="green"))


class MockTokenCredential:
    """Mock TokenCredential for offline development and testing."""

    class MockAccessToken:
        def __init__(self, token: str = "mock-bearer-token-pie-offline-001"):
            self.token = token
            self.expires_on = 9999999999

    def get_token(self, *scopes, **kwargs) -> MockAccessToken:
        logger.info("[dim]Acquiring synthetic token using MockTokenCredential...[/dim]")
        return self.MockAccessToken()


class CredentialFactory:
    """Factory responsible for instantiating the appropriate TokenCredential."""

    @staticmethod
    def get_credential(settings: Settings) -> tuple[TokenCredential, str]:
        """Instantiate credential according to configured AuthMode.

        Returns:
            tuple[TokenCredential, str]: The credential instance and a human-readable description.
        """
        mode = settings.auth_mode if isinstance(settings.auth_mode, AuthMode) else AuthMode(settings.auth_mode)
        logger.info(f"Initializing Azure Credential Factory with mode: [cyan]{mode.value}[/cyan]")

        try:
            if mode == AuthMode.DEVICE_CODE:
                logger.info("Starting Microsoft Entra ID Device Code flow...")
                kwargs = {
                    "prompt_callback": _device_code_prompt_callback,
                    "client_id": settings.client_id or "04b07795-8ddb-461a-bbee-02f9e1bf7b46",
                }
                if settings.tenant_id:
                    kwargs["tenant_id"] = settings.tenant_id
                cred = DeviceCodeCredential(**kwargs)
                return cred, "Device Code Credential (Browser/Mobile Login)"

            elif mode == AuthMode.INTERACTIVE:
                logger.info("Opening system browser for Microsoft Entra ID authentication...")
                kwargs = {
                    "client_id": settings.client_id or "04b07795-8ddb-461a-bbee-02f9e1bf7b46",
                    "redirect_uri": "http://localhost:8400",
                }
                if settings.tenant_id:
                    kwargs["tenant_id"] = settings.tenant_id
                cred = InteractiveBrowserCredential(**kwargs)
                return cred, "Interactive Browser Credential (Entra ID - Port 8400)"

            elif mode == AuthMode.CLI:
                logger.info("Using Azure CLI active login session (az login)...")
                kwargs = {}
                if settings.tenant_id:
                    kwargs["tenant_id"] = settings.tenant_id
                cred = AzureCliCredential(**kwargs)
                return cred, "Azure CLI Active Credential"

            elif mode == AuthMode.SERVICE_PRINCIPAL:
                if not (settings.tenant_id and settings.client_id and settings.client_secret):
                    raise PieAuthError(
                        "Service Principal auth requires AZURE_TENANT_ID, AZURE_CLIENT_ID, and AZURE_CLIENT_SECRET."
                    )
                logger.info(f"Authenticating Service Principal App ID: {settings.client_id}")
                cred = ClientSecretCredential(
                    tenant_id=settings.tenant_id,
                    client_id=settings.client_id,
                    client_secret=settings.client_secret,
                )
                return cred, f"Service Principal ({settings.client_id})"

            elif mode == AuthMode.MOCK:
                logger.info("Using Mock Offline Credential for synthetic validation.")
                return MockTokenCredential(), "Mock Offline Credential (Synthetic)"

            elif mode == AuthMode.DEFAULT:
                # Default Azure Credential tries: Env -> Managed Identity -> Azure CLI -> Azure Developer CLI -> Interactive
                logger.info("Using DefaultAzureCredential resolution chain...")
                kwargs = {"exclude_interactive_browser_credential": False}
                if settings.tenant_id:
                    kwargs["interactive_browser_tenant_id"] = settings.tenant_id
                cred = DefaultAzureCredential(**kwargs)
                return cred, "DefaultAzureCredential (Chain: CLI -> ManagedIdentity -> Interactive)"

            else:
                raise PieAuthError(f"Unsupported authentication mode: {mode}")

        except Exception as e:
            if isinstance(e, PieAuthError):
                raise
            raise PieAuthError(f"Failed to initialize Azure Credential: {e}") from e
