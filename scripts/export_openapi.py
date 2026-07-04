#!/usr/bin/env python3
"""Exporta el schema OpenAPI de la API móvil a JSON.

Para el desarrollo de la app Flutter: el archivo generado sirve de
contrato (o de input para generadores de cliente).

Uso:
    PYTHONPATH=src python scripts/export_openapi.py [salida.json]

Sin argumento, imprime a stdout.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def main(argv: list[str]) -> int:
    from mobile.api import create_app

    schema = create_app().openapi()
    rendered = json.dumps(schema, indent=2, ensure_ascii=False, sort_keys=True)
    if argv:
        output = Path(argv[0])
        output.write_text(rendered + "\n", encoding="utf-8")
        print(f"OK: schema OpenAPI escrito en {output} ({len(schema['paths'])} rutas).")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
