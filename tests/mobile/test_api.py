from __future__ import annotations

import hashlib
import hmac
import json

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


def test_setup_page_is_public_and_uses_setup_flow(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "rako.db"))
    monkeypatch.setenv("RAKO_API_TOKEN", "secret")
    client = TestClient(create_app())

    response = client.get("/setup")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Configurar Rako" in response.text
    assert 'fetchJson("/setup/flow")' in response.text
    assert 'fetchJson("/factory/report")' in response.text
    assert 'fetchJson("/factory/provisioning-plan")' in response.text
    assert 'submitJson(event, "/user/profile"' in response.text
    assert 'submitJson(event, "/user/consent"' in response.text
    assert 'fetchJson("/user/memory"' in response.text
    assert 'fetchJson("/setup/hotspot/plan")' in response.text
    assert "secret" not in response.text


def test_factory_page_is_public_shell_and_uses_factory_endpoints(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "rako.db"))
    monkeypatch.setenv("RAKO_API_TOKEN", "secret")
    client = TestClient(create_app())

    response = client.get("/factory")

    assert response.status_code == 200
    assert "Rako Factory" in response.text
    assert 'fetchJson("/factory/report")' in response.text
    assert 'fetchJson("/update/status")' in response.text
    assert "Bearer secret" not in response.text


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


def test_coach_plan_endpoint_recommends_next_study_action(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "rako.db"))
    monkeypatch.delenv("RAKO_API_TOKEN", raising=False)
    client = TestClient(create_app())

    empty = client.get("/coach/plan")
    client.post("/focus/start", json={"title": "cálculo", "minutes": 30})
    active = client.get("/coach/plan")

    assert empty.status_code == 200
    assert empty.json()["kind"] == "PLAN_FIRST_STEP"
    assert active.json()["kind"] == "RESUME_ACTIVE_TASK"
    assert active.json()["recommended_minutes"] == 25


def test_user_config_endpoints_support_product_onboarding(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "rako.db"))
    monkeypatch.delenv("RAKO_API_TOKEN", raising=False)
    client = TestClient(create_app())

    initial = client.get("/onboarding/status")
    profile = client.patch(
        "/user/profile",
        json={"preferred_name": "Nico", "university": "UDD", "program": "Ingeniería"},
    )
    channels = client.patch(
        "/user/channels",
        json={"wifi_ssid": "Casa", "whatsapp_number": "+56912345678"},
    )
    consent = client.patch(
        "/user/consent",
        json={"whatsapp_enabled": True, "progress_reports_enabled": True},
    )
    ready = client.get("/onboarding/status")

    assert initial.status_code == 200
    assert "privacy_consent" in initial.json()["missing"]
    assert profile.json()["preferred_name"] == "Nico"
    assert channels.json()["wifi_ssid"] == "Casa"
    assert consent.json()["accepted_at"] is not None
    assert ready.json()["ready"] is True


def test_setup_flow_endpoint_shows_next_first_run_action(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "rako.db"))
    monkeypatch.delenv("RAKO_API_TOKEN", raising=False)
    client = TestClient(create_app())

    initial = client.get("/setup/flow")
    client.patch("/user/profile", json={"preferred_name": "Nico"})
    updated = client.get("/setup/flow")

    assert initial.status_code == 200
    assert initial.json()["next_step_id"] == "profile"
    assert initial.json()["steps"][0]["title"] == "Perfil del estudiante"
    assert updated.json()["next_step_id"] == "wifi"


def test_setup_wifi_endpoint_stores_ssid_without_password(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "rako.db"))
    monkeypatch.delenv("RAKO_API_TOKEN", raising=False)
    client = TestClient(create_app())

    response = client.post(
        "/setup/wifi",
        json={"ssid": "Casa", "password": "super-secret", "apply": False},
    )
    channels = client.get("/user/channels")

    assert response.status_code == 200
    assert response.json()["status"] == "stored"
    assert response.json()["ssid"] == "Casa"
    assert channels.json()["wifi_ssid"] == "Casa"
    assert "super-secret" not in str(channels.json())


