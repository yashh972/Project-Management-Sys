"""Bridge to the original batch scripts while the pipeline is ported.

The PHP application must never shell out again. This module keeps the existing
analytics/assignment scripts usable from inside the ML service until the new
training code and registry take over.

SQLite is the native path. MySQL is supported through a temporary SQLite mirror
of the tables the scripts read: the scripts run unchanged, and the three result
tables are written back to MySQL. This is intentionally a bridge, not the
long-term architecture.
"""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

import pandas as pd

from .config import get_settings
from .db import get_engine, read_df

MIRROR_COLUMNS = {
    "user": ["id", "username", "email", "name", "role", "rank", "created_date", "deleted_date"],
    "issue": [
        "id",
        "type_id",
        "status",
        "name",
        "description",
        "author_id",
        "owner_id",
        "parent_id",
        "priority",
        "hours_total",
        "hours_remaining",
        "hours_spent",
        "created_date",
        "closed_date",
        "deleted_date",
        "start_date",
        "due_date",
        "sprint_id",
    ],
    "issue_update": ["id", "issue_id", "user_id", "created_date"],
    "issue_update_field": ["id", "issue_update_id", "field", "old_value", "new_value"],
    "issue_tag": ["id", "issue_id", "tag"],
}


def _run(script_name: str, args: list[str], timeout: int = 300) -> str:
    settings = get_settings()
    script = settings.legacy_dir / script_name
    if not script.is_file():
        raise FileNotFoundError(f"Legacy ML script not found: {script}")

    env = os.environ.copy()
    env.setdefault("PYTHONUNBUFFERED", "1")
    result = subprocess.run(
        [sys.executable, str(script), *args],
        cwd=str(settings.legacy_dir),
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
        check=False,
    )
    output = (result.stdout or "") + (result.stderr or "")
    if result.returncode != 0:
        raise RuntimeError(f"{script_name} failed ({result.returncode}): {output[-2000:]}")
    return output[-4000:]


def _sqlite_schema() -> Path:
    settings = get_settings()
    candidates = [
        settings.legacy_dir / "database.sqlite.sql",
        settings.project_root / "db" / "database.sqlite.sql",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise FileNotFoundError("db/database.sqlite.sql is required for the MySQL analytics bridge")


def _read_sqlite_table(con: sqlite3.Connection, table: str) -> pd.DataFrame:
    try:
        return pd.read_sql_query(f"SELECT * FROM {table}", con)
    except Exception:
        return pd.DataFrame()


def _train_mirror(include_assignment: bool) -> dict:
    settings = get_settings()
    schema = _sqlite_schema()
    output: list[str] = []
    metrics: dict[str, object] = {}

    with tempfile.TemporaryDirectory(prefix="phproject-ml-") as tmp:
        mirror_path = Path(tmp) / "mirror.sqlite"
        mirror = sqlite3.connect(mirror_path)
        try:
            mirror.executescript(schema.read_text(encoding="utf-8"))
            for table, columns in MIRROR_COLUMNS.items():
                if table == "issue_tag":
                    mirror.execute("DELETE FROM issue_tag")
                quoted = ", ".join(f"`{column}`" for column in columns)
                frame = read_df(f"SELECT {quoted} FROM `{table}`")
                frame.to_sql(table, mirror, if_exists="append", index=False)
            mirror.commit()
        finally:
            mirror.close()

        output.append(_run("run_analytics.py", ["--db", str(mirror_path), "--quiet"]))
        if include_assignment:
            output.append(_run("assign_model.py", ["train", "--db", str(mirror_path), "--quiet"]))

        mirror = sqlite3.connect(mirror_path)
        try:
            employee = _read_sqlite_table(mirror, "employee_performance")
            risk = _read_sqlite_table(mirror, "task_risk")
            runs = _read_sqlite_table(mirror, "ml_run")
            assignment_runs = _read_sqlite_table(mirror, "assign_model_run")
        finally:
            mirror.close()

        engine = get_engine()
        if not employee.empty:
            employee.to_sql("employee_performance", engine, if_exists="replace", index=False)
        if not risk.empty:
            risk.to_sql("task_risk", engine, if_exists="replace", index=False)
        if not runs.empty:
            runs.to_sql("ml_run", engine, if_exists="replace", index=False)
        if not assignment_runs.empty:
            assignment_runs.to_sql("assign_model_run", engine, if_exists="replace", index=False)

        if not runs.empty:
            try:
                metrics["analytics"] = json.loads(str(runs.iloc[-1]["metrics"]))
            except Exception:
                pass
        if not assignment_runs.empty:
            try:
                metrics["assignment"] = json.loads(str(assignment_runs.iloc[-1]["metrics"]))
            except Exception:
                pass

    return {
        "ok": True,
        "engine": settings.db_engine,
        "output": "\n".join(part for part in output if part),
        "metrics": metrics,
    }


def train_legacy(include_assignment: bool = True) -> dict:
    settings = get_settings()
    if settings.db_engine != "sqlite":
        return _train_mirror(include_assignment)

    if not settings.db_path or not settings.db_path.is_file():
        raise FileNotFoundError(f"SQLite database not found: {settings.db_path}")

    output = [_run("run_analytics.py", ["--db", str(settings.db_path), "--quiet"])]
    if include_assignment:
        output.append(_run("assign_model.py", ["train", "--db", str(settings.db_path), "--quiet"]))

    metrics: dict[str, object] = {}
    try:
        rows = read_df("SELECT metrics FROM ml_run ORDER BY id DESC LIMIT 1")
        if not rows.empty:
            metrics["analytics"] = json.loads(rows.iloc[0]["metrics"])
    except Exception:
        pass

    try:
        rows = read_df("SELECT metrics FROM assign_model_run ORDER BY id DESC LIMIT 1")
        if not rows.empty:
            metrics["assignment"] = json.loads(rows.iloc[0]["metrics"])
    except Exception:
        pass

    return {
        "ok": True,
        "engine": settings.db_engine,
        "output": "\n".join(part for part in output if part),
        "metrics": metrics,
    }
