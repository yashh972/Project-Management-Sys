from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_health_and_version(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"
    assert body["service"] == "phproject-ml"

    version = client.get("/version")
    assert version.status_code == 200
    assert version.json()["database_engine"] == "sqlite"


def test_root_and_metrics(client):
    root = client.get("/")
    assert root.status_code == 200
    assert root.json()["service"] == "phproject-ml"

    metrics = client.get("/metrics")
    assert metrics.status_code == 200
    assert "phproject_ml_up 1" in metrics.text


def test_internal_auth_is_required():
    with TestClient(app) as anonymous:
        response = anonymous.post("/v1/predict/risk", json={"issue_id": 1001})
        assert response.status_code == 401
