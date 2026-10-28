from __future__ import annotations


def test_optimize_assigns_sprint_tasks(client):
    response = client.post(
        "/v1/assign/optimize",
        json={"sprint_id": 1, "capacity_hours": 80, "max_wip": 10, "time_limit_seconds": 2},
    )
    assert response.status_code == 200
    body = response.json()

    assert body["sprint_id"] == 1
    assert body["solver"] in {"cp_sat", "greedy"}
    assert body["summary"]["tasks"] == 4
    assert body["summary"]["assigned"] + len(body["unassigned"]) == 4
    assert body["assignments"]
    assert body["baseline"]
    for assignment in body["assignments"]:
        assert assignment["issue_id"] > 0
        assert assignment["user_id"] in {2, 3}
        assert 0 <= assignment["score"] <= 100


def test_optimize_unknown_sprint_is_404(client):
    response = client.post("/v1/assign/optimize", json={"sprint_id": 999})
    assert response.status_code == 404
