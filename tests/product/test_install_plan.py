from __future__ import annotations

from config import Settings
from product.install_plan import build_install_plan, install_plan_to_dict


def test_install_plan_blocks_without_security_env() -> None:
    plan = build_install_plan(Settings(_env_file=None, rako_env="prod"))
    payload = install_plan_to_dict(plan)

    assert payload["ready_to_run"] is False
    assert any(
        step["name"] == "security env" and step["status"] == "blocked" for step in payload["steps"]
    )


def test_install_plan_ready_when_security_env_exists() -> None:
    plan = build_install_plan(
        Settings(
            _env_file=None,
            rako_env="prod",
            rako_api_token="token",
            sqlite_encryption_key="x" * 64,
        )
    )

    assert plan.ready_to_run is True
