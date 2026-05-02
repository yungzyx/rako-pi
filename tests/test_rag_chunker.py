"""Tests del chunker de la vault de Obsidian."""

from __future__ import annotations

from pathlib import Path

import pytest

from rag.chunker import (
    chunk_note,
    chunk_vault,
    parse_obsidian_note,
)
from rag.types import Chunk, ParsedNote

_NOTE_WITH_FRONTMATTER = """---
titulo: "Técnicas de respiración"
tipo: tecnica
categoria: respiracion
usar_cuando: [angustia_aguda, ansiedad]
duracion_minutos: 2-5
nivel_evidencia: alto
tags: [#respiracion, #ansiedad]
---
[[02_grounding]]

# Técnicas de Respiración

## Qué es

Texto introductorio.

## Respiración 4-7-8

Paso 1. Paso 2.

## Cuándo no usarlo

En crisis severa, derivar.
"""

_NOTE_WITHOUT_FRONTMATTER = """# Solo título

## Sección A

Cuerpo A.
"""


def test_parse_extracts_frontmatter_metadata() -> None:
    parsed = parse_obsidian_note(_NOTE_WITH_FRONTMATTER, source="01_tecnicas")

    assert isinstance(parsed, ParsedNote)
    assert parsed.frontmatter["titulo"] == "Técnicas de respiración"
    assert parsed.frontmatter["categoria"] == "respiracion"
    assert parsed.frontmatter["usar_cuando"] == ["angustia_aguda", "ansiedad"]
    assert parsed.frontmatter["tags"] == ["#respiracion", "#ansiedad"]
    assert parsed.source == "01_tecnicas"


def test_parse_handles_note_without_frontmatter() -> None:
    parsed = parse_obsidian_note(_NOTE_WITHOUT_FRONTMATTER, source="raw")

    assert parsed.frontmatter == {}
    assert "Solo título" in parsed.body


def test_parse_strips_wikilinks_block_before_first_heading() -> None:
    text = "---\nfoo: bar\n---\n[[02_grounding]][[01_tecnicas]]\n\n# Heading\n\nBody."
    parsed = parse_obsidian_note(text, source="x")

    assert "[[02_grounding]]" not in parsed.body
    assert parsed.frontmatter == {"foo": "bar"}


def test_chunk_note_splits_on_h2() -> None:
    parsed = parse_obsidian_note(_NOTE_WITH_FRONTMATTER, source="01_tecnicas")
    chunks = chunk_note(parsed)

    headings = [c.metadata.get("section") for c in chunks]
    assert "Qué es" in headings
    assert "Respiración 4-7-8" in headings
    assert "Cuándo no usarlo" in headings


def test_chunk_ids_combine_source_and_index() -> None:
    parsed = parse_obsidian_note(_NOTE_WITH_FRONTMATTER, source="01_tecnicas")
    chunks = chunk_note(parsed)

    ids = [c.id for c in chunks]
    assert all(cid.startswith("01_tecnicas#") for cid in ids)
    assert len(set(ids)) == len(ids)  # IDs únicos


def test_each_chunk_inherits_frontmatter_metadata() -> None:
    parsed = parse_obsidian_note(_NOTE_WITH_FRONTMATTER, source="01_tecnicas")
    chunks = chunk_note(parsed)

    for c in chunks:
        assert c.metadata["categoria"] == "respiracion"
        assert c.metadata["tipo"] == "tecnica"


def test_chunk_skips_empty_sections() -> None:
    text = """---
foo: bar
---

# Title

## A

cuerpo a.

## B

## C

cuerpo c.
"""
    parsed = parse_obsidian_note(text, source="x")
    chunks = chunk_note(parsed)
    sections = [c.metadata.get("section") for c in chunks]

    assert "B" not in sections
    assert "A" in sections
    assert "C" in sections


