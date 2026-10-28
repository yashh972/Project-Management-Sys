"""Small, dependency-free evaluation helpers used by models and reports."""

from __future__ import annotations

import numpy as np


def expected_calibration_error(y_true: np.ndarray, p: np.ndarray, bins: int = 10) -> float:
    """Mean absolute gap between predicted confidence and observed frequency."""
    y_true = np.asarray(y_true, dtype=float)
    p = np.asarray(p, dtype=float)
    if len(y_true) == 0:
        return 0.0

    edges = np.linspace(0.0, 1.0, bins + 1)
    total = 0.0
    for index in range(bins):
        low, high = edges[index], edges[index + 1]
        mask = (p >= low) & (p < high if index < bins - 1 else p <= high)
        if not mask.any():
            continue
        gap = abs(float(y_true[mask].mean()) - float(p[mask].mean()))
        total += gap * mask.mean()
    return float(total)


def reliability_curve(y_true: np.ndarray, p: np.ndarray, bins: int = 10) -> list[dict]:
    """Bins for a reliability diagram: predicted mean vs observed frequency."""
    y_true = np.asarray(y_true, dtype=float)
    p = np.asarray(p, dtype=float)
    edges = np.linspace(0.0, 1.0, bins + 1)
    rows = []
    for index in range(bins):
        low, high = edges[index], edges[index + 1]
        mask = (p >= low) & (p < high if index < bins - 1 else p <= high)
        rows.append(
            {
                "bin": f"{low:.1f}-{high:.1f}",
                "count": int(mask.sum()),
                "predicted": round(float(p[mask].mean()), 4) if mask.any() else None,
                "observed": round(float(y_true[mask].mean()), 4) if mask.any() else None,
            }
        )
    return rows


def precision_at_fraction(y_true: np.ndarray, p: np.ndarray, fraction: float = 0.1) -> float:
    """Precision among the highest-risk `fraction` of tasks."""
    y_true = np.asarray(y_true, dtype=float)
    p = np.asarray(p, dtype=float)
    if len(y_true) == 0:
        return 0.0
    count = max(1, int(round(len(y_true) * fraction)))
    order = np.argsort(-p)[:count]
    return float(y_true[order].mean())


def summarize(y_true: np.ndarray, p: np.ndarray) -> dict[str, float]:
    """Common classification metrics for an imbalanced risk model."""
    from sklearn.metrics import brier_score_loss, roc_auc_score

    y_true = np.asarray(y_true, dtype=float)
    p = np.asarray(p, dtype=float)
    metrics = {
        "brier": float(brier_score_loss(y_true, p)),
        "ece": expected_calibration_error(y_true, p),
        "precision_at_10pct": precision_at_fraction(y_true, p, 0.10),
    }
    if len(np.unique(y_true)) > 1:
        metrics["auc"] = float(roc_auc_score(y_true, p))
    return metrics
