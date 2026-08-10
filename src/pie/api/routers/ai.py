"""AI Reasoning, real-time SSE streaming chat, and code generation endpoints."""

import asyncio
import json
from typing import AsyncGenerator, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import StreamingResponse

from pie.api.models import (
    AIAskRequest,
    AIAskResponse,
    ChatStreamRequest,
    CodeGenRequest,
    CodeGenResponse,
)
from pie.api.dependencies import get_chat_session_store, get_reasoning_engine
from pie.ai.chat_session import ChatSessionStore
from pie.ai.engine import PIEReasoningEngine
from pie.ai.models import ChatRole

router = APIRouter(prefix="/ai", tags=["AI Reasoning & Engineering Assistant"])

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
