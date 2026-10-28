"""Feature engineering shared by the risk, cycle-time and forecast models.

Every feature is knowable at the moment a task starts. This is deliberate: the
current ``ml/run_analytics.py`` pipeline already made the same choice, and it is
the difference between a useful model and a leaking one.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import numpy as np
import pandas as pd

from .db import read_df

FEATURES = [
    "planned_hours",
    "priority",
    "is_bug",
    "window_days",
    "queue_days",
    "pressure",
    "act_dow",
    "owner_late_rate",
    "owner_load",
]

SHRINK_K = 5
DEFAULT_HOURS = 4.0


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def load_issues() -> pd.DataFrame:
    """Load the issue history in one query.

    The query intentionally uses only portable SQL so it works on MySQL and
    SQLite. Date parsing happens in pandas because SQLite returns strings.
    """
    df = read_df(
        """
        SELECT i.id,
               i.status,
               i.type_id,
               i.name,
               i.parent_id,
               i.author_id,
               i.owner_id,
               i.priority,
               i.hours_total,
               i.hours_remaining,
               i.hours_spent,
               i.created_date,
               i.closed_date,
               i.start_date,
               i.due_date,
               i.sprint_id,
               s.closed           AS status_closed,
               t.role             AS type_role,
               u.name             AS owner_name,
               u.username         AS owner_username,
               u.role             AS owner_role
        FROM issue i
        LEFT JOIN issue_status s ON s.id = i.status
        LEFT JOIN issue_type   t ON t.id = i.type_id
        LEFT JOIN user         u ON u.id = i.owner_id
        WHERE i.deleted_date IS NULL
        """
    )

    for source, target in (
        ("created_date", "created_dt"),
        ("closed_date", "closed_dt"),
        ("start_date", "start_dt"),
        ("due_date", "due_dt"),
    ):
        df[target] = pd.to_datetime(df[source], errors="coerce")

    df["status_closed"] = pd.to_numeric(df["status_closed"], errors="coerce").fillna(0).astype(int)
    df["priority"] = pd.to_numeric(df["priority"], errors="coerce").fillna(0).astype(float)
    for column in ("hours_total", "hours_remaining", "hours_spent"):
        df[column] = pd.to_numeric(df[column], errors="coerce")

    df["is_late"] = (
        (df["status_closed"] == 1)
        & df["closed_dt"].notna()
        & df["due_dt"].notna()
        & (df["closed_dt"] > df["due_dt"] + pd.Timedelta(1, unit="D"))
    ).astype(float)
    df.loc[df["status_closed"] != 1, "is_late"] = np.nan

    return df


def load_dependencies() -> pd.DataFrame:
    return read_df("SELECT issue_id, dependency_id, dependency_type FROM issue_dependency")


def load_sprints() -> pd.DataFrame:
    return read_df("SELECT id, name, start_date, end_date FROM sprint")


def load_users() -> pd.DataFrame:
    return read_df(
        """
        SELECT id, username, name, email, role
        FROM user
        WHERE deleted_date IS NULL AND role <> 'group'
        """
    )


def load_user_tags() -> dict[int, set[str]]:
    rows = read_df(
        """
        SELECT i.owner_id, LOWER(it.tag) AS tag
        FROM issue i
        JOIN issue_tag it ON it.issue_id = i.id
        WHERE i.owner_id IS NOT NULL AND i.deleted_date IS NULL
        """
    )
    out: dict[int, set[str]] = {}
    for row in rows.itertuples(index=False):
        out.setdefault(int(row.owner_id), set()).add(str(row.tag))
    return out


def median_hours(df: pd.DataFrame) -> float:
    values = df.loc[df["hours_total"] > 0, "hours_total"]
    if values.empty:
        return DEFAULT_HOURS
    median = float(values.median())
    return median if np.isfinite(median) and median > 0 else DEFAULT_HOURS


def _owner_load_frame(df: pd.DataFrame, now: datetime) -> pd.Series:
    """How many tasks each owner had open when a task started."""
    load = pd.Series(0.0, index=df.index, dtype=float)
    for _, group in df.groupby("owner_id"):
        starts = group["created_dt"].to_numpy(dtype="datetime64[ns]")
        ends = group["closed_dt"].fillna(pd.Timestamp(now)).to_numpy(dtype="datetime64[ns]")
        for idx, row in group.iterrows():
            start = np.datetime64(row["created_dt"]) if pd.notna(row["created_dt"]) else np.datetime64(now)
            load.loc[idx] = float(((starts < start) & (ends > start)).sum())
    return load


def training_frame(df: pd.DataFrame, now: datetime | None = None) -> pd.DataFrame:
    """Return closed tasks with engineered features and the ``late`` label."""
    now = now or utcnow()
    closed = df[
        (df["status_closed"] == 1)
        & df["due_dt"].notna()
        & df["closed_dt"].notna()
        & df["created_dt"].notna()
    ].copy()
    if closed.empty:
        return closed

    closed = closed.sort_values("closed_dt")
    closed["late"] = closed["is_late"].fillna(0).astype(int)

    fallback_hours = median_hours(closed)
    closed["planned_hours"] = closed["hours_total"].where(closed["hours_total"] > 0, fallback_hours)
    closed["window_days"] = (
        (closed["due_dt"] - closed["created_dt"]).dt.total_seconds() / 86400
    ).clip(lower=0.5)
    closed["queue_days"] = (
        (closed["start_dt"].fillna(closed["created_dt"]) - closed["created_dt"]).dt.total_seconds() / 86400
    ).clip(lower=0)
    closed["pressure"] = closed["planned_hours"] / closed["window_days"].clip(lower=0.5)
    closed["act_dow"] = closed["start_dt"].fillna(closed["created_dt"]).dt.dayofweek.fillna(0)
    closed["is_bug"] = (closed["type_role"] == "bug").astype(float)
    closed["owner_late_rate"] = _owner_late_rate(closed)
    closed["owner_load"] = _owner_load_frame(closed, now)

    closed[FEATURES] = closed[FEATURES].replace([np.inf, -np.inf], np.nan).fillna(0.0)
    return closed


def _owner_late_rate(closed: pd.DataFrame) -> pd.Series:
    """Trailing late rate, shrunk toward the team rate (no future leakage)."""
    team_rate = float(closed["late"].mean()) if not closed.empty else 0.2
    result = pd.Series(np.nan, index=closed.index, dtype=float)

    for _, group in closed.groupby("owner_id"):
        prior_late = 0.0
        prior_count = 0
        for idx, row in group.sort_values("closed_dt").iterrows():
            result.loc[idx] = (prior_late + team_rate * SHRINK_K) / (prior_count + SHRINK_K)
            prior_late += float(row["late"])
            prior_count += 1

    return result.fillna(team_rate)


def owner_history(df: pd.DataFrame, owner_id: int | None, before: datetime) -> tuple[float, int, int]:
    """Owner's trailing late rate, closed count and open load at ``before``."""
    closed = df[(df["status_closed"] == 1) & df["closed_dt"].notna()]
    team_rate = float(closed["is_late"].mean()) if not closed.empty else 0.2
    if not owner_id:
        return team_rate, 0, 0

    history = closed[(closed["owner_id"] == owner_id) & (closed["closed_dt"] < before)].sort_values("closed_dt")
    recent = history.tail(15)
    late_sum = float(recent["is_late"].fillna(0).sum())
    rate = (late_sum + team_rate * SHRINK_K) / (len(recent) + SHRINK_K)

    open_tasks = int(
        (
            (df["status_closed"] == 0)
            & (df["owner_id"] == owner_id)
            & (df["created_dt"] < before)
        ).sum()
    )
    return float(rate), int(len(history)), open_tasks