def test_setup_wifi_endpoint_blocks_apply_until_enabled(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "rako.db"))
    monkeypatch.delenv("RAKO_API_TOKEN", raising=False)
    client = TestClient(create_app())

    response = client.post(
        "/setup/wifi",
        json={"ssid": "Casa", "password": "super-secret", "apply": True},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "blocked"


def test_setup_hotspot_plan_endpoint_is_read_only(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "rako.db"))
    monkeypatch.setenv("RAKO_DEVICE_ID", "rako-test-001")
    monkeypatch.delenv("RAKO_API_TOKEN", raising=False)
    client = TestClient(create_app())

    response = client.get("/setup/hotspot/plan")

    assert response.status_code == 200
    assert response.json()["status"] == "disabled"
    assert response.json()["ssid"] == "Rako-Setup-est001"
    assert "<temporary-setup-password>" in response.json()["commands"][1]


def test_setup_hotspot_start_endpoint_blocks_real_apply_by_default(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "rako.db"))
    monkeypatch.delenv("RAKO_API_TOKEN", raising=False)
    client = TestClient(create_app())

    response = client.post(
        "/setup/hotspot/start",
        json={"password": "temporary-123", "apply": True},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "blocked"


def test_setup_qr_endpoints_do_not_expose_token(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "rako.db"))
    monkeypatch.setenv("RAKO_DEVICE_ID", "rako-test-001")
    monkeypatch.setenv("RAKO_API_TOKEN", "secret")
    client = TestClient(create_app())

    payload = client.get("/setup/qr", headers={"Authorization": "Bearer secret"})
    svg = client.get("/setup/qr.svg", headers={"Authorization": "Bearer secret"})

    assert payload.status_code == 200
    assert payload.json()["includes_secret"] is False
    assert "Bearer secret" not in str(payload.json())
    assert "RAKO_API_TOKEN" not in str(payload.json())
    assert svg.status_code == 200
    assert "image/svg+xml" in svg.headers["content-type"]
    assert "Bearer secret" not in svg.text
    assert "RAKO_API_TOKEN" not in svg.text


def test_user_memory_endpoint_requires_sensitive_memory_consent(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "rako.db"))
    monkeypatch.delenv("RAKO_API_TOKEN", raising=False)
    client = TestClient(create_app())

    rejected = client.post(
        "/user/memory",
        json={"text": "Prefiero estudiar de noche", "sensitivity": "sensitive"},
    )
    client.patch("/user/consent", json={"sensitive_memory_enabled": True})
    created = client.post(
        "/user/memory",
        json={"text": "Prefiero estudiar de noche", "category": "routine"},
    )
    listed = client.get("/user/memory")
    deleted = client.delete(f"/user/memory/{created.json()['id']}")

    assert rejected.status_code == 400
    assert created.status_code == 200
    assert listed.json()["items"][0]["text"] == "Prefiero estudiar de noche"
    assert deleted.json()["deleted"] is True


def test_user_export_and_delete_all_endpoints_manage_product_data(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "rako.db"))
    monkeypatch.delenv("RAKO_API_TOKEN", raising=False)
    client = TestClient(create_app())
    client.patch("/user/profile", json={"preferred_name": "Nico", "university": "UDD"})
    client.patch("/user/channels", json={"wifi_ssid": "Casa", "whatsapp_number": "+56912345678"})
    client.patch("/user/consent", json={"whatsapp_enabled": True})
    client.post("/user/memory", json={"text": "Prefiero bloques cortos"})

    exported = client.get("/user/export")
    deleted = client.post("/user/delete-all")
    exported_after_delete = client.get("/user/export")

    assert exported.status_code == 200
    assert exported.json()["profile"]["preferred_name"] == "Nico"
    assert exported.json()["memory"][0]["text"] == "Prefiero bloques cortos"
    assert deleted.json()["deleted_count"] == 4
    assert exported_after_delete.json()["profile"]["preferred_name"] is None
    assert exported_after_delete.json()["memory"] == []


