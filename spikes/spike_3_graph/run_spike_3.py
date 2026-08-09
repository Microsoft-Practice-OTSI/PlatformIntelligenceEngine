"""Platform Intelligence Engine (PIE) - Phase 2 Technical Discovery
Spike 3: Knowledge Graph Prototype, Lineage Traversal & Deep Pipeline Storyteller
"""

import json
import argparse
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree

from pie.core.logging import get_logger
from pie.discovery.models import Spike2Result
from pie.graph.models import (
    NodeType,
    Spike3Result,
)
from pie.graph.builder import KnowledgeGraphBuilder, KnowledgeGraph
from pie.graph.traversal import GraphTraversalService
from pie.graph.storyteller import PipelineStoryteller
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

    logger.info("[dim]Using enterprise mock ADF fixture for Knowledge Graph.[/dim]")
    return get_mock_spike_2_result()


def display_pipeline_story(story: dict):
    """Render a human-readable execution story and minute activity sequence."""
    if not story.get("found"):
        console.print(f"[red]{story.get('error')}[/red]")
        return

    console.print(
        Panel(
            f"[bold cyan]Pipeline:[/bold cyan] [bold white]{story['pipeline_name']}[/bold white] (Folder: [yellow]{story['folder'] or 'Root'}[/yellow])\n\n"
            f"[bold green]Executive Workflow Story:[/bold green]\n{story['executive_summary']}",
            title=f"Pipeline Execution Story: {story['pipeline_name']}",
            border_style="cyan",
        )
    )

    # Activity Execution Sequence Table
    tbl = Table(title=f"Minute Activity Sequence for {story['pipeline_name']}", header_style="bold cyan", border_style="dim")
    tbl.add_column("Step", style="bold yellow", justify="right", width=6)
    tbl.add_column("Activity Name", style="bold white")
    tbl.add_column("Activity Type", style="cyan")
    tbl.add_column("Operation / Target / Notes", style="magenta")

    for step in story["execution_steps"]:
        called = f"[Child: {step['called_pipeline']}]" if step.get("called_pipeline") else ""
        desc = step.get("description") or called or "-"
        tbl.add_row(str(step["step_number"]), step["activity_name"], step["type"], desc)

    console.print(tbl)
    console.print()


def display_graph_summary(graph: KnowledgeGraph, traversal: GraphTraversalService):
    """Render summary table of nodes, edges, and density."""
    node_counts: dict[str, int] = {}
    for node in graph.nodes.values():
        node_counts[node.type.value] = node_counts.get(node.type.value, 0) + 1

    edge_counts: dict[str, int] = {}
    for edge in graph.edges:
        edge_counts[edge.type.value] = edge_counts.get(edge.type.value, 0) + 1

    tbl = Table(title=f"Knowledge Graph Topology: {graph.factory_name}", header_style="bold cyan", border_style="dim")
    tbl.add_column("Entity / Node Type", style="bold white")
    tbl.add_column("Node Count", style="bold green", justify="right")
    tbl.add_column("Relationship / Edge Type", style="bold yellow")
    tbl.add_column("Edge Count", style="bold magenta", justify="right")

    node_items = list(node_counts.items())
    edge_items = list(edge_counts.items())
    max_len = max(len(node_items), len(edge_items))

    for i in range(max_len):
        n_type, n_cnt = node_items[i] if i < len(node_items) else ("", "")
        e_type, e_cnt = edge_items[i] if i < len(edge_items) else ("", "")
        tbl.add_row(str(n_type), str(n_cnt), str(e_type), str(e_cnt))

    console.print(tbl)
    console.print(f"[bold]Total Vertices (Nodes):[/bold] [cyan]{len(graph.nodes)}[/cyan] | [bold]Total Directed Edges:[/bold] [magenta]{len(graph.edges)}[/magenta]\n")


def main():
    parser = argparse.ArgumentParser(description="PIE Spike 3: Knowledge Graph Prototype & Deep Activity Storyteller")
    parser.add_argument("--asset", type=str, default="RailCarRx_InvoiceLoad", help="Target asset or pipeline name")
    parser.add_argument("--story", action="store_true", default=True, help="Generate step-by-step pipeline story")
    parser.add_argument("--hops", type=int, default=4, help="Maximum traversal hop distance")
    args = parser.parse_args()

    console.print(
        Panel.fit(
            "[bold white]Platform Intelligence Engine (PIE) - Phase 2 Technical Discovery[/bold white]\n"
            "[bold cyan]Spike 3: Knowledge Graph Prototype & Deep Activity-Level Storyteller[/bold cyan]\n"
            "[dim]Lineage Tracing, Blast Radius, Deep Activity Parameters & Plain-Language Summaries[/dim]",
            border_style="cyan",
        )
    )

    # 1. Load Data Factory Metadata
    spike2_res = load_factory_metadata()
    factory_meta = spike2_res.factories[0]

    # 2. Construct In-Memory Knowledge Graph & Storyteller
    graph = KnowledgeGraphBuilder.build(factory_meta)
    traversal = GraphTraversalService(graph)
    storyteller = PipelineStoryteller(graph)

    # 3. Render Topology Summary
    display_graph_summary(graph, traversal)

    # 4. Cycle Detection
    cycles = traversal.detect_cycles()
    if cycles:
        console.print(f"[bold red]⚠️ Cycles / Loops Detected ({len(cycles)}):[/bold red]")
        for c in cycles:
            console.print(f"  [red]Cycle:[/red] {' -> '.join(c)}")
    else:
        console.print("[bold green][OK] Cycle & Loop Detection:[/bold green] Zero circular dependency loops detected across all pipelines.\n")

    # 5. Deep Pipeline Story Demonstration
    target_pipeline = args.asset if args.asset != "all" else "RailCarRx_InvoiceLoad"
    story = storyteller.explain_pipeline(target_pipeline)
    display_pipeline_story(story)

    # 6. Build and Save Spike 3 Result Artifact
    node_counts = {}
    for node in graph.nodes.values():
        node_counts[node.type.value] = node_counts.get(node.type.value, 0) + 1

    edge_counts = {}
    for edge in graph.edges:
        edge_counts[edge.type.value] = edge_counts.get(edge.type.value, 0) + 1

    report = traversal.compute_impact_report(target_pipeline)

    result = Spike3Result(
        factory_name=graph.factory_name,
        total_nodes=len(graph.nodes),
        total_edges=len(graph.edges),
        node_counts_by_type=node_counts,
        edge_counts_by_type=edge_counts,
        cycles_detected=cycles,
        sample_impact_reports=[report],
    )

    out_file = Path("spikes/spike_3_graph/output/spike_3_graph.json")
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(result.model_dump_json(indent=2))

    console.print(f"[bold green][SUCCESS][/bold green] Spike 3 Knowledge Graph & Pipeline Story Artifact Persisted to: [cyan]{out_file.resolve()}[/cyan]")


if __name__ == "__main__":
    main()
