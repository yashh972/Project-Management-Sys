"""Liveness and readiness endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from ..config import get_settings
from ..db import ping
from ..schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/healthz", response_model=HealthResponse)
def healthz() -> HealthResponse:
    settings = get_settings()
    try:
        ping()
        database = "ok"
        status = "ok"
        detail = None
    except Exception as exc:  # pragma: no cover - exercised by deployment checks
        database = "unavailable"
        status = "degraded"
        detail = str(exc)[:300]

    return HealthResponse(
        status=status,
        service="phproject-ml",
        version=settings.service_version,
        database=database,
        detail=detail,
    )


@router.get("/version")
def version() -> dict:
    settings = get_settings()
    return {
        "service": "phproject-ml",
        "version": settings.service_version,
        "environment": settings.env,
        "database_engine": settings.db_engine,
    }
