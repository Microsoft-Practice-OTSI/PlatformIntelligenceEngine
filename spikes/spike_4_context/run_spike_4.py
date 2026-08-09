"""Platform Intelligence Engine (PIE) - Phase 2 Technical Discovery
Spike 4: Context Builder, Subgraph Extractor & Token Budgeting Engine
"""

import json
import argparse
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.markdown import Markdown

from pie.core.logging import get_logger
from pie.discovery.models import Spike2Result
from pie.graph.builder import KnowledgeGraphBuilder
from pie.context.models import TokenBudget, Spike4Result
from pie.context.builder import ContextBuilder
from spikes.spike_2_discovery.mock_adf_fixture import get_mock_spike_2_result

logger = get_logger(__name__)
console = Console()


def load_factory_metadata() -> Spike2Result:
    """Load metadata from live Spike 2 output or fall back to enterprise mock fixture."""
    live_file = Path("spikes/spike_2_discovery/output/spike_2_metadata.json")
    if live_file.exists():
        try:
            with open(live_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            spike2_res = Spike2Result.model_validate(data)
            logger.info(f"[green][OK][/green] Loaded live ADF metadata from: [cyan]{live_file.resolve()}[/cyan]")
            return spike2_res
        except Exception as e:
            logger.warning(f"Failed parsing live metadata JSON ({e}), using mock fixture.")

    logger.info("[dim]Using enterprise mock ADF fixture for Context Builder.[/dim]")
    return get_mock_spike_2_result()


def main():
    parser = argparse.ArgumentParser(description="PIE Spike 4: Context Builder & Token Budgeting Engine")
    parser.add_argument("--asset", type=str, default="RailCarRx_InvoiceLoad", help="Target asset (pipeline, dataset, linked service)")
    parser.add_argument("--budget", type=int, default=4000, help="Maximum token budget for prompt payload")
    parser.add_argument("--hops", type=int, default=2, help="Subgraph neighborhood radius")
    args = parser.parse_args()

    console.print(
        Panel.fit(
            "[bold white]Platform Intelligence Engine (PIE) - Phase 2 Technical Discovery[/bold white]\n"
            "[bold cyan]Spike 4: Context Builder, Subgraph Extractor & Token Budgeting Engine[/bold cyan]\n"
            "[dim]Deterministic Subgraph Isolation, Schema Compression, Token Optimization & LLM Payloads[/dim]",
            border_style="cyan",
        )
    )

    # 1. Load Data Factory Metadata & Build Graph
    spike2_res = load_factory_metadata()
    factory_meta = spike2_res.factories[0]
    graph = KnowledgeGraphBuilder.build(factory_meta)

    # 2. Initialize Context Builder
    context_builder = ContextBuilder(graph)
    budget = TokenBudget(max_tokens=args.budget)

    # 3. Construct Token-Budgeted Context Package
    context_package = context_builder.build_context_package(
        target_asset_name=args.asset,
        budget=budget,
        max_hops=args.hops,
    )

    # 4. Render Token Savings & Compression Dashboard
    tbl = Table(title=f"Token Budgeting & Compression Matrix: {context_package.target_asset_name}", header_style="bold cyan", border_style="dim")
    tbl.add_column("Metric", style="bold white")
    tbl.add_column("Value", style="bold yellow")
    tbl.add_column("Impact / Performance Benefit", style="green")

    tbl.add_row("Target Entity", f"{context_package.target_asset_name} ({context_package.target_asset_type})", "Focal point of context package")
    tbl.add_row("Configured Token Budget", f"{context_package.token_budget:,} tokens", "Hard ceiling to prevent context truncation")
    tbl.add_row("Raw Uncompressed JSON Tokens", f"{context_package.raw_uncompressed_tokens:,} tokens", "Raw subgraph with UI visual layout & GUID noise")
    tbl.add_row("Compressed Context Package", f"{context_package.compressed_context_tokens:,} tokens", "High-density semantic markdown for LLMs")
    tbl.add_row("Token Savings Ratio", f"{context_package.compression_ratio}% reduction", f"Saved {context_package.raw_uncompressed_tokens - context_package.compressed_context_tokens:,} tokens per call")

    console.print(tbl)
    console.print()

    # 5. Render LLM-Ready Prompt Markdown
    console.print(Panel(Markdown(context_package.full_prompt_payload_md), title="Generated LLM Prompt Context Payload", border_style="green"))
    console.print()

    # 6. Save Spike 4 Artifacts
    result = Spike4Result(
        target_asset=args.asset,
        budget_configured=args.budget,
        raw_tokens=context_package.raw_uncompressed_tokens,
        compressed_tokens=context_package.compressed_context_tokens,
        token_savings_pct=context_package.compression_ratio,
        context_package=context_package,
    )

    out_json = Path("spikes/spike_4_context/output/spike_4_context.json")
    out_md = Path("spikes/spike_4_context/output/spike_4_context.md")
    out_json.parent.mkdir(parents=True, exist_ok=True)

    with open(out_json, "w", encoding="utf-8") as f:
        f.write(result.model_dump_json(indent=2))

    with open(out_md, "w", encoding="utf-8") as f:
        f.write(context_package.full_prompt_payload_md)

    console.print(f"[bold green][SUCCESS][/bold green] Spike 4 Context Artifacts Persisted:")
    console.print(f"  • JSON Package: [cyan]{out_json.resolve()}[/cyan]")
    console.print(f"  • Markdown Payload: [cyan]{out_md.resolve()}[/cyan]")


if __name__ == "__main__":
    main()
