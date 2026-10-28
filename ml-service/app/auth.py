"""Internal service authentication.

The PHP application is the only intended caller. A shared secret is sent in the
``X-Internal-Token`` header and compared in constant time. In development an
empty token is allowed so that ``uvicorn app.main:app`` works out of the box;
outside development the service refuses to serve inference requests until a
token is configured.
"""

from __future__ import annotations

import secrets

from fastapi import Header, HTTPException, status

from .config import get_settings


def require_internal_token(x_internal_token: str = Header(default="")) -> None:
    settings = get_settings()

    if not settings.internal_token:
        if settings.env in {"dev", "test"}:
            return
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ML_INTERNAL_TOKEN is not configured",
        )

    if not x_internal_token or not secrets.compare_digest(x_internal_token, settings.internal_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid internal token",
        )
