"""Test fixtures: a complete SQLite Phproject schema with deterministic history."""

from __future__ import annotations

import os
import sqlite3
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if not (ROOT / "db" / "database.sqlite.sql").is_file():
    # Docker copies the service to /app (the repository root is /app).
    ROOT = Path(__file__).resolve().parents[1]
DB_PATH = Path(tempfile.mkdtemp(prefix="phproject-ml-")) / "test.sqlite"

os.environ["ML_ENV"] = "test"
os.environ["PHPROJECT_DB_ENGINE"] = "sqlite"
os.environ["PHPROJECT_DB_NAME"] = str(DB_PATH)
os.environ["ML_INTERNAL_TOKEN"] = "test-token"
os.environ["ML_RISK_CACHE_SECONDS"] = "300"


def _iso(value: datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M:%S")


def _build_database() -> None:
    schema = (ROOT / "db" / "database.sqlite.sql").read_text(encoding="utf-8")
    con = sqlite3.connect(DB_PATH)
    try:
        con.executescript(schema)
        now = datetime.now(UTC).replace(tzinfo=None, microsecond=0)

        con.executemany(
            "INSERT INTO user (id, username, email, name, role, rank, created_date) VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (1, "admin", "admin@example.com", "Admin", "admin", 100, _iso(now - timedelta(days=200))),
                (2, "alice", "alice@example.com", "Alice", "user", 10, _iso(now - timedelta(days=200))),
                (3, "bob", "bob@example.com", "Bob", "user", 10, _iso(now - timedelta(days=200))),
            ],
        )
        con.execute(
            "INSERT INTO sprint (id, name, start_date, end_date) VALUES (?, ?, ?, ?)",
            (1, "Sprint 1", (now - timedelta(days=7)).date().isoformat(), (now + timedelta(days=7)).date().isoformat()),
        )

        rows = []
        issue_id = 100
        for owner, late_bias, tag in ((2, 0, "backend"), (3, 1, "frontend")):
            for index in range(20):
                created = now - timedelta(days=150 - index * 5)
                start = created + timedelta(days=1)
                due = start + timedelta(days=5)
                late = (index % 4 == 0) if late_bias == 0 else (index % 2 == 0)
                closed = due + timedelta(days=3) if late else due - timedelta(days=1)
                rows.append(
                    {
                        "id": issue_id,
                        "status": 3,
                        "type_id": 1,
                        "name": f"Closed task {issue_id}",
                        "description": "Synthetic history",
                        "author_id": 1,
                        "owner_id": owner,
                        "parent_id": None,
                        "priority": 0,
                        "hours_total": 4 + (index % 5),
                        "hours_remaining": None,
                        "hours_spent": 0,
                        "created_date": _iso(created),
                        "closed_date": _iso(closed),
                        "deleted_date": None,
                        "start_date": _iso(start),
                        "due_date": due.date().isoformat(),
                        "sprint_id": None,
                        "due_date_sprint": 0,
                    }
                )
                con.execute("INSERT INTO issue_tag (issue_id, tag) VALUES (?, ?)", (issue_id, tag))
                issue_id += 1

        # Open sprint work, including a dependency and an unassigned task.
        open_tasks = [
            (1001, 2, "Open backend task", 8, 3, 1, 1, 1001),
            (1002, 3, "Open frontend task", 16, 1, 4, 1, 1002),
            (1003, 2, "Dependent task", 4, 5, 2, 0, 1003),
            (1004, None, "Unassigned task", 6, 6, 0, 0, 1004),
        ]
        for task_id, owner, name, hours, due_in, queue, priority, _ in open_tasks:
            created = now - timedelta(days=queue)
            start = created + timedelta(days=1) if owner else created
            rows.append(
                {
                    "id": task_id,
                    "status": 1,
                    "type_id": 1,
                    "name": name,
                    "description": "Synthetic open task",
                    "author_id": 1,
                    "owner_id": owner,
                    "parent_id": None,
                    "priority": priority,
                    "hours_total": hours,
                    "hours_remaining": hours,
                    "hours_spent": 0,
                    "created_date": _iso(created),
                    "closed_date": None,
                    "deleted_date": None,
                    "start_date": _iso(start),
                    "due_date": (now + timedelta(days=due_in)).date().isoformat(),
                    "sprint_id": 1,
                    "due_date_sprint": 0,
                }
            )

        con.executemany(
            """
            INSERT INTO issue
                (id, status, type_id, name, description, author_id, owner_id, parent_id, priority,
                 hours_total, hours_remaining, hours_spent, created_date, closed_date,
                 deleted_date, start_date, due_date, sprint_id, due_date_sprint)
            VALUES (:id, :status, :type_id, :name, :description, :author_id, :owner_id, :parent_id, :priority,
                    :hours_total, :hours_remaining, :hours_spent, :created_date, :closed_date,
                    :deleted_date, :start_date, :due_date, :sprint_id, :due_date_sprint)
            """,
            rows,
        )
        con.execute("INSERT INTO issue_tag (issue_id, tag) VALUES (1001, 'backend')")
        con.execute("INSERT INTO issue_tag (issue_id, tag) VALUES (1002, 'frontend')")
        con.execute(
            "INSERT INTO issue_dependency (issue_id, dependency_id, dependency_type) VALUES (1003, 1001, 'FS')"
        )
        con.commit()
    finally:
        con.close()


_build_database()


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as test_client:
        test_client.headers.update({"X-Internal-Token": "test-token"})
        yield test_client


@pytest.fixture(scope="session")
def db_path() -> Path:
    return DB_PATH
