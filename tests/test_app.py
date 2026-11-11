import types

import numpy as np
import pytest
from fastapi.testclient import TestClient

import src.app as appmod


class FakeModel:
    def predict(self, X):
        return [1 for _ in X]

    def predict_proba(self, X):
        return np.array([[0.2, 0.8] for _ in X])


class FakeClient:
    def get_model_version_by_alias(self, name, alias):
        assert alias == "champion"
        return types.SimpleNamespace(version="7")


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("MLFLOW_TRACKING_URI", "http://dummy:5000")
    monkeypatch.setattr(appmod.mlflow.sklearn, "load_model", lambda uri: FakeModel())
    monkeypatch.setattr(appmod.mlflow, "MlflowClient", lambda *a, **k: FakeClient())
    with TestClient(appmod.app) as c:  # the context manager runs the lifespan (model loading)
        yield c


def test_health_reports_model_version(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "model_version": "7"}


def test_predict_returns_sentiment(client):
    r = client.post("/predict", json={"message": "a wonderful film"})
    assert r.status_code == 200
    body = r.json()
    assert body["sentiment"] == "positive"
    assert body["confidence"] == pytest.approx(0.8)


def test_predict_rejects_missing_message(client):
    assert client.post("/predict", json={}).status_code == 422
