"""Unified Developer CLI for Platform Intelligence Engine (PIE)."""

import argparse
import sys
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt

from pie.discovery.repository import get_repository
from pie.graph.builder import GraphBuilder
from pie.graph.deletion_simulator import AssetDeletionSimulator
from pie.graph.audit_engine import AssetAuditEngine
from pie.ai.engine import PIEReasoningEngine

console = Console(force_terminal=True, legacy_windows=False)


def cmd_serve(args: argparse.Namespace) -> None:
    """Start the production FastAPI REST API server."""
    import uvicorn
    console.print(
        Panel.fit(
            f"[bold white]Starting PIE Core REST API Server on [cyan]http://{args.host}:{args.port}[/cyan][/bold white]\n"
            f"[dim]Interactive Swagger Docs: [green]http://{args.host}:{args.port}/docs[/green][/dim]",
            title="[bold green]PIE Headless Engine[/bold green]",
            border_style="green",
        )
    )
    uvicorn.run("pie.api.app:app", host=args.host, port=args.port, reload=args.reload)


def cmd_discover(args: argparse.Namespace) -> None:
    """Interactive Subscription and Factory Discovery Flow."""
    console.print(
        Panel.fit(
            "[bold white]PIE Interactive Hierarchical Discovery Flow[/bold white]\n"
            "[dim]Enumerating accessible subscriptions and targeted factory sync...[/dim]",
            title="[bold cyan]Discovery Assistant[/bold cyan]",
            border_style="cyan",
        )
    )
    repo = get_repository()
    factories = repo.list_factories()

    table = Table(title="Currently Synchronized Data Factories", border_style="cyan")
    table.add_column("Factory Name", style="bold white")
    table.add_column("Resource Group", style="dim")
    table.add_column("Subscription ID", style="dim")
    table.add_column("Pipelines", style="bold green", justify="right")
    table.add_column("Last Refreshed At", style="bold yellow")

    for f in factories:
        ts = repo.get_last_refreshed_at(f.factory_name, subscription_id=f.subscription_id)
        table.add_row(f.factory_name, f.resource_group, f.subscription_id[:12] + "...", str(len(f.pipelines)), ts or "Initial Load")

    console.print(table)


def cmd_audit(args: argparse.Namespace) -> None:
    """Run technical debt, SaaS vendor, and schedule concurrency audits."""
    repo = get_repository()
    factories = repo.list_factories()
    builder = GraphBuilder()
    for f in factories:
        builder.build_from_factory(f)

    auditor = AssetAuditEngine(builder.graph)
    debt = auditor.audit_technical_debt()
    vendors = auditor.audit_saas_vendor_ecosystem()
    heatmap = auditor.audit_schedule_concurrency()

    console.print(
        Panel.fit(
            f"[bold white]Technical Debt Summary[/bold white]\n"
            f"- [bold red]Orphan Pipelines:[/bold red] {debt.total_orphan_count}\n"
            f"- [bold yellow]Zero-Retry Fragile Activities:[/bold yellow] {debt.total_zero_retry_count}\n"
            f"- [bold cyan]SaaS Vendor Integrations:[/bold cyan] {len(vendors)} vendors\n"
            f"- [bold magenta]Peak Batch Collision Hour:[/bold magenta] {heatmap.peak_hour} ({heatmap.peak_concurrency_count} pipelines)",
            title="[bold red]Enterprise Audit Results[/bold red]",
            border_style="red",
        )
    )


