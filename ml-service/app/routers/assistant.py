"""Grounded project assistant endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ..assistant import ask
from ..auth import require_internal_token
from ..schemas import AskRequest, AskResponse

router = APIRouter(prefix="/v1/assistant", tags=["assistant"], dependencies=[Depends(require_internal_token)])


@router.post("/ask", response_model=AskResponse)
def assistant_ask(payload: AskRequest) -> AskResponse:
    try:
        return AskResponse(**ask(payload.question, sprint_id=payload.sprint_id))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
