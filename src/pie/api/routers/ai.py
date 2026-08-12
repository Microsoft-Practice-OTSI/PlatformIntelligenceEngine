"""AI Reasoning, real-time SSE streaming chat, and code generation endpoints."""

import asyncio
import json
import time
from typing import AsyncGenerator, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import StreamingResponse

from pie.api.models import (
    AIAskRequest,
    AIAskResponse,
    ChatStreamRequest,
    CodeGenRequest,
    CodeGenResponse,
    FactoryInsightsRequest,
    FactoryInsightsResponse,
    DuplicateParameterFinding,
)
from pie.api.dependencies import (
    get_chat_session_store,
    get_current_tenant_id,
    get_reasoning_engine,
)
from pie.ai.chat_session import ChatSessionStore
from pie.ai.engine import PIEReasoningEngine, BASE_SYSTEM_INSTRUCTION
from pie.ai.models import ChatRole
from pie.ai.providers import DeterministicMockLLMProvider
from pie.core.logging import get_logger
from pie.discovery.repository import get_repository
from pie.graph.audit_engine import AssetAuditEngine
from pie.graph.builder import KnowledgeGraphBuilder

logger = get_logger(__name__)

router = APIRouter(prefix="/ai", tags=["AI Reasoning & Engineering Assistant"])

_LLM_INSIGHTS_TIMEOUT_SECONDS = 20

_STREAM_END = object()


def _next_stream_event(iterator):
    """Advance a sync generator without letting StopIteration escape the thread future."""
    try:
        return next(iterator)
    except StopIteration:
        return _STREAM_END


@router.post("/ask", response_model=AIAskResponse)
async def ask_pie(
    payload: AIAskRequest,
    engine: PIEReasoningEngine = Depends(get_reasoning_engine),
    store: ChatSessionStore = Depends(get_chat_session_store),
    x_session_token: Optional[str] = Header(default=None, alias="X-Session-Token"),
) -> AIAskResponse:
    """Execute grounded AI reasoning query with deterministic context bounds."""
    history = []
    if payload.session_id:
        store.get_or_create(x_session_token, payload.session_id, payload.factory_name or "default")
        history = store.get_history(x_session_token, payload.session_id)

    resp = engine.ask(payload, history=history)

    if payload.session_id:
        store.add_message(x_session_token, payload.session_id, ChatRole.USER, payload.query)
        store.add_message(x_session_token, payload.session_id, ChatRole.ASSISTANT, resp.response_markdown)

    return AIAskResponse(
        query=resp.user_query,
        detected_intent=resp.detected_intent.value.upper(),
        target_asset=resp.target_asset,
        grounding_score=resp.grounding_score,
        response_markdown=resp.response_markdown,
        latency_ms=resp.latency_ms,
        cited_assets=resp.cited_assets,
    )


@router.post("/chat/stream")
async def stream_ai_chat(
    payload: ChatStreamRequest,
    request: Request,
    engine: PIEReasoningEngine = Depends(get_reasoning_engine),
    store: ChatSessionStore = Depends(get_chat_session_store),
    x_session_token: Optional[str] = Header(default=None, alias="X-Session-Token"),
) -> StreamingResponse:
    """Stream real-time Server-Sent Events (SSE) AI response tokens with disconnect detection.

    Maintains conversational context server-side per chat session id.
    """

    async def event_generator() -> AsyncGenerator[str, None]:
        session_id = payload.session_id or f"chat_{uuid4().hex}"
        store.get_or_create(x_session_token, session_id, payload.factory_name or "default")
        history = store.get_history(x_session_token, session_id)
        store.add_message(x_session_token, session_id, ChatRole.USER, payload.query)

        events = engine.stream_ask(payload, history=history)
        iterator = iter(events)
        assistant_chunks: list[str] = []

        while True:
            if await request.is_disconnected():
                break
            event = await asyncio.to_thread(_next_stream_event, iterator)
            if event is _STREAM_END:
                break

            event_type = event.get("type", "message")
            data = {k: v for k, v in event.items() if k != "type"}
            if event_type == "token":
                assistant_chunks.append(event.get("token", ""))
            yield f"event: {event_type}\ndata: {json.dumps(data)}\n\n"

        if assistant_chunks:
            store.add_message(x_session_token, session_id, ChatRole.ASSISTANT, "".join(assistant_chunks))
        elif not await request.is_disconnected():
            yield f"event: done\ndata: {json.dumps({'status': 'COMPLETE'})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/generate-code", response_model=CodeGenResponse)
