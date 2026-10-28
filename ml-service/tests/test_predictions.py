from __future__ import annotations


def test_risk_prediction(client):
    response = client.post("/v1/predict/risk", json={"issue_id": 1001})
    assert response.status_code == 200
    body = response.json()

    assert body["issue_id"] == 1001
    assert 0 <= body["p_late"] <= 1
    assert body["risk"] in {"low", "medium", "high"}
    assert body["model_version"]
    assert body["explanation"]
    assert body["due_date"]


def test_cycle_prediction(client):
    response = client.post("/v1/predict/cycle", json={"issue_id": 1002})
    assert response.status_code == 200
    body = response.json()

    assert body["p50_days"] > 0
    assert body["p85_days"] >= body["p50_days"]
    assert body["sample_size"] > 0


def test_unknown_issue_is_404(client):
    response = client.post("/v1/predict/risk", json={"issue_id": 999999})
    assert response.status_code == 404


def test_closed_issue_is_rejected(client):
    response = client.post("/v1/predict/risk", json={"issue_id": 100})
    assert response.status_code == 400
