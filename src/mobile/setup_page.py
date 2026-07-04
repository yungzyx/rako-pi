"""Self-contained first-run setup page for a local Rako device."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

_TEMPLATE_PATH = Path(__file__).parent / "templates" / "setup_page.html"


@lru_cache(maxsize=1)
def render_setup_page() -> str:
    return _TEMPLATE_PATH.read_text(encoding="utf-8")
