"""Tests del troceo de habla por oraciones (latencia percibida de TTS)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "button_conversation.py"
_spec = importlib.util.spec_from_file_location("button_conversation_speech", _SCRIPT)
assert _spec is not None and _spec.loader is not None
button_conversation = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(button_conversation)

_split = button_conversation._split_speech_chunks


def test_short_text_stays_in_one_chunk() -> None:
    assert _split("Hola, ¿cómo estás?") == ["Hola, ¿cómo estás?"]


def test_long_reply_splits_on_sentence_boundaries() -> None:
    text = (
        "Entiendo que la prueba te tiene con la cabeza a mil. "
        "Probemos algo chico: quince minutos solo leyendo el primer capítulo. "
        "Cuando termines me cuentas cómo te fue y vemos el siguiente paso juntos."
    )

    chunks = _split(text)

    assert len(chunks) >= 2
    # Cada trozo termina en un límite de oración — nunca corta al medio.
    for chunk in chunks:
        assert chunk[-1] in ".!?…"
    assert " ".join(chunks) == " ".join(text.split())


def test_tiny_sentences_are_merged_not_spoken_alone() -> None:
    text = "Ya. Dale. Empecemos con el resumen del capítulo dos que me contaste ayer."

    chunks = _split(text)

    # "Ya." y "Dale." no deben salir como trozos sueltos de 3 caracteres.
    assert all(len(chunk) >= 10 for chunk in chunks)


def test_respects_max_chunk_size() -> None:
    sentence = "Esta es una oración de largo medio que se repite varias veces."
    text = " ".join([sentence] * 8)

    chunks = _split(text, max_chars=200)

    assert len(chunks) > 1
    assert all(len(chunk) <= 200 for chunk in chunks)


def test_empty_and_whitespace_texts_produce_no_chunks() -> None:
    assert _split("") == []
    assert _split("   \n  ") == []
