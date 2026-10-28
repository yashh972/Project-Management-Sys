"""FastAPI entrypoint for the Agile CodeBoard ML service."""

from __future__ import annotations

import time
import uuid

from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse

from . import __version__
from .config import get_settings
from .routers import assignments, assistant, forecasts, health, models, predictions, search, training

settings = get_settings()

app = FastAPI(
    title="Agile CodeBoard ML",
    description="Risk prediction, sprint forecasting and assignee recommendations for Phproject.",
    version=__version__,
)

app.include_router(health.router)
app.include_router(predictions.router)
app.include_router(forecasts.router)
app.include_router(assignments.router)
app.include_router(models.router)
app.include_router(training.router)
app.include_router(search.router)
app.include_router(assistant.router)

_STARTED_AT = time.time()


@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:16]
    response = await call_next(request)
    response.headers["x-request-id"] = request_id
    response.headers["x-service-version"] = __version__
    return response


@app.get("/")
def root() -> dict:
    return {
        "service": "phproject-ml",
        "version": __version__,
        "environment": settings.env,
        "docs": "/docs",
        "health": "/healthz",
    }


@app.get("/metrics", response_class=PlainTextResponse)
def metrics() -> str:
    uptime = time.time() - _STARTED_AT
    lines = [
        "# HELP phproject_ml_up Whether the service process is running.",
        "# TYPE phproject_ml_up gauge",
        "phproject_ml_up 1",
        "# HELP phproject_ml_uptime_seconds Process uptime in seconds.",
        "# TYPE phproject_ml_uptime_seconds gauge",
        f"phproject_ml_uptime_seconds {uptime:.1f}",
        "# HELP phproject_ml_info Build information.",
        "# TYPE phproject_ml_info gauge",
        f'phproject_ml_info{{version="{__version__}",environment="{settings.env}"}} 1',
    ]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)
