"""Monte Carlo sprint delivery forecasting.

This is the first, deliberately simple version: sample cycle times from the
historical distribution, honour dependencies, and queue work per assignee. The
interfaces and stored assumptions are designed so the calibrated/quantile model
can replace the sampler without touching the API or the UI.
"""

from __future__ import annotations

from datetime import UTC, datetime

import numpy as np
import pandas as pd

from .cycle import cycle_service
from .features import load_dependencies, load_issues, load_sprints, median_hours


def _topological_order(task_ids: list[int], deps: dict[int, list[int]]) -> tuple[list[int], bool]:
    remaining = set(task_ids)
    order: list[int] = []
    had_cycle = False

    while remaining:
        ready = [task for task in remaining if all(dep not in remaining for dep in deps.get(task, []))]
        if not ready:
            had_cycle = True
            ready = sorted(remaining)
        order.extend(ready)
        remaining -= set(ready)

    return order, had_cycle


def forecast_sprint(sprint_id: int, simulations: int = 5000, capacity_hours_per_day: float = 8.0) -> dict:
    sprints = load_sprints()
    sprint = sprints[sprints["id"] == sprint_id]
    if sprint.empty:
        raise KeyError(f"Sprint {sprint_id} not found")
    sprint = sprint.iloc[0]

    now = datetime.now(UTC).replace(tzinfo=None)
    df = load_issues()
    tasks = df[
        (df["sprint_id"] == sprint_id)
        & (df["status_closed"] == 0)
        & (df["type_role"] != "project")
    ].copy()

    if tasks.empty:
        end = pd.Timestamp(sprint["end_date"]).date().isoformat()
        return {
            "sprint_id": int(sprint_id),
            "sprint_name": str(sprint["name"]),
            "start_date": str(sprint["start_date"]),
            "end_date": str(sprint["end_date"]),
            "open_tasks": 0,
            "probability_on_time": 1.0,
            "p50_date": end,
            "p85_date": end,
            "p95_date": end,
            "expected_days": 0.0,
            "drivers": [],
            "assumptions": {"simulations": simulations, "open_tasks": 0},
            "generated_at": now.replace(tzinfo=UTC),
        }

    task_ids = [int(value) for value in tasks["id"].tolist()]
    dependencies = load_dependencies()
    deps: dict[int, list[int]] = {}
    dependency_count = 0
    for row in dependencies[dependencies["issue_id"].isin(task_ids)].itertuples(index=False):
        deps.setdefault(int(row.issue_id), []).append(int(row.dependency_id))
        dependency_count += 1

    order, had_cycle = _topological_order(task_ids, deps)
    index = {task_id: position for position, task_id in enumerate(task_ids)}
    ordered_index = [index[task_id] for task_id in order]

    history = cycle_service.snapshot().durations
    rng = np.random.default_rng(42)
    if len(history) >= 5:
        sampled = rng.choice(history, size=(simulations, len(task_ids)), replace=True)
    else:
        sampled = rng.lognormal(mean=np.log(4.0), sigma=0.8, size=(simulations, len(task_ids)))
    sampled = np.clip(sampled, 0.25, 45.0)

    fallback_hours = median_hours(df)
    task_rows = tasks.set_index("id")
    scales = np.ones(len(task_ids), dtype=float)
    min_days = np.zeros(len(task_ids), dtype=float)
    for position, task_id in enumerate(task_ids):
        hours = task_rows.loc[task_id, "hours_total"]
        if pd.notna(hours) and float(hours) > 0:
            hours = float(hours)
            scales[position] = float(np.clip(hours / fallback_hours, 0.5, 3.0))
            min_days[position] = hours / max(capacity_hours_per_day, 0.5)
    sampled *= scales
    sampled = np.maximum(sampled, min_days)

    finish_days = np.zeros((simulations, len(task_ids)), dtype=float)

    for sim in range(simulations):
        user_available: dict[int, float] = {}
        task_finish: dict[int, float] = {}

        for position in ordered_index:
            task_id = task_ids[position]
            start = 0.0

            for dependency_id in deps.get(task_id, []):
                if dependency_id in task_finish:
                    start = max(start, task_finish[dependency_id])

            owner = task_rows.loc[task_id, "owner_id"]
            owner_key = int(owner) if pd.notna(owner) else 0
            if owner_key:
                start = max(start, user_available.get(owner_key, 0.0))

            duration = float(sampled[sim, position])
            finish = start + duration
            task_finish[task_id] = finish
            finish_days[sim, position] = finish
            if owner_key:
                user_available[owner_key] = finish

    end_days = finish_days.max(axis=1)
    sprint_end = pd.Timestamp(sprint["end_date"]) + pd.Timedelta(1, unit="D") - pd.Timedelta(1, unit="s")
    sprint_end_days = max(0.0, (sprint_end - pd.Timestamp(now)).total_seconds() / 86400)
    probability = float((end_days <= sprint_end_days).mean())

    def date_for(quantile: float) -> str:
        return (pd.Timestamp(now) + pd.Timedelta(float(np.quantile(end_days, quantile)), unit="D")).date().isoformat()

    # Probability that a task is the one that finishes last in a simulation.
    last_index = finish_days.argmax(axis=1)
    criticality = np.bincount(last_index, minlength=len(task_ids)) / simulations

    driver_positions = np.argsort(criticality)[-5:][::-1]
    drivers = []
    for position in driver_positions:
        if criticality[position] <= 0:
            continue
        task_id = task_ids[position]
        row = task_rows.loc[task_id]
        median_finish = float(np.median(finish_days[:, position]))
        drivers.append(
            {
                "issue_id": int(task_id),
                "name": str(row["name"]),
                "owner": None if pd.isna(row["owner_name"]) else str(row["owner_name"]),
                "median_finish": (pd.Timestamp(now) + pd.Timedelta(median_finish, unit="D")).date().isoformat(),
                "criticality": round(float(criticality[position]), 3),
            }
        )

    assumptions: dict[str, str | float | int] = {
        "simulations": simulations,
        "historical_cycle_samples": int(len(history)),
        "dependencies": dependency_count,
        "capacity_hours_per_day": capacity_hours_per_day,
        "duration_source": "historical_cycle_times" if len(history) >= 5 else "lognormal_default",
        "dependencies_outside_sprint": "assumed_complete",
        "dependency_cycle": "parallel" if had_cycle else "none",
        "seed": 42,
    }
    unassigned = int(tasks["owner_id"].isna().sum())
    if unassigned:
        assumptions["unassigned_tasks"] = unassigned

    return {
        "sprint_id": int(sprint_id),
        "sprint_name": str(sprint["name"]),
        "start_date": str(sprint["start_date"]),
        "end_date": str(sprint["end_date"]),
        "open_tasks": int(len(tasks)),
        "probability_on_time": round(probability, 4),
        "p50_date": date_for(0.50),
        "p85_date": date_for(0.85),
        "p95_date": date_for(0.95),
        "expected_days": round(float(end_days.mean()), 2),
        "drivers": drivers,
        "assumptions": assumptions,
        "generated_at": now.replace(tzinfo=UTC),
    }
