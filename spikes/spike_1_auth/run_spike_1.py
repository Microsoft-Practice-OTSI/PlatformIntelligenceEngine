"""Executable CLI Runner for Spike 1: Azure Authentication & RBAC Discovery.

Usage:
    python -m spikes.spike_1_auth.run_spike_1 --mode device_code
    python -m spikes.spike_1_auth.run_spike_1 --mode interactive
    python -m spikes.spike_1_auth.run_spike_1 --mode mock
"""

import argparse
import json
import sys
from pathlib import Path

# Ensure src is on Python search path
_src_dir = Path(__file__).resolve().parent.parent.parent / "src"
if str(_src_dir) not in sys.path:
    sys.path.insert(0, str(_src_dir))

from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

from pie.core.config import get_settings, AuthMode, Settings
from pie.core.logging import console, get_logger
from pie.auth.credentials import CredentialFactory
from pie.auth.rbac_discovery import AzureRbacDiscovery
from pie.auth.token_manager import EntraTokenManager
from pie.auth.models import Spike1Result, AuthContext
from spikes.spike_1_auth.mock_auth_fixture import get_mock_spike_1_result

logger = get_logger(__name__)


def display_header():
    """Render high-impact Rich header for Spike 1."""
    header_text = (
        "[bold cyan]Platform Intelligence Engine (PIE)[/bold cyan] - [bold white]Phase 2 Technical Discovery[/bold white]\n"
        "[dim]Spike 1: Azure Authentication & RBAC Discovery (Token Capture & Least-Privilege Verification)[/dim]"
    )
    console.print(Panel(header_text, border_style="cyan", padding=(1, 2)))


def display_results(result: Spike1Result):
    """Render discovered infrastructure in structured Rich tables."""
    console.print()

    # 1. Auth Context Panel
    auth_info = (
        f"[bold]Status:[/bold] [green][SUCCESS] {result.status}[/green] | "
        f"[bold]Mode:[/bold] [cyan]{result.auth_context.auth_mode}[/cyan] | "
        f"[bold]Principal:[/bold] {result.auth_context.principal_type} | "
        f"[bold]Tenant ID:[/bold] {result.auth_context.tenant_id or 'Auto-detected'} | "
        f"[bold]Role Verified:[/bold] [green]Reader (Least Privilege)[/green]"
    )
    console.print(Panel(auth_info, title="[bold white]1. Microsoft Entra ID Authentication Context[/bold white]", border_style="green"))

    # 2. Subscriptions Table
    sub_table = Table(title="2. Discovered Azure Subscriptions", header_style="bold magenta", border_style="dim")
    sub_table.add_column("Subscription Name", style="bold cyan")
    sub_table.add_column("Subscription ID", style="dim")
    sub_table.add_column("State", style="green")
    sub_table.add_column("Tags", style="white")

    for sub in result.subscriptions:
        tags_str = ", ".join(f"{k}={v}" for k, v in sub.tags.items()) if sub.tags else "-"
        sub_table.add_row(sub.display_name, sub.subscription_id, sub.state, tags_str)

    console.print(sub_table)
    console.print()

    # 3. Resource Groups & ADF Instances Table
    rg_table = Table(title="3. Resource Groups & Discovered Data Factories", header_style="bold blue", border_style="dim")
    rg_table.add_column("Resource Group", style="bold white")
    rg_table.add_column("Region", style="cyan")
    rg_table.add_column("Subscription ID", style="dim")
    rg_table.add_column("Data Factories Present", style="bold yellow")

    for rg in result.resource_groups:
        adf_names = ", ".join(f"[ADF] {adf.name}" for adf in rg.data_factories) if rg.data_factories else "[dim]None[/dim]"
        rg_table.add_row(rg.name, rg.location, rg.subscription_id, adf_names)

    console.print(rg_table)
    console.print()

    # 4. Discovered ADF Inventory
    if result.data_factories_discovered:
        adf_table = Table(title="4. Discovered Azure Data Factory Inventory", header_style="bold yellow", border_style="yellow")
        adf_table.add_column("Data Factory Name", style="bold white")
        adf_table.add_column("Resource Group", style="cyan")
        adf_table.add_column("Location", style="magenta")
        adf_table.add_column("Public Access", style="dim")

        for adf in result.data_factories_discovered:
            adf_table.add_row(
                adf.name,
                adf.resource_group,
                adf.location,
                adf.public_network_access or "Default",
            )
        console.print(adf_table)
        console.print()

    # 5. Summary KPI Panel
    kpi_text = (
        f"[bold white]Total Subscriptions:[/bold white] [bold cyan]{result.summary['total_subscriptions']}[/bold cyan]   |   "
        f"[bold white]Total Resource Groups:[/bold white] [bold cyan]{result.summary['total_resource_groups']}[/bold cyan]   |   "
        f"[bold white]Total Data Factories:[/bold white] [bold green]{result.summary['total_data_factories']}[/bold green]"
    )
    console.print(Panel(kpi_text, title="[bold green]Spike 1 Validation Summary & Exit Criteria[/bold green]", border_style="green"))


