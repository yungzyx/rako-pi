#!/usr/bin/env bash
# Provisión inicial de la Raspberry Pi 4 para Rako.
#
# Uso (en la Pi, como usuario con sudo configurado):
#   git clone <repo> ~/rako-pi
#   cd ~/rako-pi
#   ./scripts/setup_pi.sh
#
# Idempotente: se puede correr múltiples veces. Cada paso verifica si
# ya está aplicado.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# ---------------------------------------------------------------------------
# 1. Sistema
# ---------------------------------------------------------------------------

echo "==> Actualizando paquetes del sistema..."
sudo apt update
sudo apt install -y \
  python3 python3-venv python3-dev python3-pip \
  sqlcipher libsqlcipher-dev \
  portaudio19-dev libsndfile1 \
  ffmpeg \
  i2c-tools \
  git curl

# ---------------------------------------------------------------------------
# 2. GPIO + audio: permisos para el usuario actual
# ---------------------------------------------------------------------------

echo "==> Agregando usuario a los grupos de hardware..."
sudo usermod -a -G gpio,i2c,spi,audio "$USER"

# ---------------------------------------------------------------------------
# 3. Python venv + dependencias
# ---------------------------------------------------------------------------

echo "==> Creando virtualenv..."
PYTHON_BIN="${PYTHON_BIN:-python3}"
PYTHON_VERSION="$($PYTHON_BIN - <<'PY'
import sys
print(f"{sys.version_info.major}.{sys.version_info.minor}")
PY
)"
case "$PYTHON_VERSION" in
  3.12|3.13)
    ;;
  *)
    echo "ERROR: Python $PYTHON_VERSION no soportado. Requiere 3.12 o 3.13." >&2
    exit 1
    ;;
esac
echo "==> Usando $PYTHON_BIN (Python $PYTHON_VERSION)"

if [[ ! -d ".venv" ]]; then
  "$PYTHON_BIN" -m venv .venv
fi

echo "==> Instalando dependencias de la Pi..."
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements-pi-lite.txt

# ---------------------------------------------------------------------------
# 4. Configuración (.env)
# ---------------------------------------------------------------------------

if [[ ! -f ".env" ]]; then
  echo "==> Creando .env desde plantilla..."
  cp .env.example .env
  echo "    EDITAR .env con credenciales reales antes de continuar."
fi

# Generar clave SQLCipher si no existe.
if grep -q "^SQLITE_ENCRYPTION_KEY=$" .env; then
  echo "==> Generando SQLITE_ENCRYPTION_KEY..."
  KEY=$(openssl rand -hex 32)
  # macOS-portable in-place sed
  if [[ "$(uname)" == "Darwin" ]]; then
    sed -i '' "s|^SQLITE_ENCRYPTION_KEY=$|SQLITE_ENCRYPTION_KEY=$KEY|" .env
  else
    sed -i "s|^SQLITE_ENCRYPTION_KEY=$|SQLITE_ENCRYPTION_KEY=$KEY|" .env
  fi
fi

# ---------------------------------------------------------------------------
# 5. Estado local: directorios
# ---------------------------------------------------------------------------

mkdir -p data chroma_db logs

# ---------------------------------------------------------------------------
# 6. Indexar el RAG si la vault está disponible
# ---------------------------------------------------------------------------

VAULT_PATH=$(grep '^OBSIDIAN_VAULT_PATH=' .env | cut -d'=' -f2-)
VAULT_PATH=${VAULT_PATH:-../Rako-kb}
if [[ -d "$VAULT_PATH" ]]; then
  echo "==> Indexando RAG desde $VAULT_PATH..."
  PYTHONPATH=src .venv/bin/python scripts/reindex_rag.py
else
  echo "==> Vault $VAULT_PATH no encontrada — omito reindex. Ejecutar luego:"
  echo "    PYTHONPATH=src .venv/bin/python scripts/reindex_rag.py"
fi

# ---------------------------------------------------------------------------
# 7. systemd unit (opcional — instalar a mano si se quiere autostart)
# ---------------------------------------------------------------------------

cat <<EOF

==> Setup completo.

Próximos pasos:

  1. Verificar y completar credenciales en .env:
       OPENAI_API_KEY (OpenAI Platform)
       ELEVENLABS_API_KEY + ELEVENLABS_VOICE_ID (ElevenLabs)
       GOOGLE_APPLICATION_CREDENTIALS (Google Cloud service account JSON)

  2. Probar el demo:
       ./scripts/rako.sh demo-turn "hola Rako"
       ./scripts/rako.sh demo-crisis-panic

  3. Provisionar este Rako para un usuario:
       ./scripts/rako-provision --name "Nico" --wifi-ssid "Casa" \\
         --whatsapp-number "+569..." --enable-whatsapp --enable-progress

  4. Para autostart en boot:
       sudo cp systemd/rako.service /etc/systemd/system/
       sudo systemctl daemon-reload
       sudo systemctl enable rako
       sudo systemctl start rako

  5. Ver logs:
       journalctl -u rako -f

EOF