def test_factory_report_endpoint_summarizes_unit_readiness(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "rako.db"))
    monkeypatch.setenv("RAKO_DEVICE_ID", "rako-test-001")
    monkeypatch.delenv("RAKO_API_TOKEN", raising=False)
    client = TestClient(create_app())

    response = client.get("/factory/report")

    assert response.status_code == 200
    assert response.json()["device_id"] == "rako-test-001"
    assert response.json()["ready_for_handoff"] is False
    assert response.json()["next_setup_step_id"] == "profile"
    assert "acceptance" in response.json()


def test_factory_provisioning_plan_endpoint_lists_blockers(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "rako.db"))
    monkeypatch.setenv("RAKO_DEVICE_ID", "rako-test-001")
    monkeypatch.delenv("RAKO_API_TOKEN", raising=False)
    client = TestClient(create_app())

    response = client.get("/factory/provisioning-plan")

    assert response.status_code == 200
    assert response.json()["device_id"] == "rako-test-001"
    assert response.json()["ready_for_image"] is False
    assert response.json()["hotspot"]["status"] == "disabled"
    assert any(
        step["name"] == "acceptance checklist" and step["status"] == "fail"
        for step in response.json()["steps"]
    )


def test_factory_install_plan_endpoint_lists_dry_run_commands(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "rako.db"))
    monkeypatch.delenv("RAKO_API_TOKEN", raising=False)
    client = TestClient(create_app())

    response = client.get("/factory/install-plan")

    assert response.status_code == 200
    assert response.json()["ready_to_run"] is False
    assert any(step["name"] == "systemd api" for step in response.json()["steps"])


def test_fleet_security_and_hardware_endpoints_support_factory_ops(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "rako.db"))
    monkeypatch.setenv("RAKO_DEVICE_ID", "rako-test-001")
    monkeypatch.delenv("RAKO_API_TOKEN", raising=False)
    client = TestClient(create_app())

    security = client.get("/security/audit")
    initial_hardware = client.get("/hardware/checks")
    recorded = client.post(
        "/hardware/checks",
        json={"name": "microphone", "status": "pass", "detail": "clear"},
    )
    snapshot = client.get("/fleet/snapshot")

    assert security.status_code == 200
    assert "checks" in security.json()
    assert initial_hardware.json()["ready"] is False
    assert "microphone" in recorded.json()["records"][0]["name"]
    assert snapshot.json()["device_id"] == "rako-test-001"
    assert "hardware" in snapshot.json()


def test_support_bundle_endpoint_is_sanitized(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "rako.db"))
    monkeypatch.setenv("RAKO_DEVICE_ID", "rako-test-001")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-secret")
    monkeypatch.delenv("RAKO_API_TOKEN", raising=False)
    client = TestClient(create_app())

    response = client.get("/support/bundle")

    assert response.status_code == 200
    assert response.json()["device_id"] == "rako-test-001"
    assert response.json()["env_presence"]["openai_api_key"] is True
    assert "sk-secret" not in str(response.json())


def test_device_identity_and_heartbeat_endpoints_support_factory_tracking(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "rako.db"))
    monkeypatch.setenv("RAKO_DEVICE_ID", "rako-test-001")
    monkeypatch.delenv("RAKO_API_TOKEN", raising=False)
    client = TestClient(create_app())

    initial = client.get("/device/identity")
    provisioned = client.patch(
        "/device/identity",
        json={"serial": "SN-001", "lot": "pilot-a", "assigned_user_label": "nico@udd"},
    )
    heartbeat = client.post("/device/heartbeat", json={"status": "ok", "detail": "bench"})
    report = client.get("/factory/report")

    assert initial.json()["device_id"] == "rako-test-001"
    assert provisioned.json()["serial"] == "SN-001"
    assert provisioned.json()["lot"] == "pilot-a"
    assert heartbeat.json()["status"] == "ok"
    assert heartbeat.json()["detail"] == "bench"
    assert report.json()["identity"]["assigned_user_label"] == "nico@udd"
    assert report.json()["heartbeat"]["status"] == "ok"


