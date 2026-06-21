"""Self-contained local factory/admin dashboard."""

from __future__ import annotations


def render_factory_page() -> str:
    return """<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Rako Factory</title>
  <style>
    :root {
      color-scheme: light dark;
      --bg: #f4f6f8;
      --panel: #ffffff;
      --text: #17202a;
      --muted: #667085;
      --line: #d8dde6;
      --ok: #0f8a5f;
      --warn: #a15c00;
      --fail: #b3261e;
      --manual: #3758a8;
    }
    @media (prefers-color-scheme: dark) {
      :root {
        --bg: #101418;
        --panel: #1a1f26;
        --text: #eef2f7;
        --muted: #aab4c2;
        --line: #323a46;
      }
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: var(--bg);
      color: var(--text);
    }
    main {
      width: min(1100px, calc(100% - 32px));
      margin: 0 auto;
      padding: 28px 0 42px;
    }
    h1, h2, p { margin: 0; }
    h1 { font-size: clamp(1.7rem, 3vw, 2.5rem); }
    h2 { font-size: 1rem; }
    p { color: var(--muted); line-height: 1.45; }
    .panel {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 18px;
      margin: 14px 0;
    }
    .grid {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px;
    }
    .metric {
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px;
    }
    .metric strong {
      display: block;
      font-size: 1.5rem;
      margin-top: 4px;
    }
    .controls {
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 10px;
      align-items: end;
    }
    label {
      display: block;
      color: var(--muted);
      font-size: 0.9rem;
      margin-bottom: 6px;
    }
    input {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 11px 12px;
      font: inherit;
      background: transparent;
      color: var(--text);
    }
    button {
      border: 0;
      border-radius: 6px;
      padding: 11px 14px;
      font: inherit;
      font-weight: 650;
      color: white;
      background: #2757d8;
      cursor: pointer;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      margin-top: 12px;
    }
    th, td {
      border-bottom: 1px solid var(--line);
      padding: 10px 8px;
      text-align: left;
      vertical-align: top;
    }
    th { color: var(--muted); font-weight: 650; }
    .ok { color: var(--ok); }
    .warn { color: var(--warn); }
    .fail { color: var(--fail); }
    .manual { color: var(--manual); }
    .error { color: var(--fail); font-weight: 650; }
    @media (max-width: 760px) {
      .grid, .controls { grid-template-columns: 1fr; }
      table { font-size: 0.92rem; }
    }
  </style>
</head>
<body>
  <main>
    <header>
      <h1>Rako Factory</h1>
      <p>Panel local para revisar una placa antes de entregarla. No muestra secretos.</p>
    </header>

    <section class="panel">
      <div class="controls">
        <div>
          <label for="token">Token local</label>
          <input id="token" type="password" autocomplete="off" placeholder="Bearer token si está activo">
        </div>
        <button id="refresh" type="button">Actualizar</button>
      </div>
      <p id="message" style="margin-top: 10px;"></p>
    </section>

    <section class="panel">
      <h2>Resumen</h2>
      <div class="grid" style="margin-top: 12px;">
        <div class="metric"><p>Entrega</p><strong id="handoff">-</strong></div>
        <div class="metric"><p>Setup</p><strong id="setup">-</strong></div>
        <div class="metric"><p>Bloqueos</p><strong id="failures">-</strong></div>
        <div class="metric"><p>Manual</p><strong id="manual">-</strong></div>
      </div>
    </section>

    <section class="panel">
      <h2>Dispositivo</h2>
      <p id="device">Cargando...</p>
      <p id="assignment">Cargando asignación...</p>
      <p id="heartbeat">Cargando heartbeat...</p>
      <p id="update">Cargando versión...</p>
    </section>

    <section class="panel">
      <h2>Checklist</h2>
      <table>
        <thead><tr><th>Categoría</th><th>Check</th><th>Estado</th><th>Detalle</th></tr></thead>
        <tbody id="items"></tbody>
      </table>
    </section>
  </main>

  <script>
    const tokenInput = document.querySelector("#token");
    const refreshButton = document.querySelector("#refresh");
    const message = document.querySelector("#message");
    const items = document.querySelector("#items");

    function headers() {
      const token = tokenInput.value.trim();
      return token ? { "Authorization": `Bearer ${token}` } : {};
    }

    async function fetchJson(path) {
      const response = await fetch(path, { headers: headers() });
      if (!response.ok) {
        throw new Error(response.status === 401 ? "Token inválido o faltante." : `${path}: HTTP ${response.status}`);
      }
      return response.json();
    }

    function render(report, update) {
      document.querySelector("#handoff").textContent = report.ready_for_handoff ? "OK" : "NO";
      document.querySelector("#handoff").className = report.ready_for_handoff ? "ok" : "fail";
      document.querySelector("#setup").textContent = `${report.setup.completion_percent}%`;
      document.querySelector("#failures").textContent = report.automatic_failures;
      document.querySelector("#failures").className = report.automatic_failures ? "fail" : "ok";
      document.querySelector("#manual").textContent = report.manual_items;
      const identity = report.identity || {};
      const heartbeat = report.heartbeat || {};
      document.querySelector("#device").textContent =
        `ID: ${report.device_id || "sin ID"} · serial: ${identity.serial || "sin serial"} · lote: ${identity.lot || "sin lote"}`;
      document.querySelector("#assignment").textContent =
        `Asignado a: ${identity.assigned_user_label || "sin asignar"} · env: ${report.environment}`;
      document.querySelector("#heartbeat").textContent =
        heartbeat.at ? `Último heartbeat: ${heartbeat.at} · ${heartbeat.status}` : "Sin heartbeat registrado";
      document.querySelector("#update").textContent =
        `Versión: ${update.app_version} · canal: ${update.release_channel} · build: ${update.build_sha || "sin build"} · generado: ${report.generated_at}`;
      items.replaceChildren(...report.acceptance.items.map((item) => {
        const row = document.createElement("tr");
        row.innerHTML = `<td>${item.category}</td><td>${item.name}</td><td class="${item.status}">${item.status}</td><td>${item.detail}</td>`;
        return row;
      }));
    }

    async function load() {
      refreshButton.disabled = true;
      message.textContent = "";
      try {
        const [report, update] = await Promise.all([
          fetchJson("/factory/report"),
          fetchJson("/update/status"),
        ]);
        render(report, update);
      } catch (error) {
        message.textContent = error.message;
        message.className = "error";
      } finally {
        refreshButton.disabled = false;
      }
    }

    refreshButton.addEventListener("click", load);
    load();
  </script>
</body>
</html>"""
