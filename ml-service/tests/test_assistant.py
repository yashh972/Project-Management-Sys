from __future__ import annotations


def test_assistant_summary(client):
    response = client.post("/v1/assistant/ask", json={"question": "Summarize this sprint"})
    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "summary"
    assert "open tasks" in body["answer"]
    assert body["citations"]


def test_assistant_forecast(client):
    response = client.post("/v1/assistant/ask", json={"question": "What is the forecast?"})
    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "forecast"
    assert "chance" in body["answer"]


def test_assistant_risk(client):
    response = client.post("/v1/assistant/ask", json={"question": "Which tasks are risky?"})
    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "risk"


def test_assistant_workload(client):
    response = client.post("/v1/assistant/ask", json={"question": "Who is overloaded?"})
    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "workload"
    assert "workload" in body["answer"].lower()


def test_assistant_assignment(client):
    response = client.post("/v1/assistant/ask", json={"question": "Who should take #1001?"})
    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "assignment"
    assert "#1001" in body["answer"]


def test_assistant_duplicates(client):
    response = client.post("/v1/assistant/ask", json={"question": "Find duplicates for backend API task"})
    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "duplicates"
