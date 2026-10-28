"""Model registry persistence.

The registry is a table rather than a directory listing so every prediction can
be traced to the exact dataset and metrics that produced it. Writes are
best-effort: the service still works on a fresh database before migrations run.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

import pandas as pd

from .db import execute


def dataset_hash(frame: pd.DataFrame) -> str:
    if frame.empty:
        return ""
    hashed = pd.util.hash_pandas_object(frame, index=True).to_numpy()
    return hashlib.sha1(hashed.tobytes()).hexdigest()


def record_model_run(
    model_name: str,
    version: str,
    trained_at: datetime,
    rows: int,
    metrics: dict[str, float],
    train: pd.DataFrame | None = None,
    artifact_path: str | None = None,
) -> None:
    try:
        execute(
            "UPDATE model_run SET is_active = 0 WHERE model_name = :name",
            {"name": model_name},
        )
        execute(
            """
            INSERT INTO model_run
                (model_name, version, trained_at, rows_count, metrics_json,
                 artifact_path, dataset_hash, is_active, created_date)
            VALUES
                (:name, :version, :trained_at, :rows, :metrics,
                 :artifact, :hash, 1, :created)
            """,
            {
                "name": model_name,
                "version": version,
                "trained_at": trained_at,
                "rows": rows,
                "metrics": json.dumps(metrics, sort_keys=True),
                "artifact": artifact_path,
                "hash": dataset_hash(train) if train is not None else None,
                "created": datetime.now(UTC).replace(tzinfo=None),
            },
        )
    except Exception:
        # A fresh database may not have the registry migration yet. Inference
        # must still work; the next successful migration will start recording.
        pass
