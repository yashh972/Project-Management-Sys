"""Assignee recommendations.

This is the first slice of the prescriptive layer: a transparent ranking based
on trailing reliability, current load and tag overlap. The OR-Tools optimizer
will replace the per-task ranking while keeping this response contract.
"""

from __future__ import annotations

from datetime import UTC, datetime

import numpy as np
import pandas as pd

from .config import get_settings
from .db import read_df
from .features import load_issues, load_user_tags, load_users, median_hours

SHRINK_K = 5
W_FIT = 0.6
W_CAPACITY = 0.4
LIMITED_PENALTY = 15.0


def _candidate_stats(df: pd.DataFrame, users: pd.DataFrame, tags: dict[int, set[str]]) -> dict[int, dict]:
    closed = df[(df["status_closed"] == 1) & df["closed_dt"].notna()]
    open_ = df[df["status_closed"] == 0]
    team_rate = float(closed["is_late"].mean()) if not closed.empty else 0.2
    fallback_hours = median_hours(df)

    stats: dict[int, dict] = {}
    for user in users.itertuples(index=False):
        user_id = int(user.id)
        history = closed[closed["owner_id"] == user_id].sort_values("closed_dt")
        recent = history.tail(15)
        late = float(recent["is_late"].fillna(0).sum())
        n = int(len(history))
        late_rate = (late + team_rate * SHRINK_K) / (len(recent) + SHRINK_K)

        own_open = open_[open_["owner_id"] == user_id]
        hours = own_open["hours_remaining"].where(own_open["hours_remaining"] > 0, own_open["hours_total"])
        open_hours = float(hours.fillna(fallback_hours).sum())

        start = history["start_dt"].fillna(history["created_dt"])
        cycle = (history["closed_dt"] - start).dt.total_seconds() / 86400
        stats[user_id] = {
            "user": user,
            "n": n,
            "late_rate": float(late_rate),
            "on_time": float(1 - late_rate),
            "open_hours": open_hours,
            "open_tasks": int(len(own_open)),
            "avg_cycle": float(cycle.median()) if not cycle.empty else None,
            "tags": tags.get(user_id, set()),
        }
    return stats


def _normalized_tags(tags: list[str] | set[str]) -> set[str]:
    return {str(tag).strip().lower().lstrip("#") for tag in tags if str(tag).strip()}


def _score(
    task_tags: set[str],
    stat: dict,
    capacity_hours: float,
    task_hours: float = 0.0,
) -> tuple[float, float, list[str]]:
    projected = stat["open_hours"] + task_hours
    capacity_score = max(0.0, 1.0 - projected / max(capacity_hours, 1.0))
    overlap = 0.0
    if task_tags:
        overlap = len(task_tags & stat["tags"]) / len(task_tags)

    score = 100.0 * (W_FIT * stat["on_time"] + W_CAPACITY * capacity_score)
    score += 5.0 * overlap
    limited = stat["n"] < 3
    if limited:
        score -= LIMITED_PENALTY
    score = float(np.clip(score, 0.0, 100.0))

    reasons = [
        f"{stat['on_time'] * 100:.0f}% on-time on {stat['n']} closed tasks"
        if stat["n"]
        else "No closed-task history yet",
        f"{stat['open_hours']:.0f}h currently open",
    ]
    if overlap > 0:
        reasons.append(f"Has worked with {', '.join(sorted(task_tags & stat['tags'])[:3])}")
    if projected > capacity_hours:
        reasons.append("Projected load exceeds capacity")
    if limited:
        reasons.append("Limited history")
    return score, overlap, reasons


def _candidates(
    task_tags: set[str],
    stats: dict[int, dict],
    capacity_hours: float,
    task_hours: float,
    exclude: set[int],
    top: int,
) -> list[dict]:
    candidates = []
    for user_id, stat in stats.items():
        if user_id in exclude:
            continue
        score, overlap, reasons = _score(task_tags, stat, capacity_hours, task_hours)
        candidates.append(
            {
                "user_id": user_id,
                "name": str(stat["user"].name),
                "username": str(stat["user"].username),
                "score": round(score, 1),
                "p_on_time": round(stat["on_time"], 4),
                "open_hours": round(stat["open_hours"], 1),
                "open_tasks": stat["open_tasks"],
                "tag_overlap": round(overlap, 3),
                "limited_history": stat["n"] < 3,
                "reasons": reasons,
            }
        )

    candidates.sort(key=lambda item: item["score"], reverse=True)
    return candidates[:top]


def read_task_tags() -> dict[int, set[str]]:
    rows = read_df("SELECT issue_id, LOWER(tag) AS tag FROM issue_tag")
    out: dict[int, set[str]] = {}
    for row in rows.itertuples(index=False):
        out.setdefault(int(row.issue_id), set()).add(str(row.tag))
    return out


def _task_hours(task: pd.Series | dict, fallback: float) -> float:
    for key in ("hours_remaining", "hours_total"):
        value = task.get(key)
        if value is not None and not pd.isna(value) and float(value) > 0:
            return float(value)
    return fallback


def suggest(
    issue_id: int | None = None,
    sprint_id: int | None = None,
    draft: dict | None = None,
    top: int = 5,
) -> dict:
    settings = get_settings()
    df = load_issues()
    users = load_users()
    users = users[users["role"] == "user"]
    tags = load_user_tags()
    stats = _candidate_stats(df, users, tags)
    fallback = median_hours(df)
    now = datetime.now(UTC).replace(tzinfo=None)

    if draft is not None:
        task_tags = _normalized_tags(draft.get("tags") or [])
        exclude = {int(value) for value in (draft.get("exclude") or [])}
        task_hours = float(draft.get("hours") or fallback)
        candidates = _candidates(
            task_tags, stats, settings.default_capacity_hours, task_hours, exclude, top
        )
        return {
            "issue_id": None,
            "sprint_id": None,
            "recommendations": [
                {"issue_id": 0, "issue_name": "New task", "candidates": candidates}
            ],
            "generated_at": now.replace(tzinfo=UTC),
        }

    if issue_id is not None:
        tasks = df[df["id"] == issue_id]
        if tasks.empty:
            raise KeyError(f"Issue {issue_id} not found")
        target = {"issue_id": int(issue_id), "sprint_id": None}
    else:
        tasks = df[
            (df["sprint_id"] == sprint_id)
            & (df["status_closed"] == 0)
            & (df["type_role"] != "project")
        ].sort_values(["due_dt", "priority", "id"], na_position="last")
        if tasks.empty:
            raise KeyError(f"Sprint {sprint_id} has no open tasks")
        tasks = tasks.head(100)
        target = {"issue_id": None, "sprint_id": int(sprint_id or 0)}

    tag_rows = read_task_tags()
    recommendations = []
    for task in tasks.itertuples(index=False):
        task_tags = tag_rows.get(int(task.id), set())
        candidates = _candidates(
            task_tags,
            stats,
            settings.default_capacity_hours,
            _task_hours(task._asdict(), fallback),
            set(),
            top,
        )
        recommendations.append(
            {
                "issue_id": int(task.id),
                "issue_name": str(task.name),
                "candidates": candidates,
            }
        )

    recommendations.sort(key=lambda item: item["issue_id"])
    return {
        **target,
        "recommendations": recommendations,
        "generated_at": now.replace(tzinfo=UTC),
    }
