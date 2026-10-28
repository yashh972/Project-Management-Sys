from __future__ import annotations


def test_backtest_returns_walk_forward_metrics(client):
    response = client.post("/v1/models/risk/backtest", json={"folds": 2, "min_train": 20})
    assert response.status_code == 200
    body = response.json()

    assert body["rows"] > 0
    assert body["generated_at"]
    if body["folds"]:
        assert len(body["folds"]) <= 2
        assert "brier" in body["overall"]
        assert "ece" in body["overall"]
        assert body["reliability"]
        for fold in body["folds"]:
            assert fold["train_rows"] > 0
            assert fold["test_rows"] > 0
    else:
        assert body["message"]
