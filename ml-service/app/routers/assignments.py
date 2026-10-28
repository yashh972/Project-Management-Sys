"""Assignee recommendation endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ..assignment import suggest
from ..auth import require_internal_token
from ..optimizer import optimize_sprint
from ..schemas import AssignRequest, AssignResponse, OptimizeRequest, OptimizeResponse

router = APIRouter(prefix="/v1/assign", tags=["assign"], dependencies=[Depends(require_internal_token)])


@router.post("/suggest", response_model=AssignResponse)
def assign_suggest(payload: AssignRequest) -> AssignResponse:
    try:
        return AssignResponse(
            **suggest(
                issue_id=payload.issue_id,
                sprint_id=payload.sprint_id,
                draft=payload.draft.model_dump() if payload.draft else None,
                top=payload.top,
            )
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/optimize", response_model=OptimizeResponse)
def assign_optimize(payload: OptimizeRequest) -> OptimizeResponse:
    try:
        return OptimizeResponse(
            **optimize_sprint(
                sprint_id=payload.sprint_id,
                capacity_hours=payload.capacity_hours,
                max_wip=payload.max_wip,
                time_limit_seconds=payload.time_limit_seconds,
                fairness=payload.fairness,
            )
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
