#!/usr/bin/env bash
# Wrapper del CLI de Rako para dev (mac/linux).
#
# Uso:
#   ./scripts/rako.sh demo-turn "me siento atascado"
#   ./scripts/rako.sh demo-crisis-panic
#   ./scripts/rako.sh purge-all

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ -d ".venv" ]]; then
  PY=".venv/bin/python"
else
  PY="python3.12"
fi

PYTHONPATH="$ROOT/src" "$PY" -m main "$@"