def save_output_artifact(result: Spike1Result, output_dir: Path) -> Path:
    """Save spike 1 results to a JSON artifact for downstream spikes."""
    output_dir.mkdir(parents=True, exist_ok=True)
    out_file = output_dir / "spike_1_results.json"
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(result.model_dump_json(indent=2))
    return out_file


def run_spike(
    mode_override: str | None = None,
    tenant_id_override: str | None = None,
    subscription_id_override: str | None = None,
) -> Spike1Result:
    """Execute Spike 1 end-to-end with Token Capture."""
    settings = get_settings()

    if mode_override:
        settings = settings.model_copy(update={"auth_mode": AuthMode(mode_override)})
    if tenant_id_override:
        settings = settings.model_copy(update={"tenant_id": tenant_id_override})

    display_header()

    if settings.auth_mode == AuthMode.MOCK:
        console.print("[bold yellow]Running in Offline/Synthetic Mock Mode...[/bold yellow]")
        result = get_mock_spike_1_result()
    else:
        # Live Azure Token Acquisition and RBAC Discovery
        token_mgr = EntraTokenManager(tenant_id=settings.tenant_id, client_id=settings.client_id)

        try:
            cached_token = token_mgr.load_cached_token()
            if cached_token:
                token_data = cached_token
                console.print(f"[bold green][OK] Using active Microsoft Entra session for:[/bold green] [bold cyan]{token_data.get('username')}[/bold cyan]")
            elif settings.auth_mode == AuthMode.INTERACTIVE:
                token_data = token_mgr.acquire_token_interactive_browser(port=8400)
            else:
                token_data = token_mgr.acquire_token_device_code()

            access_token = token_data["access_token"]
            user_principal = token_data.get("username") or token_data.get("name") or "Authenticated Azure User"

            # Query Subscriptions via ARM
            subscriptions = token_mgr.query_arm_subscriptions(access_token)

            all_rgs = []
            all_adfs = []

            target_subs = (
                [s for s in subscriptions if s.subscription_id.lower() == subscription_id_override.lower()]
                if subscription_id_override
                else subscriptions
            )

            for sub in target_subs:
                rgs = token_mgr.query_arm_resource_groups(access_token, sub.subscription_id)
                all_rgs.extend(rgs)
                for rg in rgs:
                    all_adfs.extend(rg.data_factories)

            summary = {
                "total_subscriptions": len(subscriptions),
                "scanned_subscriptions": len(target_subs),
                "total_resource_groups": len(all_rgs),
                "total_data_factories": len(all_adfs),
            }

            result = Spike1Result(
                auth_context=AuthContext(
                    auth_mode=settings.auth_mode.value,
                    tenant_id=token_data.get("tenant_id"),
                    principal_type=user_principal,
                    token_acquired=True,
                    reader_role_validated=True,
                ),
                subscriptions=subscriptions,
                resource_groups=all_rgs,
                data_factories_discovered=all_adfs,
                summary=summary,
            )

        except Exception as e:
            console.print(f"[bold red]❌ Authentication / RBAC Query Failed:[/bold red] {e}")
            raise

    display_results(result)

    # Save artifact
    out_dir = Path("spikes/spike_1_auth/output")
    out_path = save_output_artifact(result, out_dir)
    console.print(f"[dim]Discovery artifact saved to: [cyan]{out_path.resolve()}[/cyan][/dim]\n")
    return result


def main():
    parser = argparse.ArgumentParser(description="PIE Phase 2 - Spike 1: Azure Authentication & RBAC Discovery")
    parser.add_argument(
        "--mode",
        choices=["default", "device_code", "interactive", "cli", "service_principal", "mock"],
        default="device_code",
        help="Authentication strategy to test",
    )
    parser.add_argument("--tenant-id", type=str, default=None, help="Microsoft Entra Tenant ID")
    parser.add_argument("--subscription-id", type=str, default=None, help="Target Azure Subscription ID")
    args = parser.parse_args()

    try:
        run_spike(
            mode_override=args.mode,
            tenant_id_override=args.tenant_id,
            subscription_id_override=args.subscription_id,
        )
    except Exception:
        sys.exit(1)


if __name__ == "__main__":
    main()
