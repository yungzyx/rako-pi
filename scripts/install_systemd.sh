#!/usr/bin/env bash
# Instala las unidades systemd de Rako renderizadas para ESTE usuario y
# ESTA copia del repo (las plantillas en systemd/ usan los tokens
# __RAKO_USER__ y __RAKO_DIR__, no rutas hardcodeadas).
#
# Uso (en la Pi, desde la raíz del repo):
#   ./scripts/install_systemd.sh              # instala rako-chat + rako-api
#   ./scripts/install_systemd.sh rako         # instala el loop `main run`
#   ./scripts/install_systemd.sh rako-api     # solo la API móvil
#   ./scripts/install_systemd.sh --no-enable rako-api
#                                             # instala sin habilitar/arrancar
#                                             # (para habilitar después, cuando
#                                             # .env/audio/OLED estén validados)
#
# Nota: rako.service y rako-chat.service compiten por el botón GPIO y el
# audio — las plantillas declaran Conflicts= entre sí, systemd no deja
# correr ambos a la vez.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RAKO_USER="${SUDO_USER:-$USER}"

ENABLE_UNITS=1
UNITS=()
for arg in "$@"; do
  if [[ "$arg" == "--no-enable" ]]; then
    ENABLE_UNITS=0
  else
    UNITS+=("$arg")
  fi
done
if [[ ${#UNITS[@]} -eq 0 ]]; then
  UNITS=(rako-chat rako-api)
fi

for unit in "${UNITS[@]}"; do
  template="$ROOT/systemd/${unit}.service"
  if [[ ! -f "$template" ]]; then
    echo "ERROR: no existe la plantilla $template" >&2
    echo "Unidades disponibles: rako, rako-chat, rako-api" >&2
    exit 1
  fi
done

if [[ ! -d "$ROOT/.venv" ]]; then
  echo "ERROR: no existe $ROOT/.venv — correr primero ./scripts/setup_pi.sh" >&2
  exit 1
fi

for unit in "${UNITS[@]}"; do
  echo "==> Instalando ${unit}.service (user=$RAKO_USER, dir=$ROOT)..."
  sed \
    -e "s|__RAKO_USER__|$RAKO_USER|g" \
    -e "s|__RAKO_DIR__|$ROOT|g" \
    "$ROOT/systemd/${unit}.service" \
    | sudo tee "/etc/systemd/system/${unit}.service" > /dev/null
done

echo "==> Recargando systemd..."
sudo systemctl daemon-reload

if [[ "$ENABLE_UNITS" -eq 1 ]]; then
  for unit in "${UNITS[@]}"; do
    echo "==> Habilitando y arrancando ${unit}..."
    sudo systemctl enable --now "$unit"
  done

  echo
  echo "==> Listo. Estado:"
  for unit in "${UNITS[@]}"; do
    sudo systemctl --no-pager --lines=0 status "$unit" || true
  done
else
  echo "==> Unidades instaladas sin habilitar (--no-enable). Cuando .env,"
  echo "    audio y OLED estén validados:"
  echo "      sudo systemctl enable --now ${UNITS[*]}"
fi

echo
echo "Logs en vivo:  journalctl -u ${UNITS[0]} -f"
