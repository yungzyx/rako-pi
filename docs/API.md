# API local y WhatsApp

[Volver al proyecto](../README.md) · [Índice de documentación](README.md)

Los comandos se ejecutan desde la raíz del repositorio.

## API local para la app móvil

```bash
./scripts/rako-api          # uvicorn en 127.0.0.1:8765
```

La documentación interactiva vive en `http://127.0.0.1:8765/docs` (OpenAPI).
Para exportar el contrato completo (por ejemplo, para generar el cliente
Flutter):

```bash
.venv/bin/python scripts/export_openapi.py
```

Grupos de endpoints (≈50 rutas, detalle en `/docs`):

| Grupo | Qué cubre |
| --- | --- |
| `core` | `/health`, `/status`, `/pairing/info` (datos públicos de emparejamiento) |
| `setup` | primer encendido: `/setup`, `/setup/flow`, `/setup/first-run`, WiFi, hotspot, QR |
| `user` | perfil, consentimiento, canales, memoria editable, export, borrado total |
| `productividad` | tareas, `/focus/start`, progreso diario/semanal, `/coach/plan` |
| `factory` | reporte, provisioning-plan, install-plan (dry-run por defecto), checks de hardware |
| `device` | identidad de placa, heartbeat, reset de usuario, OTA (`/update/*`) |
| `whatsapp` | envíos internos, plantillas, webhook de Meta (verificación + firma) |
| `observabilidad` | `/observability`, `/security/audit`, `/support/bundle`, `/fleet/snapshot` |

Seguridad de la API:

- Escucha solo en `127.0.0.1:8765` por defecto (`RAKO_API_HOST`/`RAKO_API_PORT`).
- Con `RAKO_API_TOKEN` definido, todo excepto `/health` y `/pairing/info`
  exige `Authorization: Bearer <token>`; fuera de `dev` el token es
  **obligatorio**.
- Fuera de `dev`, el arranque aborta si la base SQLite no está cifrada
  (gate de SQLCipher en el lifespan).
- `POST /user/delete-all` ejecuta **borrado total real**: config de
  producto, tareas, interacciones, estados de ánimo, logros y journal de
  crisis (`Database.purge_all_user_data()`), con efecto inmediato.
- La contraseña WiFi nunca se persiste; `nmcli` solo se ejecuta con
  `apply=true` + `RAKO_WIFI_APPLY_ENABLED=1` (ídem hotspot con
  `RAKO_SETUP_HOTSPOT_ENABLED=1`).

## Canal WhatsApp

Canal de producto completo sobre WhatsApp Business Cloud API
(`src/channels/whatsapp/`): check-ins, menú de acciones, reportes de
progreso con conteos (nunca títulos de tareas), memoria editable
(`recuerda que…`, `qué sabes de mí`, `olvida…`), configuración, pausa de
mensajes, export y borrado con confirmación.

Reglas de privacidad del canal (detalle en [`CLAUDE.md`](../CLAUDE.md) §4.1):

- Solo memorias `sensitivity=normal` salen por WhatsApp; de las sensibles
  solo se informa la cantidad.
- El remitente debe coincidir con el número emparejado antes de exponer
  datos o ejecutar borrado. Un número no emparejado solo puede recibir el
  protocolo de crisis o una respuesta genérica.
- El webhook de Meta se valida por firma HMAC (`X-Hub-Signature-256`)
  antes de procesar cualquier payload; fuera de `dev`,
  `WHATSAPP_CLOUD_APP_SECRET` es obligatorio.
- La detección de crisis corre **antes** que cualquier otra rama y usa el
  mismo detector curado que la voz.

Configuración (sin credenciales usa un cliente en memoria para desarrollo):

```bash
WHATSAPP_CLIENT=cloud
WHATSAPP_CLOUD_ACCESS_TOKEN=...
WHATSAPP_CLOUD_PHONE_NUMBER_ID=...
WHATSAPP_CLOUD_VERIFY_TOKEN=...
WHATSAPP_CLOUD_APP_SECRET=...
```

### Smart check-ins

El scheduler decide si corresponde un check-in proactivo respetando
consentimiento, horario silencioso, intervalo mínimo, actividad reciente y
**crisis recientes** (no compite con el protocolo de seguridad):

```bash
./scripts/rako.sh smart-checkin --dry-run
./scripts/rako.sh smart-checkin
```

Requiere `whatsapp_enabled=true`, `proactive_messages_enabled=true` y
`whatsapp_number` configurado.
