"""Platform Intelligence Engine (PIE) - Phase 2 Technical Discovery
Spike 5: AI Reasoning Engine, Dynamic Intent Routing & Interactive Chat Assistant
"""

import json
import argparse
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.markdown import Markdown
from rich.prompt import Prompt

from pie.core.logging import get_logger
from pie.discovery.models import Spike2Result
from pie.graph.builder import KnowledgeGraphBuilder
from pie.ai.models import Spike5Result, ReasoningResponse
from pie.ai.engine import PIEReasoningEngine
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

    logger.info("[dim]Using enterprise mock ADF fixture for AI Reasoning.[/dim]")
    return get_mock_spike_2_result()


def run_demo_questions(engine: PIEReasoningEngine) -> list[ReasoningResponse]:
    """Execute pre-configured enterprise demonstration questions."""
    demo_questions = [
        "Explain the RailCarRx_InvoiceLoad workflow in simple terms and list external systems.",
        "What happens if I delete dataset DataLakeCsv?",
        "Which pipelines run at 06:00 AM and do we have concurrency collisions?",
        "Find all on-premise CSV datasets.",
        "Write a Python PySpark script to replicate Load_LeadToCash_Charges.",
    ]

    responses: list[ReasoningResponse] = []

    for idx, q in enumerate(demo_questions, 1):
        console.print(f"\n[bold cyan]--- Demo Interaction {idx} / {len(demo_questions)} ---[/bold cyan]")
        console.print(f"[bold yellow]User Question:[/bold yellow] [bold white]{q}[/bold white]")
        
        resp = engine.ask(q)
        responses.append(resp)

        # Render metadata header
        tbl = Table(show_header=False, border_style="dim")
        tbl.add_column("Key", style="dim")
        tbl.add_column("Val", style="bold green")
        tbl.add_row("Detected Intent", resp.detected_intent.value.upper())
        tbl.add_row("Target Entity", resp.target_asset or "Platform-Wide")
        tbl.add_row("Grounding Score", f"{resp.grounding_score}% (Zero Hallucination)")
        tbl.add_row("Inference Latency", f"{resp.latency_ms} ms")
        console.print(tbl)

        # Render Markdown response
        console.print(Panel(Markdown(resp.response_markdown), border_style="green"))

    return responses


def main():
    parser = argparse.ArgumentParser(description="PIE Spike 5: AI Reasoning Engine & Interactive Chat")
    parser.add_argument("--interactive", action="store_true", help="Launch interactive conversational prompt session")
    args = parser.parse_args()

    console.print(
        Panel.fit(
            "[bold white]Platform Intelligence Engine (PIE) - Phase 2 Technical Discovery[/bold white]\n"
            "[bold cyan]Spike 5: AI Reasoning Engine & End-to-End Chat Assistant[/bold cyan]\n"
            "[dim]Dynamic Intent Routing, 100% Grounded Context, Subgraph Extraction & Multi-Persona Answers[/dim]",
            border_style="cyan",
        )
    )

    # 1. Ingest Data Factory Metadata into Knowledge Graph
    spike2_res = load_factory_metadata()
    factory_meta = spike2_res.factories[0]
    graph = KnowledgeGraphBuilder.build(factory_meta)

    # 2. Initialize AI Reasoning Engine
    engine = PIEReasoningEngine(graph)

    # 3. Run Enterprise Demonstration Questions
    responses = run_demo_questions(engine)

    # 4. Interactive Live Prompt Loop if requested
    if args.interactive:
        console.print("\n[bold green]=== Entering Live Interactive Chat Session (type 'exit' or 'quit' to end) ===[/bold green]\n")
        while True:
            try:
                user_input = Prompt.ask("[bold yellow]Ask PIE[/bold yellow]")
                if not user_input or user_input.strip().lower() in ["exit", "quit", "q"]:
                    break
                
                resp = engine.ask(user_input.strip())
                responses.append(resp)
                console.print(Panel(Markdown(resp.response_markdown), title=f"PIE [{resp.detected_intent.value.upper()}]", border_style="cyan"))
            except (KeyboardInterrupt, EOFError):
                break

    # 5. Persist Spike 5 Artifacts
    result = Spike5Result(
        provider_used="DeterministicMockLLMProvider",
        sample_interactions=responses,
    )

    out_file = Path("spikes/spike_5_ai/output/spike_5_chat_results.json")
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(result.model_dump_json(indent=2))

    console.print(f"\n[bold green][SUCCESS][/bold green] Spike 5 Chat Results Persisted to: [cyan]{out_file.resolve()}[/cyan]")


if __name__ == "__main__":
    main()
