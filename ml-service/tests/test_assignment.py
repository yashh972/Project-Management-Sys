from __future__ import annotations


def test_single_issue_recommendations(client):
    response = client.post("/v1/assign/suggest", json={"issue_id": 1001, "top": 3})
    assert response.status_code == 200
    body = response.json()

    assert body["issue_id"] == 1001
    assert len(body["recommendations"]) == 1
    candidates = body["recommendations"][0]["candidates"]
    assert len(candidates) == 2
    assert candidates[0]["score"] >= candidates[1]["score"]
    assert all(0 <= candidate["score"] <= 100 for candidate in candidates)


def test_sprint_recommendations(client):
    response = client.post("/v1/assign/suggest", json={"sprint_id": 1})
    assert response.status_code == 200
    body = response.json()

    assert body["sprint_id"] == 1
    assert len(body["recommendations"]) == 4
    assert all(recommendation["candidates"] for recommendation in body["recommendations"])


def test_draft_task_recommendations(client):
    response = client.post(
        "/v1/assign/suggest",
        json={
            "draft": {
                "type_id": 1,
                "hours": 8,
                "priority": 1,
                "due": "2026-11-15",
                "tags": ["backend", "api"],
                "exclude": [3],
            },
            "top": 3,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["issue_id"] is None
    assert body["sprint_id"] is None
    assert len(body["recommendations"]) == 1
    candidates = body["recommendations"][0]["candidates"]
    assert [candidate["user_id"] for candidate in candidates] == [2]
    assert candidates[0]["tag_overlap"] > 0


def test_target_is_required(client):
    response = client.post("/v1/assign/suggest", json={})
    assert response.status_code == 422

    both = client.post("/v1/assign/suggest", json={"issue_id": 1001, "sprint_id": 1})
    assert both.status_code == 422
