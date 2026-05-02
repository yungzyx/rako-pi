#!/usr/bin/env bash
# Provisión inicial de la Raspberry Pi 4 para Rako.
#
# Uso (en la Pi, como usuario `rako` con sudo configurado):
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
  python3.12 python3.12-venv python3.12-dev python3-pip \
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
if [[ ! -d ".venv" ]]; then
  python3.12 -m venv .venv
fi

echo "==> Instalando dependencias de la Pi..."
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

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
       ANTHROPIC_API_KEY (Anthropic Console)
       GOOGLE_APPLICATION_CREDENTIALS (Google Cloud service account JSON)
       FIREBASE_CREDENTIALS_PATH (Firebase service account JSON)

  2. Probar el demo:
       ./scripts/rako.sh demo-turn "hola Rako"
       ./scripts/rako.sh demo-crisis-panic

  3. Para autostart en boot:
       sudo cp systemd/rako.service /etc/systemd/system/
       sudo systemctl daemon-reload
       sudo systemctl enable rako
       sudo systemctl start rako

  4. Ver logs:
       journalctl -u rako -f

EOF
