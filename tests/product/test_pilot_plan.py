from __future__ import annotations

from product.pilot_plan import build_pilot_plan, pilot_plan_to_dict


def test_pilot_plan_prioritizes_real_user_validation() -> None:
    payload = pilot_plan_to_dict(build_pilot_plan())

    assert payload["recommended_users"] == "3-5"
    assert payload["duration_days"] == 14
    assert any(
        step["area"] == "academia" and step["priority"] == "must" for step in payload["steps"]
    )
