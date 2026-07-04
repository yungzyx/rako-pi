"""Detector de señales de crisis.

Combina:
- Botón pánico (físico o app).
- Frases clave de ideación o autolesión en la transcripción.
- Vector emocional extremo sostenido.
- Inactividad prolongada tras una interacción de alta angustia.

El orquestador debe consultar `detect_crisis` ANTES de cualquier llamada
al LLM. Si el resultado tiene `should_bypass_llm`, no se genera respuesta
con IA: se ejecuta el protocolo curado.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta

from safety.types import (
    CrisisInput,
    CrisisLevel,
    CrisisReason,
    CrisisSignal,
    EmotionalSample,
    PanicSource,
)

# ---------------------------------------------------------------------------
# Umbrales (constantes nombradas — nada de números mágicos en el código)
# ---------------------------------------------------------------------------

# Sostenido = al menos N muestras extremas en una ventana, cubriendo
# un span temporal mínimo (descarta spikes concentrados de pocos segundos).
_SUSTAINED_LOOKBACK = timedelta(minutes=10)
_SUSTAINED_MIN_SAMPLES = 4
_SUSTAINED_MIN_SPAN = timedelta(minutes=6)
_EXTREME_VALENCE_MAX = -0.7  # valence < este valor cuenta como extremo
_EXTREME_AROUSAL_MIN = 0.7  # arousal > este valor cuenta como extremo

# Elevated (ni neutro ni crisis): promedio reciente bajo este umbral.
_ELEVATED_LOOKBACK = timedelta(minutes=60)
_ELEVATED_VALENCE_MAX = -0.4
_ELEVATED_MIN_SAMPLES = 3

# Inactividad prolongada tras angustia.
_INACTIVITY_DISTRESS_FRESHNESS = timedelta(hours=24)
_INACTIVITY_GAP_MIN = timedelta(hours=2)


# ---------------------------------------------------------------------------
# Frases clave (forma normalizada: minúsculas, sin acentos, con espacios
# colapsados). Pares (frase, exclusiones) — si una exclusión coincide,
# la frase no dispara.
#
# Solo la forma SIN acentos/ñ: `_normalize()` le hace strip de acentos al
# transcript de entrada, así que una variante con tilde/ñ nunca podría
# matchear — no duplicar entradas "hacer daño" junto a "hacer dano".
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _Pattern:
    needle: str
    excludes: tuple[str, ...] = ()


_IDEATION_PATTERNS: tuple[_Pattern, ...] = (
    _Pattern("quiero morir", excludes=("no quiero morir",)),
    _Pattern("quiero morirme", excludes=("no quiero morirme",)),
    _Pattern("me quiero morir", excludes=("no me quiero morir",)),
    _Pattern("ya no quiero vivir"),
    _Pattern("no quiero vivir"),
    _Pattern("no quiero seguir vivo"),
    _Pattern("no quiero seguir viva"),
    _Pattern("no quiero seguir aqui"),
    _Pattern("quiero matarme"),
    _Pattern("me quiero matar"),
    _Pattern("quiero suicidarme"),
    _Pattern("me quiero suicidar"),
    _Pattern("voy a matarme"),
    _Pattern("voy a suicidarme"),
    _Pattern("me voy a suicidar"),
    _Pattern("pensando en suicidarme"),
    _Pattern("pienso en suicidarme"),
    _Pattern("suicidarme"),
    _Pattern("kiero morir", excludes=("no kiero morir",)),
    _Pattern("me kiero morir", excludes=("no me kiero morir",)),
)

_SELFHARM_PATTERNS: tuple[_Pattern, ...] = (
    _Pattern("autolesion"),
    _Pattern("autolesionarme"),
    _Pattern("cortarme"),
    _Pattern("me cortaria"),
    _Pattern("me corte"),
    _Pattern("hacerme dano"),
    _Pattern("hacer dano a mi"),
    _Pattern("me hice dano"),
    _Pattern("lastimarme"),
    _Pattern("lesionarme"),
    _Pattern("quemarme"),
    _Pattern("golpearme"),
    _Pattern("dejar de comer"),
    _Pattern("rayarme"),
    _Pattern("me raye"),
    _Pattern("rayandome"),
    _Pattern("quiero rayarme"),
)

_GOODBYE_PATTERNS: tuple[_Pattern, ...] = (
    _Pattern("quiero desaparecer"),
    _Pattern("desaparecer para siempre"),
    _Pattern("ya no quiero estar"),
    _Pattern("dormir para siempre"),
    _Pattern("no tiene sentido seguir"),
    _Pattern("no aguanto mas"),
    _Pattern("no puedo mas"),
    _Pattern("ya nse puede mas"),
    _Pattern("ya no se puede mas"),
    _Pattern("les haria un favor a todos"),
    _Pattern("ya para que"),
)

_ABUSE_SEXUAL_PATTERNS: tuple[_Pattern, ...] = (
    _Pattern("abuso sexual"),
    _Pattern("abusaron de mi"),
    _Pattern("me abusaron"),
    _Pattern("violacion"),
    _Pattern("me violaron"),
)

_HARM_OTHERS_PATTERNS: tuple[_Pattern, ...] = (
    _Pattern("quiero matar a"),
    _Pattern("voy a matar a"),
    _Pattern("matar a un"),
    _Pattern("matar a una"),
    _Pattern("quiero herir a"),
    _Pattern("voy a herir a"),
    _Pattern("herir a un"),
    _Pattern("herir a una"),
    _Pattern("lastimar a un"),
    _Pattern("lastimar a una"),
    _Pattern("hacerle dano a"),
    _Pattern("hacer dano a"),
    _Pattern("hacer dano al"),
    _Pattern("hacer dano a un"),
    _Pattern("hacer dano a una"),
)

_DANGEROUS_ACCESS_PATTERNS: tuple[_Pattern, ...] = (
    _Pattern("cafe con cloro"),
    _Pattern("tomar cloro"),
    _Pattern("tomar veneno"),
    _Pattern("mezclar pastillas"),
    _Pattern("sobredosis"),
    _Pattern("que pasa si uno toma"),
    _Pattern("que pasaria si alguien tomara"),
    _Pattern("conseguir un arma"),
    _Pattern("usar un arma"),
    _Pattern("preparar veneno"),
    _Pattern("hacer veneno"),
)


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------


def detect_crisis(input: CrisisInput) -> CrisisSignal:
    """Devuelve la señal de crisis que aplica al input dado.

    Determinístico, sin efectos. Llamar siempre antes del LLM.
    """
    reasons: list[CrisisReason] = []

    if input.panic_button is PanicSource.PHYSICAL:
        reasons.append(CrisisReason.PANIC_BUTTON_PHYSICAL)
    elif input.panic_button is PanicSource.APP:
        reasons.append(CrisisReason.PANIC_BUTTON_APP)

    if input.transcript:
        normalized = _normalize(input.transcript)
        if _matches_any(normalized, _IDEATION_PATTERNS):
            reasons.append(CrisisReason.KEYWORDS_IDEATION)
        if _matches_any(normalized, _SELFHARM_PATTERNS):
            reasons.append(CrisisReason.KEYWORDS_SELFHARM)
        if _matches_any(normalized, _GOODBYE_PATTERNS):
            reasons.append(CrisisReason.KEYWORDS_GOODBYE)
        if _matches_any(normalized, _ABUSE_SEXUAL_PATTERNS):
            reasons.append(CrisisReason.KEYWORDS_ABUSE_SEXUAL)
        if _matches_any(normalized, _HARM_OTHERS_PATTERNS):
            reasons.append(CrisisReason.KEYWORDS_HARM_OTHERS)
        if _matches_any(normalized, _DANGEROUS_ACCESS_PATTERNS):
            reasons.append(CrisisReason.KEYWORDS_DANGEROUS_ACCESS)

    if _is_sustained_extreme(input.emotion_history, input.now):
        reasons.append(CrisisReason.SUSTAINED_EMOTIONAL_EXTREME)

    if _is_prolonged_inactivity_after_distress(input):
        reasons.append(CrisisReason.PROLONGED_INACTIVITY_AFTER_DISTRESS)

    if reasons:
        return CrisisSignal(
            level=CrisisLevel.CRISIS,
            reasons=tuple(reasons),
            detected_at=input.now,
        )

    if _is_emotionally_elevated(input.emotion_history, input.now):
        return CrisisSignal(
            level=CrisisLevel.ELEVATED,
            reasons=(CrisisReason.EMOTIONAL_DISTRESS,),
            detected_at=input.now,
        )

    return CrisisSignal(
        level=CrisisLevel.NONE,
        reasons=(),
        detected_at=input.now,
    )


# ---------------------------------------------------------------------------
# Helpers — texto
# ---------------------------------------------------------------------------


def _normalize(text: str) -> str:
    """Lowercase + strip de acentos + colapso de espacios."""
    text = text.lower()
    decomposed = unicodedata.normalize("NFD", text)
    stripped = "".join(c for c in decomposed if unicodedata.category(c) != "Mn")
    collapsed = re.sub(r"\s+", " ", stripped).strip()
    return collapsed


def _find_all_spans(text: str, needle: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    start = 0
    while (idx := text.find(needle, start)) != -1:
        spans.append((idx, idx + len(needle)))
        start = idx + 1
    return spans


def _spans_overlap(a: tuple[int, int], b: tuple[int, int]) -> bool:
    return a[0] < b[1] and b[0] < a[1]


def _matches_any(normalized_text: str, patterns: Iterable[_Pattern]) -> bool:
    """True si alguna ocurrencia del needle de algún patrón no está negada.

    Una ocurrencia solo se descarta si el span de una frase de exclusión se
    solapa con ella — una negación en otra parte de la transcripción (p.ej.
    "no quiero morir... pero en el fondo sí quiero morir") no debe poder
    silenciar una afirmación real y posterior de la misma frase.
    """
    for p in patterns:
        needle_spans = _find_all_spans(normalized_text, p.needle)
        if not needle_spans:
            continue
        exclude_spans = [
            span for exc in p.excludes for span in _find_all_spans(normalized_text, exc)
        ]
        unsuppressed = (
            span
            for span in needle_spans
            if not any(_spans_overlap(span, exc_span) for exc_span in exclude_spans)
        )
        if any(True for _ in unsuppressed):
            return True
    return False


# ---------------------------------------------------------------------------
# Helpers — emoción
# ---------------------------------------------------------------------------


def _samples_in_window(
    history: Iterable[EmotionalSample], now: datetime, window: timedelta
) -> list[EmotionalSample]:
    cutoff = now - window
    return [s for s in history if cutoff <= s.at <= now]


def _is_sustained_extreme(history: Iterable[EmotionalSample], now: datetime) -> bool:
    # NOTA (ver CLAUDE.md §4.2): esta lógica está completa y testeada, pero
    # hoy ningún llamador real (`orchestrator/run.py`) le pasa un
    # `emotion_history` no vacío — no hay modelo SER local implementado
    # todavía. Este trigger está dormido en producción hasta que exista un
    # SER local y algo que lo alimente. "Tiene tests" no es "está en
    # producción" — no confundir el uno con el otro.
    samples = _samples_in_window(history, now, _SUSTAINED_LOOKBACK)
    if len(samples) < _SUSTAINED_MIN_SAMPLES:
        return False

    extreme = [
        s
        for s in samples
        if s.vector.valence <= _EXTREME_VALENCE_MAX and s.vector.arousal >= _EXTREME_AROUSAL_MIN
    ]
    if len(extreme) < _SUSTAINED_MIN_SAMPLES:
        return False

    span = max(s.at for s in extreme) - min(s.at for s in extreme)
    return span >= _SUSTAINED_MIN_SPAN


def _is_emotionally_elevated(history: Iterable[EmotionalSample], now: datetime) -> bool:
    samples = _samples_in_window(history, now, _ELEVATED_LOOKBACK)
    if len(samples) < _ELEVATED_MIN_SAMPLES:
        return False

    avg_valence = sum(s.vector.valence for s in samples) / len(samples)
    return avg_valence <= _ELEVATED_VALENCE_MAX


# ---------------------------------------------------------------------------
# Helpers — inactividad
# ---------------------------------------------------------------------------


def _is_prolonged_inactivity_after_distress(input: CrisisInput) -> bool:
    # ACTIVO en producción (ver CLAUDE.md §4.2): los datos vivos los
    # calculan `find_last_high_distress_at`/`find_last_interaction_at`
    # (orchestrator/context.py) y los inyecta TurnSession en ambos loops
    # de voz. En modo privado ambos llegan None y el trigger queda
    # apagado. Los eventos de follow-up no renuevan la ventana de 24h
    # (anti-loop, filtrado en el helper).
    if input.last_high_distress_at is None:
        return False
    if input.last_interaction_at is None:
        return False

    distress_age = input.now - input.last_high_distress_at
    if distress_age > _INACTIVITY_DISTRESS_FRESHNESS:
        return False

    inactivity = input.now - input.last_interaction_at
    return inactivity >= _INACTIVITY_GAP_MIN
