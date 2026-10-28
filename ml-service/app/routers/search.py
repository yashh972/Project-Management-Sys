"""Duplicate / similar-issue search endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ..auth import require_internal_token
from ..schemas import SimilarRequest, SimilarResponse
from ..search import similar_issues

router = APIRouter(prefix="/v1/search", tags=["search"], dependencies=[Depends(require_internal_token)])


@router.post("/similar", response_model=SimilarResponse)
def search_similar(payload: SimilarRequest) -> SimilarResponse:
    try:
        return SimilarResponse(
            **similar_issues(issue_id=payload.issue_id, text=payload.text, top_k=payload.top_k)
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
