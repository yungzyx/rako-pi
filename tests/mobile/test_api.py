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


def test_progress_endpoint_summarizes_tasks(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "rako.db"))
    monkeypatch.delenv("RAKO_API_TOKEN", raising=False)
    client = TestClient(create_app())

    client.post("/focus/start", json={"title": "cálculo", "minutes": 30})
    response = client.get("/progress/today")

    assert response.status_code == 200
    assert response.json()["tasks_created"] == 1
    assert response.json()["next_task_title"] == "cálculo"


def test_whatsapp_checkin_endpoint_returns_outbound_message(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "rako.db"))
    monkeypatch.delenv("RAKO_API_TOKEN", raising=False)
    client = TestClient(create_app())

    response = client.post("/whatsapp/checkin", json={"to": "+56912345678"})

    assert response.status_code == 200
    assert response.json()["kind"] == "CHECKIN"
    assert "¿cómo te sientes" in response.json()["text"]


def test_whatsapp_progress_endpoint_returns_report(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "rako.db"))
    monkeypatch.delenv("RAKO_API_TOKEN", raising=False)
    client = TestClient(create_app())

    client.post("/focus/start", json={"title": "leer papers", "minutes": 25})
    response = client.post("/whatsapp/progress", json={"to": "+56912345678"})

    assert response.status_code == 200
    assert response.json()["kind"] == "PROGRESS_REPORT"
    assert "leer papers" in response.json()["text"]


def test_whatsapp_actions_endpoint_returns_menu(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "rako.db"))
    monkeypatch.delenv("RAKO_API_TOKEN", raising=False)
    client = TestClient(create_app())

    response = client.post("/whatsapp/actions", json={"to": "+56912345678"})

    assert response.status_code == 200
    assert response.json()["kind"] == "ACTION_MENU"
    assert "Foco de 25 minutos" in response.json()["text"]


def test_whatsapp_inbound_endpoint_records_mood(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "rako.db"))
    monkeypatch.delenv("RAKO_API_TOKEN", raising=False)
    client = TestClient(create_app())

    response = client.post(
        "/whatsapp/inbound",
        json={"from_number": "+56912345678", "text": "estoy bien"},
    )

    assert response.status_code == 200
    assert response.json()["action"] == "MOOD_RECORDED"
    assert response.json()["stored_mood"] == "good"