def open_feature_dict(
    issue: pd.Series,
    df: pd.DataFrame,
    now: datetime | None = None,
    fallback_hours: float | None = None,
) -> dict[str, Any]:
    now = now or utcnow()
    fallback_hours = fallback_hours or median_hours(df)
    planned = issue.get("hours_total")
    if pd.isna(planned) or float(planned) <= 0:
        planned = fallback_hours
    planned = float(planned)

    due = issue.get("due_dt")
    if pd.notna(due):
        window = max(0.5, (pd.Timestamp(due) + pd.Timedelta(1, unit="D") - pd.Timestamp(now)).total_seconds() / 86400)
    else:
        window = 7.0

    created = issue.get("created_dt")
    queue = max(0.0, (pd.Timestamp(now) - pd.Timestamp(created)).total_seconds() / 86400) if pd.notna(created) else 0.0

    owner_rate, owner_n, owner_load = owner_history(df, issue.get("owner_id"), now)
    act_dow = pd.Timestamp(now).dayofweek

    features = {
        "planned_hours": planned,
        "priority": float(issue.get("priority") or 0),
        "is_bug": float(issue.get("type_role") == "bug"),
        "window_days": float(window),
        "queue_days": float(queue),
        "pressure": planned / max(window, 0.5),
        "act_dow": float(act_dow),
        "owner_late_rate": float(owner_rate),
        "owner_load": float(owner_load),
    }
    features["_owner_history_n"] = owner_n
    features["_owner_load"] = owner_load
    return features
