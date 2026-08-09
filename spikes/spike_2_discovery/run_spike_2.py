"""Executable CLI Runner for Spike 2: ADF Metadata Extraction & Schema Normalization.

Usage:
    python -m spikes.spike_2_discovery.run_spike_2 --mode mock
    python -m spikes.spike_2_discovery.run_spike_2 --mode default --resource-group <rg> --factory-name <factory>
"""

import argparse
import sys
from pathlib import Path

# Ensure src is on sys.path
_src_dir = Path(__file__).resolve().parent.parent.parent / "src"
if str(_src_dir) not in sys.path:
    sys.path.insert(0, str(_src_dir))

from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

from pie.core.config import get_settings, AuthMode
from pie.core.logging import console, get_logger
from pie.auth.credentials import CredentialFactory
from pie.discovery.extractor import AdfMetadataExtractor
from pie.discovery.models import Spike2Result, FactoryMetadata
from spikes.spike_2_discovery.mock_adf_fixture import get_mock_spike_2_result

logger = get_logger(__name__)


def display_header():
    """Render Rich header for Spike 2."""
    header_text = (
        "[bold cyan]Platform Intelligence Engine (PIE)[/bold cyan] - [bold white]Phase 2 Technical Discovery[/bold white]\n"
        "[dim]Spike 2: ADF Metadata Extraction & Schema Normalization (Pipelines, Activities, Datasets, Linked Services, Triggers)[/dim]"
    )
    console.print(Panel(header_text, border_style="cyan", padding=(1, 2)))


def display_factory_metadata(factory: FactoryMetadata):
    """Render comprehensive Rich tables for a discovered Data Factory."""
    # 1. Pipelines Table
    pipe_table = Table(title=f"1. Discovered Pipelines in {factory.factory_name} (Showing Top 15 of {len(factory.pipelines)})", header_style="bold cyan", border_style="dim")
    pipe_table.add_column("Pipeline Name", style="bold white")
    pipe_table.add_column("Folder", style="cyan")
    pipe_table.add_column("Activities", style="bold green", justify="right")
    pipe_table.add_column("Parameters", style="yellow", justify="right")
    pipe_table.add_column("Annotations", style="magenta")

    for p in factory.pipelines[:15]:
        annot_str = ", ".join(p.annotations[:3]) if p.annotations else "-"
        pipe_table.add_row(p.name, p.folder or "/", str(len(p.activities)), str(len(p.parameters)), annot_str)

    console.print(pipe_table)
    if len(factory.pipelines) > 15:
        console.print(f"[dim]... and {len(factory.pipelines) - 15} more pipelines saved to JSON artifact[/dim]\n")

    # 2. Datasets Table
    ds_table = Table(title=f"2. Datasets & Storage (Showing Top 15 of {len(factory.datasets)})", header_style="bold yellow", border_style="dim")
    ds_table.add_column("Dataset Name", style="bold white")
    ds_table.add_column("Type", style="cyan")
    ds_table.add_column("Folder", style="dim")
    ds_table.add_column("Linked Service", style="bold magenta")
    ds_table.add_column("Schema Columns", style="green", justify="right")

    for d in factory.datasets[:15]:
        ds_table.add_row(d.name, d.type, d.folder or "/", d.linked_service_name, str(len(d.schema_fields)))

    console.print(ds_table)
    if len(factory.datasets) > 15:
        console.print(f"[dim]... and {len(factory.datasets) - 15} more datasets saved to JSON artifact[/dim]\n")

    # 3. Linked Services Table
    ls_table = Table(title=f"3. Linked Services & Connection Posture (Showing Top 15 of {len(factory.linked_services)})", header_style="bold magenta", border_style="dim")
    ls_table.add_column("Linked Service Name", style="bold white")
    ls_table.add_column("Type", style="cyan")
    ls_table.add_column("Host / Endpoint / Server", style="yellow")
    ls_table.add_column("Security Posture", style="green")

    for ls in factory.linked_services[:15]:
        host = (
            ls.connection_properties.get("server")
            or ls.connection_properties.get("accountEndpoint")
            or ls.connection_properties.get("domain")
            or ls.connection_properties.get("baseUrl")
            or "[dim]Configured[/dim]"
        )
        ls_table.add_row(ls.name, ls.type, str(host), "[green][SECURE] Secrets Sanitized[/green]")

    console.print(ls_table)
    if len(factory.linked_services) > 15:
        console.print(f"[dim]... and {len(factory.linked_services) - 15} more linked services saved to JSON artifact[/dim]\n")

    # 4. Triggers Table
    tr_table = Table(title=f"4. Triggers & Schedules (Total: {len(factory.triggers)})", header_style="bold green", border_style="dim")
    tr_table.add_column("Trigger Name", style="bold white")
    tr_table.add_column("Type", style="cyan")
    tr_table.add_column("State", style="bold green")
    tr_table.add_column("Recurrence / Event", style="yellow")
    tr_table.add_column("Target Pipelines", style="bold white")

    for tr in factory.triggers[:15]:
        targets = ", ".join(tr.pipelines[:3]) if tr.pipelines else "[dim]None[/dim]"
        tr_table.add_row(tr.name, tr.type, tr.runtime_state, tr.recurrence_schedule or "-", targets)

    console.print(tr_table)
    console.print()


