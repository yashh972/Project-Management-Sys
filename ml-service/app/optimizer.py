"""Prescriptive sprint assignment.

The optimizer chooses owners for a sprint as a constrained assignment problem:
one owner per task, per-person capacity, WIP limits, and a score built from
trailing reliability, tag experience, spare capacity and owner stability.
OR-Tools CP-SAT solves it exactly for normal sprint sizes; a deterministic
greedy pass keeps the feature usable when the solver is unavailable.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import numpy as np
import pandas as pd

from .assignment import _candidate_stats, read_task_tags
from .config import get_settings
from .db import execute, read_df
from .features import load_issues, load_user_tags, load_users, median_hours

W_FIT = 0.55
W_CAPACITY = 0.25
W_TAGS = 0.10
W_STABILITY = 0.10
LIMITED_PENALTY = 15.0


def _task_hours(row: pd.Series | dict, fallback: float) -> float:
    for key in ("hours_remaining", "hours_total"):
        value = row.get(key)
        if value is not None and not pd.isna(value) and float(value) > 0:
            return float(value)
    return fallback


def _committed_load(df: pd.DataFrame, task_ids: set[int], users: list[int]) -> dict[int, float]:
    open_ = df[(df["status_closed"] == 0) & ~df["id"].isin(task_ids)]
    fallback = median_hours(df)
    load = {user_id: 0.0 for user_id in users}
    for row in open_.itertuples(index=False):
        if pd.isna(row.owner_id):
            continue
        owner = int(row.owner_id)
        if owner in load:
            load[owner] += _task_hours(row._asdict(), fallback)
    return load


def _leave_hours(sprint_start: str, sprint_end: str, users: list[int]) -> dict[int, float]:
    out = {user_id: 0.0 for user_id in users}
    try:
        rows = read_df(
            "SELECT user_id, SUM(hours) AS hours FROM user_availability "
            "WHERE date BETWEEN :start AND :end GROUP BY user_id",
            {"start": sprint_start, "end": sprint_end},
        )
        for row in rows.itertuples(index=False):
            if int(row.user_id) in out:
                out[int(row.user_id)] = float(row.hours or 0)
    except Exception:
        pass
    return out


def _skills() -> dict[int, set[str]]:
    try:
        rows = read_df("SELECT user_id, LOWER(skill) AS skill FROM user_skill")
    except Exception:
        return {}
    out: dict[int, set[str]] = {}
    for row in rows.itertuples(index=False):
        out.setdefault(int(row.user_id), set()).add(str(row.skill))
    return out


def _score(
    task: pd.Series,
    task_tags: set[str],
    stat: dict,
    committed_hours: float,
    capacity_hours: float,
    task_hours: float,
    skills: set[str],
) -> tuple[float, list[str]]:
    projected = committed_hours + task_hours
    capacity_fit = max(0.0, 1.0 - projected / max(capacity_hours, 1.0))
    overlap = len(task_tags & stat["tags"]) / len(task_tags) if task_tags else 0.0
    skill_overlap = len(task_tags & skills) / len(task_tags) if task_tags and skills else 0.0
    stability = 1.0 if pd.notna(task.get("owner_id")) and int(task.get("owner_id")) == int(stat["user"].id) else 0.0

    score = 100.0 * (
        W_FIT * stat["on_time"]
        + W_CAPACITY * capacity_fit
        + W_TAGS * max(overlap, skill_overlap)
        + W_STABILITY * stability
    )
    if stat["n"] < 3:
        score -= LIMITED_PENALTY
    score = float(np.clip(score, 0.0, 100.0))

    reasons = [
        f"{stat['on_time'] * 100:.0f}% on-time on {stat['n']} closed tasks"
        if stat["n"]
        else "No closed-task history",
        f"{committed_hours:.0f}h committed + {task_hours:.0f}h task",
    ]
    if overlap > 0 or skill_overlap > 0:
        reasons.append(f"Relevant experience: {', '.join(sorted(task_tags & (stat['tags'] | skills))[:3])}")
    if stability:
        reasons.append("Current owner (stability bonus)")
    if stat["n"] < 3:
        reasons.append("Limited history")
    return score, reasons


def _baseline(tasks: pd.DataFrame, scores: dict[tuple[int, int], float]) -> dict:
    assigned = 0
    weighted = 0.0
    total_hours = 0.0
    for task in tasks.itertuples(index=False):
        if pd.isna(task.owner_id):
            continue
        owner = int(task.owner_id)
        score = scores.get((int(task.id), owner), 0.0)
        hours = _task_hours(task._asdict(), 4.0)
        assigned += 1
        weighted += score * hours
        total_hours += hours
    return {
        "assigned": assigned,
        "expected_fit": round(weighted / total_hours, 2) if total_hours else 0.0,
        "unassigned": int(len(tasks) - assigned),
    }


def _cp_sat(
    task_ids: list[int],
    user_ids: list[int],
    task_hours: dict[int, float],
    committed: dict[int, float],
    leave: dict[int, float],
    capacity_hours: float,
    max_wip: int,
    scores: dict[tuple[int, int], float],
    fairness_cap: float | None,
    time_limit_seconds: float,
) -> dict[int, int] | None:
    try:
        from ortools.sat.python import cp_model
    except Exception:
        return None

    try:
        model = cp_model.CpModel()
        variables: dict[tuple[int, int], cp_model.IntVar] = {}
        for task_id in task_ids:
            for user_id in user_ids:
                variables[(task_id, user_id)] = model.NewBoolVar(f"x_{task_id}_{user_id}")
            model.AddExactlyOne(variables[(task_id, user_id)] for user_id in user_ids)

        for user_id in user_ids:
            capacity = max(1.0, capacity_hours - leave.get(user_id, 0.0))
            load = model.NewIntVar(0, int(capacity * 100), f"load_{user_id}")
            model.Add(
                load
                == int(committed.get(user_id, 0.0) * 100)
                + sum(
                    int(round(task_hours[task_id] * 100)) * variables[(task_id, user_id)]
                    for task_id in task_ids
                )
            )
            model.Add(load <= int(capacity * 100))
            if fairness_cap is not None:
                model.Add(load <= int(fairness_cap * 100))
            model.Add(sum(variables[(task_id, user_id)] for task_id in task_ids) <= max_wip)

        model.Maximize(
            sum(
                int(round(scores[(task_id, user_id)] * 100)) * variables[(task_id, user_id)]
                for task_id in task_ids
                for user_id in user_ids
            )
        )

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = max(0.5, min(30.0, time_limit_seconds))
        solver.parameters.num_search_workers = 4
        status = solver.Solve(model)
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return None

        chosen: dict[int, int] = {}
        for task_id in task_ids:
            for user_id in user_ids:
                if solver.Value(variables[(task_id, user_id)]) == 1:
                    chosen[task_id] = user_id
                    break
        return chosen or None
    except Exception:
        return None


def _record_run(sprint_id: int, result: dict, constraints: dict, baseline: dict) -> None:
    try:
        execute(
            """
            INSERT INTO assignment_run
                (sprint_id, created_at, objective, constraints_json, result_json, baseline_json)
            VALUES (:sprint_id, :created_at, :objective, :constraints, :result, :baseline)
            """,
            {
                "sprint_id": sprint_id,
                "created_at": datetime.now(UTC).replace(tzinfo=None),
                "objective": result["solver"],
                "constraints": json.dumps(constraints, sort_keys=True),
                "result": json.dumps(result, sort_keys=True),
                "baseline": json.dumps(baseline, sort_keys=True),
            },
        )
    except Exception:
        pass


def optimize_sprint(
    sprint_id: int,
    capacity_hours: float | None = None,
    max_wip: int = 5,
    time_limit_seconds: float = 5.0,
    fairness: bool = True,
) -> dict:
    settings = get_settings()
    capacity_hours = capacity_hours or settings.default_capacity_hours
    df = load_issues()
    tasks = df[
        (df["sprint_id"] == sprint_id)
        & (df["status_closed"] == 0)
        & (df["type_role"] != "project")
    ].copy()
    if tasks.empty:
        raise KeyError(f"Sprint {sprint_id} has no open tasks")

    users_frame = load_users()
    users_frame = users_frame[users_frame["role"] == "user"]
    user_ids = [int(value) for value in users_frame["id"].tolist()]
    if not user_ids:
        raise KeyError("No assignable users")

    task_ids = [int(value) for value in tasks["id"].tolist()]
    task_set = set(task_ids)
    fallback_hours = median_hours(df)
    committed = _committed_load(df, task_set, user_ids)
    sprint_rows = read_df("SELECT start_date, end_date FROM sprint WHERE id = :id", {"id": sprint_id})
    sprint_start = str(sprint_rows.iloc[0]["start_date"]) if not sprint_rows.empty else ""
    sprint_end = str(sprint_rows.iloc[0]["end_date"]) if not sprint_rows.empty else ""
    leave = _leave_hours(sprint_start, sprint_end, user_ids)

    stats = _candidate_stats(df, users_frame, load_user_tags())
    skills = _skills()
    tags = read_task_tags()
    scores: dict[tuple[int, int], float] = {}
    reasons: dict[tuple[int, int], list[str]] = {}

    for task in tasks.itertuples(index=False):
        task_tags = tags.get(int(task.id), set())
        hours = _task_hours(task._asdict(), fallback_hours)
        for user_id in user_ids:
            effective = max(1.0, capacity_hours - leave.get(user_id, 0.0))
            score, why = _score(
                task._asdict(),
                task_tags,
                stats[user_id],
                committed.get(user_id, 0.0),
                effective,
                hours,
                skills.get(user_id, set()),
            )
            scores[(int(task.id), user_id)] = score
            reasons[(int(task.id), user_id)] = why

    baseline = _baseline(tasks, scores)
    task_hours = {int(t.id): _task_hours(t._asdict(), fallback_hours) for t in tasks.itertuples(index=False)}
    sprint_hours = sum(task_hours.values())
    average_load = (sprint_hours + sum(committed.values())) / len(user_ids)
    fairness_cap = None
    if fairness:
        fairness_cap = min(capacity_hours, max(capacity_hours * 0.5, average_load * 1.4))

    chosen = _cp_sat(
        task_ids,
        user_ids,
        task_hours,
        committed,
        leave,
        capacity_hours,
        max_wip,
        scores,
        fairness_cap,
        time_limit_seconds,
    )
    fairness_applied = chosen is not None and fairness_cap is not None

    if chosen is None and fairness_cap is not None:
        chosen = _cp_sat(
            task_ids,
            user_ids,
            task_hours,
            committed,
            leave,
            capacity_hours,
            max_wip,
            scores,
            None,
            time_limit_seconds,
        )
        fairness_applied = False

    solver_name = "cp_sat" if chosen else "greedy"
    chosen = chosen or {}

    if not chosen:
        load = dict(committed)
        wip: dict[int, int] = {user_id: 0 for user_id in user_ids}
        ordered = tasks.sort_values(["due_dt", "priority", "id"], na_position="last")
        for task in ordered.itertuples(index=False):
            task_id = int(task.id)
            hours = _task_hours(task._asdict(), fallback_hours)
            options = [
                user_id
                for user_id in user_ids
                if load.get(user_id, 0.0) + hours <= max(1.0, capacity_hours - leave.get(user_id, 0.0))
                and wip[user_id] < max_wip
                and (
                    not fairness_applied
                    or fairness_cap is None
                    or load.get(user_id, 0.0) + hours <= fairness_cap
                )
            ]
            if not options:
                options = [
                    user_id
                    for user_id in user_ids
                    if load.get(user_id, 0.0) + hours <= max(1.0, capacity_hours - leave.get(user_id, 0.0))
                    and wip[user_id] < max_wip
                ]
            if not options:
                continue
            best = max(options, key=lambda user_id: scores[(task_id, user_id)])
            chosen[task_id] = best
            load[best] = load.get(best, 0.0) + hours
            wip[best] += 1
        solver_name = "greedy"

    names = {int(row.id): str(row.name) for row in users_frame.itertuples(index=False)}
    assignments = []
    unassigned = []
    total_hours = 0.0
    weighted_fit = 0.0
    changed = 0
    for task in tasks.itertuples(index=False):
        task_id = int(task.id)
        hours = _task_hours(task._asdict(), fallback_hours)
        if task_id not in chosen:
            unassigned.append({"issue_id": task_id, "issue_name": str(task.name), "hours": round(hours, 1)})
            continue
        user_id = chosen[task_id]
        current = int(task.owner_id) if pd.notna(task.owner_id) else None
        if current != user_id:
            changed += 1
        total_hours += hours
        weighted_fit += scores[(task_id, user_id)] * hours
        assignments.append(
            {
                "issue_id": task_id,
                "issue_name": str(task.name),
                "user_id": user_id,
                "user_name": names.get(user_id, str(user_id)),
                "score": round(scores[(task_id, user_id)], 1),
                "current_owner_id": current,
                "changed": current != user_id,
                "hours": round(hours, 1),
                "reasons": reasons[(task_id, user_id)],
            }
        )

    assignments.sort(key=lambda item: item["issue_id"])
    loads = []
    projected_by_user = dict(committed)
    for assignment in assignments:
        projected_by_user[assignment["user_id"]] = (
            projected_by_user.get(assignment["user_id"], 0.0) + assignment["hours"]
        )
    for user_id in user_ids:
        effective = max(1.0, capacity_hours - leave.get(user_id, 0.0))
        hours = projected_by_user.get(user_id, 0.0)
        loads.append(
            {
                "user_id": user_id,
                "user_name": names.get(user_id, str(user_id)),
                "hours": round(hours, 1),
                "capacity": round(effective, 1),
                "utilization": round(min(1.0, hours / effective), 3),
            }
        )

    result = {
        "sprint_id": sprint_id,
        "solver": solver_name,
        "assignments": assignments,
        "unassigned": unassigned,
        "baseline": baseline,
        "summary": {
            "tasks": len(tasks),
            "assigned": len(assignments),
            "changed": changed,
            "capacity_hours": capacity_hours,
            "max_wip": max_wip,
            "projected_hours": round(total_hours, 1),
            "expected_fit": round(weighted_fit / total_hours, 2) if total_hours else 0.0,
            "baseline_fit": baseline["expected_fit"],
            "lift": round((weighted_fit / total_hours - baseline["expected_fit"]), 2) if total_hours else 0.0,
            "fairness": fairness,
            "fairness_applied": fairness_applied,
            "fairness_cap": round(fairness_cap, 1) if fairness_cap is not None else None,
            "loads": loads,
        },
        "generated_at": datetime.now(UTC).isoformat(),
    }
    _record_run(
        sprint_id,
        result,
        {"capacity_hours": capacity_hours, "max_wip": max_wip, "fairness": fairness},
        baseline,
    )
    return result
