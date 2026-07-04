"""Notificador real del contacto de confianza vía WhatsApp.

Implementa el `_Notifier` del protocolo de crisis (safety/protocol.py, por
tipado estructural — sin import cruzado). Hasta ahora el dispositivo usaba
un notifier de logging: el protocolo curado corría, pero nadie externo se
enteraba. Este módulo cierra ese gap.

Reglas (CLAUDE.md §4.1 y §4.2.3):
- Solo envía con consentimiento previo registrado
  (`trusted_contact_alerts_enabled`) Y contacto configurado.
- El texto es curado y mínimo: sin transcripciones, sin detalle emocional,
  sin nivel/razones de la crisis — solo "actívate ahora" + recurso curado.
- Un fallo de envío NUNCA rompe el protocolo (la voz y los recursos ya se
  despacharon); se loggea y el journal conserva `contact_notified`.
"""

from __future__ import annotations

import logging

from channels.whatsapp.client import WhatsAppClient
from db.database import Database
from product.user_config import UserConfigService
from safety.types import CrisisSignal

_log = logging.getLogger(__name__)

# Texto curado — pendiente de revisión clínica (docs/CLINICAL_REVIEW.md).
# Deliberadamente sin detalles del evento: solo pide contacto humano ahora
# y entrega el recurso oficial por si no logra ubicarle.
_ALERT_TEXT = (
    "Hola, soy Rako, el dispositivo de acompañamiento de {name}. "
    "Hace un momento activó su protocolo de apoyo y tu número está "
    "registrado como su contacto de confianza. ¿Puedes escribirle o "
    "llamarle ahora? Si no logras ubicarle y te preocupa, Salud Responde "
    "orienta 24/7: 600 360 7777."
)
_FALLBACK_NAME = "la persona que acompaño"


class WhatsAppCrisisNotifier:
    """Alerta al contacto de confianza; muestra recursos vía logging.

    `show_resources` no envía nada externo — los recursos se despliegan
    por voz/pantalla en el dispositivo; acá solo queda traza operativa.
    """

    def __init__(self, *, db: Database, client: WhatsAppClient) -> None:
        self._db = db
        self._client = client
        self.resources_shown = 0

    def notify_trusted_contact(self, signal: CrisisSignal) -> None:
        config = UserConfigService(self._db)
        consent = config.get_consent()
        contact_phone = config.get_channels().trusted_contact_phone
        if not consent.trusted_contact_alerts_enabled:
            _log.warning(
                "crisis alert skipped: trusted_contact_alerts_enabled is off "
                "(no prior consent registered)"
            )
            return
        if not contact_phone:
            _log.warning("crisis alert skipped: no trusted contact phone configured")
            return

        name = config.get_profile().preferred_name or _FALLBACK_NAME
        text = _ALERT_TEXT.format(name=name)
        try:
            self._client.send_text(to=contact_phone, text=text, kind="crisis_alert")
        except Exception:
            # El protocolo ya entregó presencia y recursos localmente; un
            # fallo de red no debe abortarlo. Queda en el log para el
            # support bundle.
            _log.exception("crisis alert delivery failed (last 4: %s)", contact_phone[-4:])
            return
        _log.info("crisis alert sent to trusted contact (last 4: %s)", contact_phone[-4:])

    def show_resources(self) -> None:
        self.resources_shown += 1
        _log.info("crisis resources displayed on device")
