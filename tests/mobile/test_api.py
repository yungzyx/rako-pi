from __future__ import annotations

from fastapi.testclient import TestClient

from mobile.api import create_app


def test_health_does_not_require_token(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "rako.db"))
    monkeypatch.setenv("RAKO_API_TOKEN", "secret")
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_status_requires_token_when_configured(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "rako.db"))
    monkeypatch.setenv("RAKO_API_TOKEN", "secret")
    client = TestClient(create_app())

    missing = client.get("/status")
    valid = client.get("/status", headers={"Authorization": "Bearer secret"})

    assert missing.status_code == 401
    assert valid.status_code == 200
    assert valid.json()["state"] == "ready"


def test_tasks_endpoint_lists_mobile_focus_tasks(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "rako.db"))
    monkeypatch.delenv("RAKO_API_TOKEN", raising=False)
    client = TestClient(create_app())

    started = client.post("/focus/start", json={"title": "cálculo", "minutes": 30})
    tasks = client.get("/tasks?pending_only=true")

    assert started.status_code == 200
    assert tasks.status_code == 200
    assert tasks.json()["tasks"][0]["title"] == "cálculo"
    assert tasks.json()["tasks"][0]["status"] == "IN_PROGRESS"