def cmd_simulate(args: argparse.Namespace) -> None:
    """Run what-if deletion simulator for a target dataset or asset."""
    repo = get_repository()
    factories = repo.list_factories()
    builder = GraphBuilder()
    for f in factories:
        builder.build_from_factory(f)

    simulator = AssetDeletionSimulator(builder.graph)
    report = simulator.simulate_dataset_deletion(args.asset)

    table = Table(title=f"What-If Deletion Assessment: {args.asset}", border_style="red")
    table.add_column("Metric / Property", style="dim")
    table.add_column("Value", style="bold white")
    table.add_row("Risk Rating", f"[{'red' if report.risk_score >= 70 else 'yellow'}]{report.risk_level.value.upper()} ({report.risk_score}/100)[/]")
    table.add_row("Direct Broken Readers", str(len(report.broken_readers)))
    table.add_row("Direct Broken Writers", str(len(report.broken_writers)))
    table.add_row("Affected Pipelines", ", ".join(report.affected_pipelines) or "None")

    console.print(table)
    console.print("\n[bold yellow]Recommended Remediation Steps:[/bold yellow]")
    for step in report.remediation_steps:
        console.print(f"  - {step}")


def cmd_clear(args: argparse.Namespace) -> None:
    """Clear all loaded factories from the in-memory repository."""
    repo = get_repository()
    count = len(repo.list_factories())
    repo._factories.clear()
    repo._pipeline_index.clear()
    repo._last_refreshed_at.clear()
    console.print(f"[green]Workspace cleared - removed {count} factory instance(s) from memory.[/green]")


def cmd_chat(args: argparse.Namespace) -> None:
    """Launch interactive conversational AI terminal session."""
    repo = get_repository()
    factories = repo.list_factories()
    builder = GraphBuilder()
    for f in factories:
        builder.build_from_factory(f)

    engine = PIEReasoningEngine(graph=builder.graph)
    console.print(
        Panel.fit(
            "[bold white]Platform Intelligence Engine (PIE) - Terminal Chat Assistant[/bold white]\n"
            "[dim]Ask architectural, debugging, deletion, or modernization questions (type 'exit' to quit)[/dim]",
            title="[bold green]Interactive Chat[/bold green]",
            border_style="green",
        )
    )

    while True:
        try:
            q = Prompt.ask("\n[bold yellow]Ask PIE[/bold yellow]")
            if q.strip().lower() in ["exit", "quit", "q"]:
                break
            resp = engine.ask(q)
            console.print(
                f"\n[dim]Intent: {resp.detected_intent.value} | Entity: {resp.target_asset} | Grounding: {resp.grounding_score}% | Latency: {resp.latency_ms}ms[/dim]"
            )
            console.print(Panel(resp.response_markdown, border_style="green"))
        except (KeyboardInterrupt, EOFError):
            break


def main() -> None:
    """CLI entrypoint dispatcher."""
    parser = argparse.ArgumentParser(prog="pie", description="Platform Intelligence Engine (PIE) CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # serve
    p_serve = subparsers.add_parser("serve", help="Start the FastAPI REST API server")
    p_serve.add_argument("--host", default="127.0.0.1", help="Host address")
    p_serve.add_argument("--port", type=int, default=8000, help="Port number")
    p_serve.add_argument("--reload", action="store_true", help="Enable auto-reload")

    # discover
    subparsers.add_parser("discover", help="Interactive subscription and factory discovery")

    # audit
    subparsers.add_parser("audit", help="Run technical debt and governance audits")

    # simulate-deletion
    p_sim = subparsers.add_parser("simulate-deletion", help="Simulate asset deletion risk")
    p_sim.add_argument("asset", help="Target asset name (e.g. DataLakeCsv)")

    # chat
    subparsers.add_parser("chat", help="Launch conversational AI terminal assistant")

    # clear
    subparsers.add_parser("clear", help="Clear all loaded factories from in-memory workspace")

    args = parser.parse_args()

    if args.command == "serve":
        cmd_serve(args)
    elif args.command == "discover":
        cmd_discover(args)
    elif args.command == "audit":
        cmd_audit(args)
    elif args.command == "simulate-deletion":
        cmd_simulate(args)
    elif args.command == "chat":
        cmd_chat(args)
    elif args.command == "clear":
        cmd_clear(args)


if __name__ == "__main__":
    main()