def test_reset_user_endpoint_clears_assignment_data_but_keeps_device_identity(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "rako.db"))
    monkeypatch.setenv("RAKO_DEVICE_ID", "rako-test-001")
    monkeypatch.delenv("RAKO_API_TOKEN", raising=False)
    client = TestClient(create_app())
    client.patch(
        "/device/identity",
        json={"serial": "SN-001", "lot": "pilot-a", "assigned_user_label": "nico@udd"},
    )
    client.post("/device/heartbeat", json={"status": "ok"})
    client.patch("/user/profile", json={"preferred_name": "Nico"})
    client.patch("/user/channels", json={"wifi_ssid": "Casa", "whatsapp_number": "+56912345678"})
    client.patch("/user/consent", json={"whatsapp_enabled": True})
    client.post("/focus/start", json={"title": "cálculo", "minutes": 25})

    reset = client.post("/device/reset-user")
    identity = client.get("/device/identity")
    profile = client.get("/user/profile")
    tasks = client.get("/tasks")
    report = client.get("/factory/report")

    assert reset.status_code == 200
    assert reset.json()["identity"]["serial"] == "SN-001"
    assert "tasks" in reset.json()["purged_domains"]
    assert identity.json()["serial"] == "SN-001"
    assert profile.json()["preferred_name"] is None
    assert tasks.json()["tasks"] == []
    assert report.json()["heartbeat"]["status"] == "ok"


def test_update_status_endpoint_is_read_only(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "rako.db"))
    monkeypatch.setenv("RAKO_RELEASE_CHANNEL", "beta")
    monkeypatch.delenv("RAKO_API_TOKEN", raising=False)
    client = TestClient(create_app())

    response = client.get("/update/status")

    assert response.status_code == 200
    assert response.json()["release_channel"] == "beta"
    assert response.json()["update_apply_enabled"] is False


def test_update_plan_endpoint_evaluates_manifest(monkeypatch, tmp_path) -> None:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "version": "0.2.0",
                "channel": "stable",
                "artifact_url": "https://example.com/rako-0.2.0.tar.gz",
                "artifact_sha256": "c" * 64,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "rako.db"))
    monkeypatch.setenv("RAKO_UPDATE_MANIFEST_PATH", str(manifest_path))
    monkeypatch.delenv("RAKO_API_TOKEN", raising=False)
    client = TestClient(create_app())

    response = client.get("/update/plan")

    assert response.status_code == 200
    assert response.json()["decision"] == "available"
    assert response.json()["target_version"] == "0.2.0"
    assert "Verify artifact SHA-256 before unpacking." in response.json()["steps"]


def test_update_apply_endpoint_is_blocked_by_default(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "rako.db"))
    monkeypatch.delenv("RAKO_API_TOKEN", raising=False)
    client = TestClient(create_app())

    response = client.post("/update/apply", json={"apply": True})

    assert response.status_code == 200
    assert response.json()["status"] == "blocked"


def test_whatsapp_checkin_endpoint_returns_outbound_message(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "rako.db"))
    monkeypatch.delenv("RAKO_API_TOKEN", raising=False)
    client = TestClient(create_app())
    client.patch("/user/channels", json={"whatsapp_number": "+56912345678"})
    client.patch("/user/consent", json={"whatsapp_enabled": True})

    response = client.post("/whatsapp/checkin", json={"to": "+56912345678"})

    assert response.status_code == 200
    assert response.json()["kind"] == "CHECKIN"
    assert "¿cómo te sientes" in response.json()["text"]


