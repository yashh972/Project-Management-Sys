"""Risk and cycle-time inference endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ..auth import require_internal_token
from ..cycle import cycle_service
from ..risk import risk_service
from ..schemas import (
    CycleRequest,
    CycleResponse,
    RiskBatchItem,
    RiskBatchRequest,
    RiskBatchResponse,
    RiskRequest,
    RiskResponse,
)

router = APIRouter(prefix="/v1/predict", tags=["predict"], dependencies=[Depends(require_internal_token)])


@router.post("/risk", response_model=RiskResponse)
def predict_risk(payload: RiskRequest) -> RiskResponse:
    try:
        return RiskResponse(**risk_service.predict(payload.issue_id))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/risk/batch", response_model=RiskBatchResponse)
def predict_risk_batch(payload: RiskBatchRequest) -> RiskBatchResponse:
    results = []
    for issue_id in dict.fromkeys(payload.issue_ids):
        try:
            result = risk_service.predict(issue_id)
            results.append(
                RiskBatchItem(
                    issue_id=issue_id,
                    p_late=result["p_late"],
                    risk=result["risk"],
                    explanation=result["explanation"],
                )
            )
        except (KeyError, ValueError) as exc:
            results.append(RiskBatchItem(issue_id=issue_id, error=str(exc)))
    return RiskBatchResponse(results=results)


@router.post("/cycle", response_model=CycleResponse)
def predict_cycle(payload: CycleRequest) -> CycleResponse:
    try:
        return CycleResponse(**cycle_service.predict(payload.issue_id))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
