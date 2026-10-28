"""Walk-forward evaluation for the risk model.

Random splits flatter a project-history model because future work leaks into the
training set. This harness trains on the past and tests on the next block, the
same way the model will be used in production.
"""

from __future__ import annotations

from datetime import UTC, datetime

import numpy as np
import pandas as pd

from .features import FEATURES, load_issues, training_frame
from .metrics import reliability_curve, summarize
from .risk import RiskService


def backtest_risk(folds: int = 4, min_train: int = 30) -> dict:
    df = load_issues()
    train = training_frame(df)
    if len(train) < min_train + folds * 3 or train["late"].nunique() < 2:
        return {
            "folds": [],
            "overall": {},
            "reliability": [],
            "rows": int(len(train)),
            "message": "Not enough closed tasks for a meaningful backtest",
            "generated_at": datetime.now(UTC).isoformat(),
        }

    usable = (len(train) - min_train) // folds
    if usable < 3:
        return {
            "folds": [],
            "overall": {},
            "reliability": [],
            "rows": int(len(train)),
            "message": "Not enough tasks per fold",
            "generated_at": datetime.now(UTC).isoformat(),
        }

    fold_rows = []
    all_y: list[np.ndarray] = []
    all_p: list[np.ndarray] = []

    for index in range(folds):
        train_end = min_train + index * usable
        test_end = train_end + usable if index < folds - 1 else len(train)
        past, future = train.iloc[:train_end], train.iloc[train_end:test_end]
        if future.empty or past["late"].nunique() < 2 or future["late"].nunique() < 2:
            continue

        base = RiskService._fit_base(past)
        model = RiskService._calibrate(past, base)
        probabilities = model.predict_proba(future[FEATURES])[:, 1]
        labels = future["late"].to_numpy()
        all_y.append(labels)
        all_p.append(probabilities)

        fold_rows.append(
            {
                "fold": index + 1,
                "train_rows": int(len(past)),
                "test_rows": int(len(future)),
                "period_start": str(pd.Timestamp(future["closed_dt"].min()).date()),
                "period_end": str(pd.Timestamp(future["closed_dt"].max()).date()),
                **summarize(labels, probabilities),
            }
        )

    if not all_y:
        return {
            "folds": [],
            "overall": {},
            "reliability": [],
            "rows": int(len(train)),
            "message": "No fold had both classes in its test window",
            "generated_at": datetime.now(UTC).isoformat(),
        }

    labels = np.concatenate(all_y)
    probabilities = np.concatenate(all_p)
    overall: dict[str, float] = {}
    for metric in ("auc", "brier", "ece", "precision_at_10pct"):
        weighted = [
            (float(fold[metric]), fold["test_rows"])
            for fold in fold_rows
            if metric in fold and fold[metric] is not None
        ]
        if weighted:
            total = sum(weight for _, weight in weighted)
            overall[metric] = round(sum(value * weight for value, weight in weighted) / total, 4)

    return {
        "folds": fold_rows,
        "overall": overall,
        "reliability": reliability_curve(labels, probabilities),
        "rows": int(len(train)),
        "generated_at": datetime.now(UTC).isoformat(),
    }
