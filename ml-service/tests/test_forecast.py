from __future__ import annotations


def test_sprint_forecast(client):
    response = client.post("/v1/forecast/sprint", json={"sprint_id": 1, "simulations": 800})
    assert response.status_code == 200
    body = response.json()

    assert body["sprint_id"] == 1
    assert body["open_tasks"] == 4
    assert 0 <= body["probability_on_time"] <= 1
    assert body["p50_date"] <= body["p85_date"] <= body["p95_date"]
    assert body["drivers"]
    assert body["assumptions"]["simulations"] == 800
    assert body["assumptions"]["dependencies"] == 1


def test_unknown_sprint_is_404(client):
    response = client.post("/v1/forecast/sprint", json={"sprint_id": 999})
    assert response.status_code == 404