def display_kpi_summary(result: Spike2Result):
    """Render overall KPI summary panel."""
    kpi_text = (
        f"[bold white]Total Factories Scanned:[/bold white] [bold cyan]{result.total_factories}[/bold cyan]   |   "
        f"[bold white]Total Pipelines:[/bold white] [bold cyan]{result.total_pipelines}[/bold cyan]   |   "
        f"[bold white]Total Activities:[/bold white] [bold green]{result.total_activities}[/bold green]   |   "
        f"[bold white]Total Datasets:[/bold white] [bold yellow]{result.total_datasets}[/bold yellow]   |   "
        f"[bold white]Linked Services:[/bold white] [bold magenta]{result.total_linked_services}[/bold magenta]   |   "
        f"[bold white]Triggers:[/bold white] [bold cyan]{result.total_triggers}[/bold cyan]"
    )
    console.print(Panel(kpi_text, title="[bold green]Spike 2 Metadata Extraction Summary & Exit Criteria[/bold green]", border_style="green"))


def save_output_artifact(result: Spike2Result, output_dir: Path) -> Path:
    """Save normalized metadata result to a JSON artifact for downstream spikes."""
    output_dir.mkdir(parents=True, exist_ok=True)
    out_file = output_dir / "spike_2_metadata.json"
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(result.model_dump_json(indent=2))
    return out_file


def run_spike(
    mode_override: str | None = None,
    subscription_id_override: str | None = None,
    resource_group_override: str | None = None,
    factory_name_override: str | None = None,
) -> Spike2Result:
    """Execute Spike 2 end-to-end."""
    settings = get_settings()

    if mode_override:
        settings = settings.model_copy(update={"auth_mode": AuthMode(mode_override)})

    display_header()

    if settings.auth_mode == AuthMode.MOCK:
        console.print("[bold yellow]Running in Offline/Synthetic Enterprise Mock Mode...[/bold yellow]")
        result = get_mock_spike_2_result()
    else:
        rg = resource_group_override or settings.resource_group
        factory = factory_name_override or settings.factory_name
        sub_id = subscription_id_override or settings.subscription_id

        if not (rg and factory and sub_id):
            console.print(
                "[bold yellow]Notice:[/bold yellow] To run live against Azure Data Factory, specify [cyan]--resource-group[/cyan], "
                "[cyan]--factory-name[/cyan], and [cyan]--subscription-id[/cyan] (or configure in .env). Falling back to mock fixture."
            )
            result = get_mock_spike_2_result()
        else:
            try:
                token_mgr = EntraTokenManager()
                cached = token_mgr.load_cached_token()
                if cached:
                    access_token = cached["access_token"]
                    auth_desc = f"Active Token Session ({cached.get('username')})"
                else:
                    token_data = token_mgr.acquire_token_device_code()
                    access_token = token_data["access_token"]
                    auth_desc = f"Fresh Session ({token_data.get('username')})"

                console.print(f"[bold green][SUCCESS][/bold green] Connected to ARM ({auth_desc})")
                console.print(f"[bold cyan]Extracting & Normalizing {factory} metadata from {rg}...[/bold cyan]")

                extractor = AdfMetadataExtractor(access_token=access_token, subscription_id=sub_id)
                factory_meta = extractor.extract_entire_factory(resource_group=rg, factory_name=factory)

                result = Spike2Result(
                    factories=[factory_meta],
                    total_factories=1,
                    total_pipelines=len(factory_meta.pipelines),
                    total_activities=sum(len(p.activities) for p in factory_meta.pipelines),
                    total_datasets=len(factory_meta.datasets),
                    total_linked_services=len(factory_meta.linked_services),
                    total_triggers=len(factory_meta.triggers),
                    total_data_flows=len(factory_meta.data_flows),
                )
            except Exception as e:
                console.print(f"[bold red]❌ Spike 2 Live Extraction Failed:[/bold red] {e}")
                console.print("[dim]Falling back to mock fixture for validation...[/dim]")
                result = get_mock_spike_2_result()

    for f in result.factories:
        display_factory_metadata(f)

    display_kpi_summary(result)

    out_dir = Path("spikes/spike_2_discovery/output")
    out_path = save_output_artifact(result, out_dir)
    console.print(f"[dim]Normalized JSON artifact saved to: [cyan]{out_path.resolve()}[/cyan][/dim]\n")
    return result


def main():
    parser = argparse.ArgumentParser(description="PIE Phase 2 - Spike 2: ADF Metadata Extraction & Schema Normalization")
    parser.add_argument(
        "--mode",
        choices=["default", "device_code", "interactive", "cli", "service_principal", "mock"],
        default="device_code",
        help="Authentication strategy (defaults to device_code for reliable browser/device login)",
    )
    parser.add_argument("--subscription-id", type=str, default=None, help="Target Azure Subscription ID")
    parser.add_argument("--resource-group", type=str, default=None, help="Target Azure Resource Group")
    parser.add_argument("--factory-name", type=str, default=None, help="Target Azure Data Factory Name")
    args = parser.parse_args()

    try:
        run_spike(
            mode_override=args.mode,
            subscription_id_override=args.subscription_id,
            resource_group_override=args.resource_group,
            factory_name_override=args.factory_name,
        )
    except Exception:
        sys.exit(1)


if __name__ == "__main__":
    main()
