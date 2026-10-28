from __future__ import annotations


def test_similar_issue_by_id(client):
    response = client.post("/v1/search/similar", json={"issue_id": 1001, "top_k": 3})
    assert response.status_code == 200
    body = response.json()
    assert body["corpus"] > 0
    assert body["results"]
    assert all(result["issue_id"] != 1001 for result in body["results"])
    assert body["results"][0]["score"] >= body["results"][-1]["score"]


def test_similar_issue_by_text(client):
    response = client.post(
        "/v1/search/similar",
        json={"text": "Open backend task with an API dependency", "top_k": 5},
    )
    assert response.status_code == 200
    assert response.json()["results"]


def test_similar_requires_query(client):
    response = client.post("/v1/search/similar", json={})
    assert response.status_code == 422
