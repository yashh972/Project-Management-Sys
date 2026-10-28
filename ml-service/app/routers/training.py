"""Admin training endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..auth import require_internal_token
from ..cycle import cycle_service
from ..legacy import train_legacy
from ..risk import risk_service

router = APIRouter(prefix="/v1/train", tags=["training"], dependencies=[Depends(require_internal_token)])


class TrainRequest(BaseModel):
    include_assignment: bool = True


@router.post("/analytics")
def train_analytics(payload: TrainRequest) -> dict:
    try:
        result = train_legacy(include_assignment=payload.include_assignment)
        # The batch bridge writes raw tables; invalidate in-process models so the
        # next prediction and forecast use the freshly computed history.
        risk_service.snapshot(force=True)
        cycle_service.snapshot(force=True)
        return result
    except NotImplementedError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