async def generate_modernization_code(
    payload: CodeGenRequest,
    engine: PIEReasoningEngine = Depends(get_reasoning_engine),
) -> CodeGenResponse:
    """Generate PySpark / dbt migration script from pipeline activities and schema."""
    resp = engine.ask(f"Write a {payload.target_framework} script to modernize {payload.pipeline_name}")
    return CodeGenResponse(
        pipeline_name=payload.pipeline_name,
        target_framework=payload.target_framework,
        generated_code=resp.response_markdown,
        explanation=f"Modernized PySpark translation for {payload.pipeline_name} based on ADF activity mappings.",
    )


def _deterministic_narrative(
    factory,
    dups: list[DuplicateParameterFinding],
    orphan_count: int,
    zero_retry_count: int,
    peak_hour: Optional[str],
    peak_concurrency_count: int,
) -> str:
    """Build a fully grounded fallback narrative when the LLM provider fails or times out."""
    lines = [
        f"**{factory.factory_name}** runs **{len(factory.pipelines)}** pipelines, "
        f"**{len(factory.datasets)}** datasets, **{len(factory.linked_services)}** linked services, "
        f"**{len(factory.triggers)}** triggers, and **{len(factory.global_parameters or {})}** global parameters."
    ]
    if dups:
        dup_bits = "; ".join(
            f"`{d.value}` shared by {len(d.names)} parameters ({', '.join(d.names)})"
            for d in dups[:5]
        )
        lines.append(f"Duplicate global parameter values detected: {dup_bits}.")
    if orphan_count:
        lines.append(f"**{orphan_count} orphan pipeline(s)** are not triggered by any schedule or parent pipeline and may be dead code.")
    if zero_retry_count:
        lines.append(f"**{zero_retry_count} activity(ies)** run with zero retries and are fragile to transient failures.")
    if peak_concurrency_count > 1:
        lines.append(f"Peak schedule concurrency of **{peak_concurrency_count} pipeline(s)** at `{peak_hour}` may cause throttling.")
    if len(lines) == 1:
        lines.append("No critical issues detected in the current metadata.")
    return "\n".join(lines)


