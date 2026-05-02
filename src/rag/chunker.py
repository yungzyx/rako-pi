"""Chunker de la vault de Obsidian para indexación en ChromaDB.

Pipeline:
1. `parse_obsidian_note(text, source)` → separa frontmatter YAML + body.
2. `chunk_note(parsed)` → divide el body en H2 secciones, cada chunk
   hereda la metadata del frontmatter + `section`.
3. `chunk_vault(path)` → camina un directorio de notas y emite todos
   los chunks.

Nota sobre el frontmatter de Obsidian: las vaults a menudo tienen
secuencias `[#tag1, #tag2]` que NO son YAML válido (PyYAML interpreta
`#` como comentario). El parser sanitiza estas listas antes de cargar.
"""

from __future__ import annotations

import re
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any, Final

import yaml

from rag.types import Chunk, ParsedNote

_FRONTMATTER_RE: Final = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?(.*)\Z", re.DOTALL)
_WIKILINK_LINE_RE: Final = re.compile(r"^\s*(?:\[\[[^\]\n]+\]\]\s*)+\s*$", re.MULTILINE)
_HASH_TOKEN_IN_FLOW_RE: Final = re.compile(r"\[([^\]\n]+)\]")
_H1_RE: Final = re.compile(r"^#\s+.+$", re.MULTILINE)
_H2_SPLIT_RE: Final = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)


def parse_obsidian_note(text: str, source: str) -> ParsedNote:
    """Parsea una nota completa: frontmatter YAML + body markdown."""
    match = _FRONTMATTER_RE.match(text)
    if match:
        raw_frontmatter, body = match.group(1), match.group(2)
        frontmatter = _parse_yaml_frontmatter(raw_frontmatter)
    else:
        frontmatter, body = {}, text

    body = _strip_wikilink_block(body)
    return ParsedNote(source=source, frontmatter=frontmatter, body=body.strip())


def chunk_note(parsed: ParsedNote) -> tuple[Chunk, ...]:
    """Divide el body en chunks por secciones H2.

    Cada chunk hereda toda la metadata del frontmatter más:
    - `source`: el nombre de la nota (sin `.md`).
    - `section`: el título H2 de la sección.
    - `chunk_index`: índice numérico (estable por nota).
    """
    sections = _split_into_sections(parsed.body)
    base_metadata = _flatten_metadata(parsed.frontmatter, parsed.source)
    chunks: list[Chunk] = []

    for index, (heading, body) in enumerate(sections):
        body_text = body.strip()
        if not body_text:
            continue
        metadata = {**base_metadata, "section": heading, "chunk_index": index}
        chunks.append(
            Chunk(
                id=f"{parsed.source}#{index}",
                text=f"## {heading}\n\n{body_text}" if heading else body_text,
                metadata=metadata,
            )
        )

    return tuple(chunks)


def chunk_vault(path: Path) -> Iterator[Chunk]:
    """Camina un directorio de notas Obsidian y emite chunks."""
    if not path.exists():
        raise FileNotFoundError(f"vault path not found: {path}")

    for md_file in sorted(path.glob("*.md")):
        if md_file.name.startswith("."):
            continue
        text = md_file.read_text(encoding="utf-8")
        parsed = parse_obsidian_note(text, source=md_file.stem)
        yield from chunk_note(parsed)


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _parse_yaml_frontmatter(raw: str) -> Mapping[str, Any]:
    sanitized = _sanitize_obsidian_yaml(raw)
    try:
        loaded = yaml.safe_load(sanitized)
    except yaml.YAMLError:
        return {}
    if not isinstance(loaded, dict):
        return {}
    return loaded


def _sanitize_obsidian_yaml(yaml_text: str) -> str:
    """Cita tokens `#word` dentro de flow sequences `[...]`.

    PyYAML interpreta `#` como inicio de comentario, lo que rompe
    `tags: [#a, #b]`. Aquí los reescribimos como `["#a", "#b"]`.
    """

    def _fix(match: re.Match[str]) -> str:
        inner = match.group(1)
        items = [token.strip() for token in inner.split(",")]
        fixed: list[str] = []
        for item in items:
            if item.startswith("#") and not (item.startswith('"') or item.startswith("'")):
                fixed.append(f'"{item}"')
            else:
                fixed.append(item)
        return "[" + ", ".join(fixed) + "]"

    return _HASH_TOKEN_IN_FLOW_RE.sub(_fix, yaml_text)


def _strip_wikilink_block(body: str) -> str:
    """Elimina líneas que solo contienen wikilinks `[[xx]]`."""
    return _WIKILINK_LINE_RE.sub("", body)


def _split_into_sections(body: str) -> list[tuple[str, str]]:
    """Divide el body por encabezados H2. Devuelve [(heading, content), ...].

    El intro antes del primer H2 se descarta — los H1 suelen repetir el
    título del frontmatter y no agregan información para el RAG.
    """
    matches = list(_H2_SPLIT_RE.finditer(body))
    if not matches:
        return [("", body)]

    sections: list[tuple[str, str]] = []
    for i, m in enumerate(matches):
        heading = m.group(1).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        sections.append((heading, body[start:end].strip()))
    return sections


def _flatten_metadata(frontmatter: Mapping[str, Any], source: str) -> dict[str, Any]:
    """Aplana el frontmatter para metadata de chunk.

    ChromaDB acepta tipos primitivos (str, int, float, bool) en metadata.
    Listas se serializan como strings separadas por coma.
    """
    out: dict[str, Any] = {"source": source}
    for key, value in frontmatter.items():
        if isinstance(value, (str, int, float, bool)):
            out[key] = value
        elif isinstance(value, list):
            out[key] = ",".join(str(item) for item in value)
        elif value is None:
            continue
        else:
            out[key] = str(value)
    return out
