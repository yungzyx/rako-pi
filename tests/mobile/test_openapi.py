"""Tests del contrato OpenAPI y del endpoint de pairing para la app."""

from __future__ import annotations

from fastapi.testclient import TestClient

from mobile.api import create_app

EXPECTED_TAGS = {"core", "user", "setup", "factory", "device", "whatsapp"}


def _client(monkeypatch, tmp_path) -> TestClient:
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "rako.db"))
    monkeypatch.delenv("RAKO_API_TOKEN", raising=False)
    return TestClient(create_app())


def test_openapi_schema_is_served_and_grouped_by_domain(monkeypatch, tmp_path) -> None:
    client = _client(monkeypatch, tmp_path)

    response = client.get("/openapi.json")

    assert response.status_code == 200
    schema = response.json()
    assert schema["info"]["title"] == "Rako Local API"
    used_tags = {
        tag
        for path_item in schema["paths"].values()
        for operation in path_item.values()
        for tag in operation.get("tags", [])
    }
    assert used_tags == EXPECTED_TAGS


def test_every_route_has_exactly_one_domain_tag(monkeypatch, tmp_path) -> None:
    client = _client(monkeypatch, tmp_path)

    schema = client.get("/openapi.json").json()

    for path, path_item in schema["paths"].items():
        for method, operation in path_item.items():
            tags = operation.get("tags", [])
            assert len(tags) == 1, f"{method.upper()} {path} tiene tags {tags}"


def test_pairing_info_is_public_and_never_leaks_the_token(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "rako.db"))
    monkeypatch.setenv("RAKO_API_TOKEN", "super-secret-token")
    client = TestClient(create_app())

    response = client.get("/pairing/info")  # sin Authorization

    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "Rako"
    assert payload["requires_token"] is True
    assert "super-secret-token" not in response.text


def test_pairing_info_reports_open_dev_device(monkeypatch, tmp_path) -> None:
    client = _client(monkeypatch, tmp_path)  # dev, sin token

    payload = client.get("/pairing/info").json()

    assert payload["requires_token"] is False
    assert payload["app_version"]


def test_swagger_docs_page_is_reachable(monkeypatch, tmp_path) -> None:
    client = _client(monkeypatch, tmp_path)

    response = client.get("/docs")

    assert response.status_code == 200
