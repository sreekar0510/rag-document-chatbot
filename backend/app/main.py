"""FastAPI application factory."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import documents, health
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.middleware import RequestIDMiddleware


def create_app() -> FastAPI:
    """Build and return the configured FastAPI application."""
    settings = get_settings()
    configure_logging(debug=settings.debug)

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        docs_url=f"{settings.api_prefix}/docs",
        redoc_url=f"{settings.api_prefix}/redoc",
        openapi_url=f"{settings.api_prefix}/openapi.json",
    )

    # ── Middleware ─────────────────────────────────────────────────────────────
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Routers ────────────────────────────────────────────────────────────────
    app.include_router(health.router, prefix=settings.api_prefix)
    app.include_router(documents.router, prefix=settings.api_prefix)

    return app


app = create_app()
