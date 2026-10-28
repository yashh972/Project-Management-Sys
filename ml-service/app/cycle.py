"""Cycle-time estimates used by the forecast and the issue form."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime

import numpy as np

from .config import get_settings
from .features import load_issues

DEFAULT_P50 = 5.0
DEFAULT_P85 = 10.0


@dataclass
class CycleSnapshot:
    durations: np.ndarray = field(default_factory=lambda: np.array([], dtype=float))
    by_type: dict[str, np.ndarray] = field(default_factory=dict)
    version: str = "cycle-empirical-v0"
    loaded_at: float = 0.0


class CycleService:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._snapshot = CycleSnapshot()

    def snapshot(self, force: bool = False) -> CycleSnapshot:
        settings = get_settings()
        with self._lock:
            if not force and (time.time() - self._snapshot.loaded_at) < settings.risk_cache_seconds:
                return self._snapshot

            df = load_issues()
            closed = df[(df["status_closed"] == 1) & df["closed_dt"].notna()].copy()
            start = closed["start_dt"].fillna(closed["created_dt"])
            days = ((closed["closed_dt"] - start).dt.total_seconds() / 86400).clip(lower=0.25)
            days = days.replace([np.inf, -np.inf], np.nan).dropna()

            by_type: dict[str, np.ndarray] = {}
            for role, group in closed.assign(days=days).groupby("type_role"):
                values = group["days"].dropna().to_numpy(dtype=float)
                if len(values) >= 8:
                    by_type[str(role)] = values

            self._snapshot = CycleSnapshot(
                durations=days.to_numpy(dtype=float),
                by_type=by_type,
                version=f"cycle-empirical-{datetime.now(UTC):%Y%m%d}",
                loaded_at=time.time(),
            )
            return self._snapshot

    def predict(self, issue_id: int) -> dict:
        snapshot = self.snapshot()
        df = load_issues()
        row = df[df["id"] == issue_id]
        if row.empty:
            raise KeyError(f"Issue {issue_id} not found")

        issue = row.iloc[0]
        values = snapshot.by_type.get(str(issue["type_role"]), snapshot.durations)
        if len(values) < 5:
            p50, p85 = DEFAULT_P50, DEFAULT_P85
            sample_size = len(values)
        else:
            p50 = float(np.quantile(values, 0.5))
            p85 = float(np.quantile(values, 0.85))
            sample_size = int(len(values))

        now = datetime.now(UTC).replace(tzinfo=None)
        return {
            "issue_id": int(issue_id),
            "p50_days": round(max(0.25, p50), 2),
            "p85_days": round(max(p50, p85), 2),
            "expected_days": round(float(np.mean(values)) if len(values) else p50, 2),
            "sample_size": sample_size,
            "model_version": snapshot.version,
            "generated_at": now.replace(tzinfo=UTC),
        }


cycle_service = CycleService()
