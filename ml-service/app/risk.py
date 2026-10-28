"""Task late-risk model.

A calibrated logistic regression trained on the same audit-backed features as
the batch pipeline. It is deliberately small and explainable: the calibrated
probability is used for decisions, while the uncalibrated coefficients provide
per-issue explanations until SHAP lands.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import TimeSeriesSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from .config import get_settings
from .features import FEATURES, load_issues, median_hours, open_feature_dict, training_frame
from .metrics import summarize
from .registry import record_model_run

MIN_TRAINING_ROWS = 20
MIN_CALIBRATION_ROWS = 40


@dataclass
class RiskSnapshot:
    model: CalibratedClassifierCV | Pipeline | None = None
    explainer: Pipeline | None = None
    calibrated: bool = False
    version: str = "risk-heuristic-v0"
    trained_at: datetime | None = None
    rows: int = 0
    metrics: dict[str, float] = field(default_factory=dict)
    df: pd.DataFrame = field(default_factory=pd.DataFrame)
    fallback_hours: float = 4.0
    loaded_at: float = 0.0


class RiskService:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._snapshot = RiskSnapshot()

    def snapshot(self, force: bool = False) -> RiskSnapshot:
        settings = get_settings()
        with self._lock:
            fresh = (time.time() - self._snapshot.loaded_at) < settings.risk_cache_seconds
            if fresh and not force and not self._snapshot.df.empty:
                return self._snapshot

            df = load_issues()
            train = training_frame(df)
            fallback = median_hours(df)
            snapshot = RiskSnapshot(
                df=df,
                fallback_hours=fallback,
                rows=int(len(train)),
                loaded_at=time.time(),
                trained_at=datetime.now(UTC).replace(tzinfo=None),
            )

            if len(train) >= MIN_TRAINING_ROWS and train["late"].nunique() == 2:
                snapshot.explainer = self._fit_base(train)
                snapshot.model = self._calibrate(train, snapshot.explainer)
                snapshot.calibrated = isinstance(snapshot.model, CalibratedClassifierCV)
                prefix = "risk-calibrated" if snapshot.calibrated else "risk-logreg"
                snapshot.version = f"{prefix}-{snapshot.trained_at:%Y%m%d%H%M}"
                snapshot.metrics = self._metrics(train)
                record_model_run(
                    model_name="task-late-risk",
                    version=snapshot.version,
                    trained_at=snapshot.trained_at,
                    rows=len(train),
                    metrics=snapshot.metrics,
                    train=train[FEATURES + ["late"]],
                )
            else:
                snapshot.version = "risk-heuristic-v0"

            self._snapshot = snapshot
            return snapshot

    @staticmethod
    def _fit_base(train: pd.DataFrame) -> Pipeline:
        model = Pipeline(
            [
                ("scale", StandardScaler()),
                ("clf", LogisticRegression(max_iter=2000, class_weight="balanced", random_state=42)),
            ]
        )
        model.fit(train[FEATURES], train["late"])
        return model

    @staticmethod
    def _calibrate(
        train: pd.DataFrame,
        base: Pipeline,
    ) -> CalibratedClassifierCV | Pipeline:
        if len(train) < MIN_CALIBRATION_ROWS or train["late"].nunique() < 2:
            return base

        try:
            splits = TimeSeriesSplit(n_splits=3)
            model = CalibratedClassifierCV(base, method="sigmoid", cv=splits)
            model.fit(train[FEATURES], train["late"])
            return model
        except Exception:
            return base

    @staticmethod
    def _metrics(train: pd.DataFrame) -> dict[str, float]:
        if len(train) < MIN_TRAINING_ROWS * 2 or train["late"].nunique() < 2:
            return {}

        # Expanding-window validation is more stable than one 75/25 split on
        # small project histories, and it mirrors how the model is retrained.
        weighted: dict[str, list[tuple[float, int]]] = {}
        for past_index, future_index in TimeSeriesSplit(n_splits=3).split(train):
            past, future = train.iloc[past_index], train.iloc[future_index]
            if past["late"].nunique() < 2 or future["late"].nunique() < 2:
                continue

            base = RiskService._fit_base(past)
            model = RiskService._calibrate(past, base)
            p = model.predict_proba(future[FEATURES])[:, 1]
            for metric, value in summarize(future["late"].to_numpy(), p).items():
                weighted.setdefault(metric, []).append((float(value), len(future)))

        metrics = {
            metric: round(sum(value * weight for value, weight in values) / sum(weight for _, weight in values), 4)
            for metric, values in weighted.items()
            if values
        }
        metrics["rows"] = float(len(train))
        return metrics

    def predict(self, issue_id: int) -> dict:
        snapshot = self.snapshot()
        row = snapshot.df[snapshot.df["id"] == issue_id]
        if row.empty:
            raise KeyError(f"Issue {issue_id} not found")

        issue = row.iloc[0]
        if int(issue["status_closed"]) == 1:
            raise ValueError("Closed issues do not need a late-risk prediction")

        now = datetime.now(UTC).replace(tzinfo=None)
        features = open_feature_dict(issue, snapshot.df, now=now, fallback_hours=snapshot.fallback_hours)
        feature_row = pd.DataFrame([{key: features[key] for key in FEATURES}])

        explanation: list[dict] = []
        if snapshot.model is not None:
            p_late = float(snapshot.model.predict_proba(feature_row)[0, 1])
            explainer = snapshot.explainer or snapshot.model
            if isinstance(explainer, Pipeline):
                explanation = self._explain(explainer, feature_row)
            model_name = "calibrated-logistic-regression" if snapshot.calibrated else "logistic-regression"
        else:
            p_late = self._heuristic(features)
            explanation = self._heuristic_explanation(features)
            model_name = "heuristic"

        p_late = float(np.clip(p_late, 0.0, 1.0))
        risk = "low" if p_late < 0.3 else "medium" if p_late < 0.6 else "high"

        due = issue["due_dt"]
        return {
            "issue_id": int(issue_id),
            "p_late": round(p_late, 4),
            "risk": risk,
            "due_date": None if pd.isna(due) else pd.Timestamp(due).date().isoformat(),
            "model": model_name,
            "model_version": snapshot.version,
            "metrics": snapshot.metrics or None,
            "explanation": explanation,
            "generated_at": now.replace(tzinfo=UTC),
        }

    @staticmethod
    def _explain(model: Pipeline, row: pd.DataFrame) -> list[dict]:
        scaler: StandardScaler = model.named_steps["scale"]
        clf: LogisticRegression = model.named_steps["clf"]
        scaled = scaler.transform(row)[0]
        contributions = clf.coef_[0] * scaled

        items = []
        for feature, impact in sorted(
            zip(FEATURES, contributions, strict=False),
            key=lambda item: abs(item[1]),
            reverse=True,
        )[:4]:
            items.append(
                {
                    "feature": feature,
                    "value": round(float(row.iloc[0][feature]), 3),
                    "impact": round(float(impact), 4),
                    "direction": "increases" if impact >= 0 else "decreases",
                }
            )
        return items

    @staticmethod
    def _heuristic(features: dict) -> float:
        score = 0.12
        score += 0.35 if features["window_days"] < 1 else 0.0
        score += 0.20 if features["pressure"] > 1 else 0.0
        score += 0.10 if features["priority"] > 0 else 0.0
        score += 0.25 * features["owner_late_rate"]
        score += 0.02 * min(features["owner_load"], 10)
        return float(np.clip(score, 0.02, 0.95))

    @staticmethod
    def _heuristic_explanation(features: dict) -> list[dict]:
        items = [
            ("window_days", -0.35 if features["window_days"] < 1 else 0.1),
            ("pressure", 0.20 if features["pressure"] > 1 else -0.05),
            ("owner_late_rate", 0.25 * features["owner_late_rate"]),
            ("owner_load", 0.02 * min(features["owner_load"], 10)),
        ]
        return [
            {
                "feature": feature,
                "value": round(float(features[feature]), 3),
                "impact": round(float(impact), 4),
                "direction": "increases" if impact >= 0 else "decreases",
            }
            for feature, impact in sorted(items, key=lambda item: abs(item[1]), reverse=True)
        ]

    def model_info(self) -> dict:
        snapshot = self.snapshot()
        return {
            "name": "task-late-risk",
            "version": snapshot.version,
            "trained_at": snapshot.trained_at.replace(tzinfo=UTC) if snapshot.trained_at else None,
            "rows": snapshot.rows,
            "metrics": snapshot.metrics,
            "active": True,
        }


risk_service = RiskService()