def test_whatsapp_progress_endpoint_returns_report(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "rako.db"))
    monkeypatch.delenv("RAKO_API_TOKEN", raising=False)
    client = TestClient(create_app())
    client.patch("/user/channels", json={"whatsapp_number": "+56912345678"})
    client.patch(
        "/user/consent",
        json={"whatsapp_enabled": True, "progress_reports_enabled": True},
    )

    client.post("/focus/start", json={"title": "leer papers", "minutes": 25})
    response = client.post("/whatsapp/progress", json={"to": "+56912345678"})

    assert response.status_code == 200
    assert response.json()["kind"] == "PROGRESS_REPORT"
    assert "leer papers" not in response.json()["text"]
    assert "siguiente paso disponible" in response.json()["text"]


def test_api_requires_token_outside_dev_when_missing(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "rako.db"))
    monkeypatch.setenv("RAKO_ENV", "prod")
    monkeypatch.delenv("RAKO_API_TOKEN", raising=False)
    client = TestClient(create_app())

    response = client.get("/status")

    assert response.status_code == 401
    assert "RAKO_API_TOKEN" in response.json()["detail"]


def test_whatsapp_actions_endpoint_returns_menu(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "rako.db"))
    monkeypatch.delenv("RAKO_API_TOKEN", raising=False)
    client = TestClient(create_app())
    client.patch("/user/channels", json={"whatsapp_number": "+56912345678"})
    client.patch("/user/consent", json={"whatsapp_enabled": True})

    response = client.post("/whatsapp/actions", json={"to": "+56912345678"})

    assert response.status_code == 200
    assert response.json()["kind"] == "ACTION_MENU"
    assert "Foco de 25 minutos" in response.json()["text"]


def test_whatsapp_templates_endpoint_lists_meta_templates(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "rako.db"))
    monkeypatch.delenv("RAKO_API_TOKEN", raising=False)
    client = TestClient(create_app())

    response = client.get("/whatsapp/templates")

    assert response.status_code == 200
    assert response.json()["templates"][0]["name"].startswith("rako_")
    assert "sensitive memory" in response.json()["notes"][1]


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


def test_whatsapp_webhook_verification(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "rako.db"))
    monkeypatch.setenv("WHATSAPP_CLOUD_VERIFY_TOKEN", "verify-me")
    client = TestClient(create_app())

    response = client.get(
        "/whatsapp/webhook",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "verify-me",
            "hub.challenge": "challenge-123",
        },
    )

    assert response.status_code == 200
    assert response.text == "challenge-123"


def test_whatsapp_webhook_processes_text_message_in_dev(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "rako.db"))
    monkeypatch.delenv("RAKO_API_TOKEN", raising=False)
    client = TestClient(create_app())

    response = client.post(
        "/whatsapp/webhook",
        json={
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "messages": [
                                    {
                                        "id": "wamid.1",
                                        "from": "56912345678",
                                        "text": {"body": "estoy bien"},
                                    }
                                ]
                            }
                        }
                    ]
                }
            ]
        },
    )

    assert response.status_code == 200
    assert response.json()["processed"] == 1
    assert response.json()["results"][0]["action"] == "MOOD_RECORDED"


def test_whatsapp_webhook_requires_signature_outside_dev(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "rako.db"))
    monkeypatch.setenv("RAKO_ENV", "prod")
    monkeypatch.setenv("RAKO_API_TOKEN", "secret")
    monkeypatch.setenv("WHATSAPP_CLOUD_APP_SECRET", "app-secret")
    client = TestClient(create_app())
    body = b'{"entry":[]}'
    digest = hmac.new(b"app-secret", body, hashlib.sha256).hexdigest()

    rejected = client.post("/whatsapp/webhook", content=body)
    accepted = client.post(
        "/whatsapp/webhook",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": f"sha256={digest}",
        },
    )

    assert rejected.status_code == 403
    assert accepted.status_code == 200
    assert accepted.json()["processed"] == 0
