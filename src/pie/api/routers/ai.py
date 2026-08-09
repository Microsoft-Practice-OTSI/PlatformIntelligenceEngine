"""AI Reasoning, real-time SSE streaming chat, and code generation endpoints."""

import asyncio
import json
from typing import AsyncGenerator
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from pie.api.models import AIAskRequest, AIAskResponse, CodeGenRequest, CodeGenResponse
from pie.api.dependencies import get_reasoning_engine
from pie.ai.engine import PIEReasoningEngine
from pie.ai.router import QueryIntent

router = APIRouter(prefix="/ai", tags=["AI Reasoning & Engineering Assistant"])


@router.post("/ask", response_model=AIAskResponse)
async def ask_pie(
    payload: AIAskRequest,
    engine: PIEReasoningEngine = Depends(get_reasoning_engine),
) -> AIAskResponse:
    """Execute grounded AI reasoning query with deterministic context bounds."""
    resp = engine.ask(payload)
    return AIAskResponse(
        query=resp.user_query,
        detected_intent=resp.detected_intent.value.upper(),
        target_asset=resp.target_asset,
        grounding_score=resp.grounding_score,
        response_markdown=resp.response_markdown,
        latency_ms=resp.latency_ms,
        cited_assets=resp.cited_assets,
    )


@router.get("/chat/stream")
async def stream_ai_chat(
    q: str,
    request: Request,
    engine: PIEReasoningEngine = Depends(get_reasoning_engine),
) -> StreamingResponse:
    """Stream real-time Server-Sent Events (SSE) AI response tokens with disconnect detection."""

    async def event_generator() -> AsyncGenerator[str, None]:
        resp = engine.ask(q)
        words = resp.response_markdown.split(" ")

        # Yield metadata header event
        init_data = json.dumps(
            {
                "intent": resp.detected_intent.value.upper(),
                "target_asset": resp.target_asset,
                "grounding_score": resp.grounding_score,
            }
        )
        yield f"event: metadata\ndata: {init_data}\n\n"

        # Stream text tokens with realistic cadence
        for word in words:
            if await request.is_disconnected():
                break
            chunk_data = json.dumps({"token": f"{word} "})
            yield f"event: token\ndata: {chunk_data}\n\n"
            await asyncio.sleep(0.01)

        # Yield completion event
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
