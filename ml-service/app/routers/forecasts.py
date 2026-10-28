"""Sprint forecasting endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ..auth import require_internal_token
from ..forecasting import forecast_sprint
from ..schemas import ForecastRequest, ForecastResponse

router = APIRouter(prefix="/v1/forecast", tags=["forecast"], dependencies=[Depends(require_internal_token)])


@router.post("/sprint", response_model=ForecastResponse)
def sprint_forecast(payload: ForecastRequest) -> ForecastResponse:
    try:
        return ForecastResponse(
            **forecast_sprint(
                sprint_id=payload.sprint_id,
                simulations=payload.simulations,
                capacity_hours_per_day=payload.capacity_hours_per_day,
            )
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
