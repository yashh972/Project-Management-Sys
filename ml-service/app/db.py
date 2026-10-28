"""Database access shared by every router and model."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache
from typing import Any

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from .config import get_settings


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    settings = get_settings()
    if settings.db_engine == "sqlite":
        return create_engine(
            settings.sqlalchemy_url,
            connect_args={"check_same_thread": False},
            pool_pre_ping=True,
            future=True,
        )

    return create_engine(
        settings.sqlalchemy_url,
        pool_pre_ping=True,
        pool_recycle=3600,
        future=True,
    )


@contextmanager
def connection() -> Iterator[Any]:
    with get_engine().connect() as conn:
        yield conn


def read_df(sql: str, params: dict[str, Any] | None = None) -> pd.DataFrame:
    with connection() as conn:
        return pd.read_sql_query(text(sql), conn, params=params or {})


def execute(sql: str, params: dict[str, Any] | None = None) -> None:
    with get_engine().begin() as conn:
        conn.execute(text(sql), params or {})


def ping() -> bool:
    with connection() as conn:
        conn.execute(text("SELECT 1"))
    return True


def reset_engine() -> None:
    """Drop the cached engine (used by tests when the database changes)."""
    engine = get_engine()
    engine.dispose()
    get_engine.cache_clear()
