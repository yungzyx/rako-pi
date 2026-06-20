from __future__ import annotations

import argparse

from db.database import Database
from product.user_config import UserConfigService
from scripts.rako_provision import provision


def test_provision_sets_profile_channels_consent_and_memory(db_conn) -> None:
    db = Database(db_conn)
    args = argparse.Namespace(
        name="Nico",
        university="UDD",
        program="Ingeniería",
        timezone=None,
        locale=None,
        wifi_ssid="Casa",
        whatsapp_number="+56912345678",
        trusted_contact_name="Apoyo",
        trusted_contact_phone="+56911111111",
        wellbeing_unit_name="Bienestar UDD",
        wellbeing_unit_phone="+56228203419",
        enable_whatsapp=True,
        enable_progress=True,
        enable_proactive=True,
        enable_wellbeing=True,
        memory=["Prefiere bloques cortos"],
    )

    status = provision(db, args)
    config = UserConfigService(db)

    assert status["ready"] is True
    assert status["missing"] == []
    assert config.get_profile().preferred_name == "Nico"
    assert config.get_channels().wifi_ssid == "Casa"
    assert config.progress_reports_can_send() is True
    assert config.list_memory()[0].text == "Prefiere bloques cortos"