def test_chunk_text_is_not_empty(tmp_path: Path) -> None:
    parsed = parse_obsidian_note(_NOTE_WITH_FRONTMATTER, source="01_tecnicas")
    chunks = chunk_note(parsed)

    assert all(c.text.strip() for c in chunks)
    assert all(isinstance(c, Chunk) for c in chunks)


def test_chunk_vault_walks_directory(tmp_path: Path) -> None:
    (tmp_path / "01.md").write_text(_NOTE_WITH_FRONTMATTER)
    (tmp_path / "02.md").write_text(_NOTE_WITHOUT_FRONTMATTER)
    (tmp_path / "ignored.txt").write_text("not markdown")

    chunks = list(chunk_vault(tmp_path))

    sources = {c.metadata["source"] for c in chunks}
    assert sources == {"01", "02"}


def test_chunk_vault_skips_hidden_files(tmp_path: Path) -> None:
    (tmp_path / "01.md").write_text(_NOTE_WITH_FRONTMATTER)
    (tmp_path / ".hidden.md").write_text(_NOTE_WITHOUT_FRONTMATTER)

    chunks = list(chunk_vault(tmp_path))

    sources = {c.metadata["source"] for c in chunks}
    assert sources == {"01"}


def test_chunk_vault_raises_for_missing_directory(tmp_path: Path) -> None:
    missing = tmp_path / "nope"

    with pytest.raises(FileNotFoundError):
        list(chunk_vault(missing))


def test_parse_handles_yaml_with_special_chars() -> None:
    # Asegura que no fallamos con caracteres no-ASCII.
    text = """---
titulo: "Cómo cuidar el sistema nervioso después de un episodio"
descripcion: "Texto con áéíóú y signos: ¿? ¡!"
---

# Título

Cuerpo.
"""
    parsed = parse_obsidian_note(text, source="x")

    assert "Cómo cuidar" in parsed.frontmatter["titulo"]
    assert "áéíóú" in parsed.frontmatter["descripcion"]


def test_parse_returns_empty_metadata_for_invalid_yaml() -> None:
    # Frontmatter rotos no deben crashear el indexador — cargar nada.
    text = """---
foo: : : bad
---

# t

cuerpo.
"""
    parsed = parse_obsidian_note(text, source="x")

    assert parsed.frontmatter == {}
    assert "cuerpo" in parsed.body


def test_parse_returns_empty_metadata_when_frontmatter_is_not_a_dict() -> None:
    text = """---
- a
- b
---

# t

cuerpo.
"""
    parsed = parse_obsidian_note(text, source="x")

    assert parsed.frontmatter == {}


def test_metadata_value_unhandled_type_is_stringified() -> None:
    # Un dict anidado en el frontmatter (caso raro) → str(...).
    text = """---
nested:
  key: value
---

# t

## A

cuerpo.
"""
    parsed = parse_obsidian_note(text, source="x")
    chunks = chunk_note(parsed)

    assert "nested" in chunks[0].metadata
    assert isinstance(chunks[0].metadata["nested"], str)


def test_chunk_note_for_simple_note_with_h2() -> None:
    parsed = parse_obsidian_note(_NOTE_WITHOUT_FRONTMATTER, source="raw")
    chunks = chunk_note(parsed)

    assert len(chunks) == 1
    assert chunks[0].metadata.get("section") == "Sección A"


def test_chunk_note_with_no_sections_at_all_falls_back() -> None:
    # Una nota sin H2 ni encabezados — debe producir 1 chunk con el body.
    text = """---
foo: bar
---

texto sin estructura.
"""
    parsed = parse_obsidian_note(text, source="x")
    chunks = chunk_note(parsed)

    assert len(chunks) == 1
    assert "texto sin estructura" in chunks[0].text


def test_metadata_drops_none_values() -> None:
    text = """---
foo: bar
empty:
---

# t

## A

cuerpo.
"""
    parsed = parse_obsidian_note(text, source="x")
    chunks = chunk_note(parsed)

    assert "empty" not in chunks[0].metadata
    assert chunks[0].metadata["foo"] == "bar"
