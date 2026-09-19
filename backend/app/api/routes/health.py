"""Health-check router."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import get_settings

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    version: str
    timestamp: str


@router.get("/health", response_model=HealthResponse, tags=["health"])
async def health_check() -> HealthResponse:
    """Return service liveness status."""
    settings = get_settings()
    return HealthResponse(
        status="ok",
        version=settings.app_version,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
