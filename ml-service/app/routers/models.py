"""Model registry and refresh endpoints."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends

from ..auth import require_internal_token
from ..backtest import backtest_risk
from ..cycle import cycle_service
from ..risk import risk_service
from ..schemas import BacktestRequest, BacktestResponse, ModelInfo, ModelListResponse

router = APIRouter(prefix="/v1/models", tags=["models"], dependencies=[Depends(require_internal_token)])


@router.get("", response_model=ModelListResponse)
def list_models() -> ModelListResponse:
    risk = risk_service.model_info()
    cycle = cycle_service.snapshot()
    return ModelListResponse(
        models=[
            ModelInfo(**risk),
            ModelInfo(
                name="task-cycle-time",
                version=cycle.version,
                trained_at=datetime.now(UTC),
                rows=int(len(cycle.durations)),
                metrics={"samples": float(len(cycle.durations))},
                active=True,
            ),
        ]
    )


@router.post("/risk/refresh", response_model=ModelInfo)
def refresh_risk() -> ModelInfo:
    risk_service.snapshot(force=True)
    cycle_service.snapshot(force=True)
    return ModelInfo(**risk_service.model_info())


@router.post("/risk/backtest", response_model=BacktestResponse)
def risk_backtest(payload: BacktestRequest) -> BacktestResponse:
    return BacktestResponse(**backtest_risk(folds=payload.folds, min_train=payload.min_train))
