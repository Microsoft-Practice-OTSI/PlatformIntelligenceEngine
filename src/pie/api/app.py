"""FastAPI Application Factory for Platform Intelligence Engine (PIE) Core REST API."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from pie.core.config import get_settings
from pie.core.exceptions import PieError
from pie.core.logging import get_logger
from pie.discovery.repository import get_repository
from pie.api.routers.auth import router as auth_router, start_callback_server, stop_callback_server
from pie.api.routers.discovery import router as discovery_router
from pie.api.routers.graph import router as graph_router
from pie.api.routers.audit import router as audit_router
from pie.api.routers.ai import router as ai_router
from pie.api.routers.settings import router as settings_router
from pie.api.routers.teams import router as teams_router

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan context manager for startup data preloading and graceful shutdown."""
    logger.info("Initializing PIE Core Platform Engine & In-Memory Repository...")
    repo = get_repository()
    cached = repo.load_cached_factories()
    logger.info(f"Restored {len(cached)} factory instance(s) from disk cache.")
    logger.info(f"PIE Ready: Preloaded {len(repo.list_factories())} factory instance(s) in-memory.")
    # Start persistent OAuth2 callback server on :8100
    print(">>> LIFESPAN: Calling start_callback_server <<<")
    start_callback_server()
    print(">>> LIFESPAN: start_callback_server returned <<<")
    yield
    stop_callback_server()
    logger.info("PIE Core Platform shutting down gracefully.")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application instance."""
    app = FastAPI(
        title="Platform Intelligence Engine (PIE) Core API",
        description=(
            "Production Headless REST API and Streaming Engine for Azure Data Factory "
            "Engineering Intelligence, Knowledge Graphs, Lineage Traversal, What-If Deletion "
            "Simulations, and Multi-Channel Teams/Web/CLI Integration."
        ),
        version="3.0.0",
        openapi_url="/api/v1/openapi.json",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # Configure CORS for Web Application Portal
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Global Exception Handlers
    @app.exception_handler(PieError)
    async def handle_pie_domain_error(request: Request, exc: PieError) -> JSONResponse:
        logger.error(f"PIE Domain Error at {request.url.path}: {exc}")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "PIE_DOMAIN_ERROR", "message": str(exc), "path": request.url.path},
        )

    @app.exception_handler(Exception)
    async def handle_unhandled_exception(request: Request, exc: Exception) -> JSONResponse:
        logger.error(f"Unhandled Exception at {request.url.path}: {exc}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "INTERNAL_SERVER_ERROR", "message": str(exc), "path": request.url.path},
        )

    # Health Check
    @app.get("/health", tags=["Health & Diagnostics"])
    async def health_check() -> dict[str, str]:
        return {"status": "HEALTHY", "service": "PIE-Core-Platform", "version": "3.0.0"}

    # Register Routers under /api/v1
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(discovery_router, prefix="/api/v1")
    app.include_router(graph_router, prefix="/api/v1")
    app.include_router(audit_router, prefix="/api/v1")
    app.include_router(ai_router, prefix="/api/v1")
    app.include_router(settings_router, prefix="/api/v1")
    app.include_router(teams_router, prefix="/api/v1")

    return app


app = create_app()
