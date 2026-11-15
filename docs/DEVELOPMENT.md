# Desarrollo y calidad

[Volver al proyecto](../README.md) · [Índice de documentación](README.md)

Los comandos se ejecutan desde la raíz del repositorio.

## Setup

### Desarrollo local (mac / linux, sin Pi)

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements-dev.txt   # stack liviano: tests + lint + API

cp .env.example .env
# rellenar credenciales; generar clave de cifrado con: openssl rand -hex 32
```

`requirements-dev.txt` es el mismo set que usa CI. El runtime de la Pi
es `requirements-pi-lite.txt` (`requirements.txt` es solo un puntero de
compatibilidad hacia él — el stack pesado del SER local quedó fuera por
decisión de arquitectura: local para lo que protege, cloud para lo que
encanta).
Hardware y APIs cloud se mockean en tests — la suite corre sin credenciales.

### Raspberry Pi (dispositivo real)

Guía completa paso a paso en [`INSTALL.md`](../INSTALL.md). Versión corta:

```bash
git clone https://github.com/yungzyx/rako-pi.git ~/rako-pi
cd ~/rako-pi
./scripts/setup_pi.sh      # apt + venv + deps + .env + clave SQLCipher + RAG
./scripts/rako-doctor      # salud: audio, I2C/OLED, credenciales, BD
.venv/bin/python scripts/checks.py safety   # bypass de crisis — no negociable
```

## Tests y calidad

```bash
python scripts/checks.py lint      # Ruff + format check, igual que CI
python scripts/checks.py test      # suite completa + cobertura ≥95%, igual que CI
python scripts/checks.py safety    # fixtures críticos de crisis + wiring real
python scripts/checks.py hygiene   # marcadores obsoletos, .gitignore, tamaños de archivo/función
python scripts/checks.py stress    # repite suites críticas para detectar flakiness
python scripts/checks.py all       # harness local completo
```

- Umbral de cobertura exigido por CI: **≥ 95%**.
- El job dedicado `safety-fixtures` corre `checks.py safety`: no solo el
  detector puro, también los tests de integración que verifican que el
  veto de crisis está cableado antes del LLM en cada punto de entrada
  (orquestador, loop de voz, WhatsApp). **Esta ruta no puede regresionar.**
- `hygiene` enforza además los límites de CLAUDE.md: ≤800 líneas por
  archivo y <50 por función (con lista cerrada de casos preexistentes).