@router.post("/insights", response_model=FactoryInsightsResponse)
async def get_factory_insights(
    payload: FactoryInsightsRequest,
    tenant_id: str = Depends(get_current_tenant_id),
) -> FactoryInsightsResponse:
    """Return deterministic factory findings plus a grounded AI narrative.

    The LLM call is bounded by a hard timeout and falls back to a deterministic
    narrative, so this endpoint always returns promptly and never surfaces
    a client-side timeout to the dashboard.
    """
    repo = get_repository()
    factory = repo.get_factory(payload.factory_name, tenant_id=tenant_id) if payload.factory_name else None
    if factory is None:
        factories = repo.list_factories(tenant_id=tenant_id)
        factory = factories[0] if factories else None
    if factory is None:
        raise HTTPException(status_code=404, detail="No factory synced. Complete onboarding first.")

    graph = KnowledgeGraphBuilder.build(factory)
    audit = AssetAuditEngine(graph)

    # --- Deterministic findings (source of truth) ---
    dup_findings: list[DuplicateParameterFinding] = []
    groups: dict[str, dict] = {}
    for pname, pdef in (factory.global_parameters or {}).items():
        value = pdef.get("value") if isinstance(pdef, dict) else pdef
        val = str(value or "").strip()
        if not val:
            continue
        group = groups.setdefault(val.lower(), {"value": val, "names": []})
        group["names"].append(pname)
    for group in groups.values():
        if len(group["names"]) > 1:
            dup_findings.append(
                DuplicateParameterFinding(value=group["value"], names=group["names"], count=len(group["names"]))
            )

    debt = audit.audit_technical_debt()
    concurrency = audit.audit_schedule_concurrency()

    orphan_count = debt.total_orphan_count
    zero_retry_count = debt.total_zero_retry_count
    peak_hour = concurrency.peak_hour
    peak_concurrency_count = concurrency.peak_concurrency_count

    # --- Compact, grounded prompt (never the full factory dump) ---
    prompt_lines = [
        "## FACTORY CONTEXT (100% verified Azure Data Factory metadata)",
        f"- **Factory:** `{factory.factory_name}`",
        f"- **Resource Group:** `{factory.resource_group}`",
        f"- **Location:** `{factory.location}`",
        f"- **Asset Counts:** Pipelines=`{len(factory.pipelines)}`, Datasets=`{len(factory.datasets)}`, "
        f"Linked Services=`{len(factory.linked_services)}`, Triggers=`{len(factory.triggers)}`, "
        f"Data Flows=`{len(factory.data_flows)}`, Global Parameters=`{len(factory.global_parameters or {})}`",
        f"- **Orphan Pipelines (never triggered):** `{orphan_count}`",
        f"- **Zero-Retry Fragile Activities:** `{zero_retry_count}`",
        f"- **Peak Schedule Concurrency:** `{peak_concurrency_count}` pipeline(s) at hour `{peak_hour}`",
    ]
    for d in dup_findings:
        prompt_lines.append(
            f"- **Duplicate global parameter value `{d.value}`** shared by {len(d.names)} parameters: {', '.join(d.names)}"
        )
    prompt_lines.append(
        "\nWrite a concise 'Factory Insights' summary (maximum ~120 words, short bullet points). "
        "Cover: duplicate global parameter values, orphan pipelines, fragile zero-retry activities, "
        "schedule concurrency risks, and any quick engineering wins. "
        "Ground every claim strictly in the FACTORY CONTEXT above. Do not invent assets, counts, or secrets."
    )
    prompt_payload = "\n".join(prompt_lines)

    # --- Provider with hard timeout + deterministic fallback ---
    engine = PIEReasoningEngine(graph=graph)
    provider_label = payload.model
    try:
        provider = engine._resolve_llm_provider(payload.model)
        if isinstance(provider, DeterministicMockLLMProvider):
            provider_label = "deterministic"
    except Exception as exc:
        logger.warning(f"Factory insights provider init failed ({exc}); using deterministic narrative.")
        provider = None
        provider_label = "deterministic"

    start = time.time()
    narrative = None
    if provider is not None and provider_label != "deterministic":
        async def _complete() -> str:
            return await asyncio.to_thread(
                provider.complete,
                prompt_payload,
                system_prompt=BASE_SYSTEM_INSTRUCTION,
                factory_name=factory.factory_name,
            )

        try:
            narrative = await asyncio.wait_for(_complete(), timeout=_LLM_INSIGHTS_TIMEOUT_SECONDS)
        except Exception as exc:
            logger.warning(f"Factory insights LLM timed out or failed ({exc}); returning deterministic narrative.")
    if narrative is None:
        narrative = _deterministic_narrative(
            factory, dup_findings, orphan_count, zero_retry_count, peak_hour, peak_concurrency_count
        )
        provider_label = "deterministic"
    latency_ms = round((time.time() - start) * 1000, 1)

    return FactoryInsightsResponse(
        factory_name=factory.factory_name,
        duplicate_parameters=dup_findings,
        orphan_count=orphan_count,
        orphan_pipelines=debt.orphan_pipelines,
        zero_retry_count=zero_retry_count,
        peak_hour=peak_hour,
        peak_concurrency_count=peak_concurrency_count,
        narrative=narrative,
        provider=provider_label,
        latency_ms=latency_ms,
    )
