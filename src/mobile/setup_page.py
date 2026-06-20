"""Self-contained first-run setup page for a local Rako device."""

from __future__ import annotations


def render_setup_page() -> str:
    return """<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Rako Setup</title>
  <style>
    :root {
      color-scheme: light dark;
      --bg: #f6f7f9;
      --panel: #ffffff;
      --text: #17202a;
      --muted: #647084;
      --line: #d8dde6;
      --ok: #0f8a5f;
      --todo: #b25500;
      --blocked: #b3261e;
      --manual: #3758a8;
    }
    @media (prefers-color-scheme: dark) {
      :root {
        --bg: #111418;
        --panel: #1a1f26;
        --text: #eef2f7;
        --muted: #a9b3c2;
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
      width: min(920px, calc(100% - 32px));
      margin: 0 auto;
      padding: 28px 0 40px;
    }
    header {
      display: grid;
      gap: 10px;
      margin-bottom: 20px;
    }
    h1, h2, p { margin: 0; }
    h1 { font-size: clamp(1.7rem, 3vw, 2.4rem); }
    h2 { font-size: 1rem; }
    p { color: var(--muted); line-height: 1.45; }
    .panel {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 18px;
      margin: 14px 0;
    }
    .topline {
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 16px;
      align-items: center;
    }
    .meter {
      height: 12px;
      background: color-mix(in srgb, var(--line) 70%, transparent);
      border-radius: 999px;
      overflow: hidden;
      margin-top: 14px;
    }
    .bar {
      height: 100%;
      width: 0%;
      background: var(--ok);
      transition: width 180ms ease;
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
    .controls {
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 10px;
      align-items: end;
    }
    .steps {
      display: grid;
      gap: 10px;
    }
    .step {
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px;
      display: grid;
      grid-template-columns: auto 1fr;
      gap: 12px;
    }
    .badge {
      min-width: 78px;
      text-align: center;
      border-radius: 999px;
      padding: 5px 9px;
      font-size: 0.78rem;
      font-weight: 700;
      text-transform: uppercase;
      border: 1px solid currentColor;
    }
    .done { color: var(--ok); }
    .todo, .optional { color: var(--todo); }
    .blocked { color: var(--blocked); }
    .manual { color: var(--manual); }
    .notes {
      padding-left: 18px;
      color: var(--muted);
      line-height: 1.45;
    }
    .error {
      color: var(--blocked);
      font-weight: 650;
    }
    @media (max-width: 640px) {
      .topline, .controls { grid-template-columns: 1fr; }
      .step { grid-template-columns: 1fr; }
      .badge { width: fit-content; }
    }
  </style>
</head>
<body>
  <main>
    <header>
      <h1>Configurar Rako</h1>
      <p>Usa esta pantalla para revisar si el dispositivo está listo para un estudiante. No ingreses contraseñas WiFi aquí; la conexión real se hace con el flujo de red del sistema.</p>
    </header>

    <section class="panel">
      <div class="topline">
        <div>
          <h2 id="summary-title">Cargando estado...</h2>
          <p id="summary-detail">Consultando /setup/flow en esta Raspberry Pi.</p>
        </div>
        <strong id="percent">0%</strong>
      </div>
      <div class="meter" aria-label="avance de configuración">
        <div class="bar" id="bar"></div>
      </div>
    </section>

    <section class="panel">
      <div class="controls">
        <div>
          <label for="token">Token local opcional</label>
          <input id="token" type="password" autocomplete="off" placeholder="Bearer token si RAKO_API_TOKEN está activo">
        </div>
        <button id="refresh" type="button">Actualizar</button>
      </div>
      <p id="message" style="margin-top: 10px;"></p>
    </section>

    <section class="panel">
      <h2>Pasos</h2>
      <div class="steps" id="steps" style="margin-top: 12px;"></div>
    </section>

    <section class="panel">
      <h2>Privacidad</h2>
      <ul class="notes" id="privacy-notes"></ul>
    </section>
  </main>

  <script>
    const tokenInput = document.querySelector("#token");
    const refreshButton = document.querySelector("#refresh");
    const title = document.querySelector("#summary-title");
    const detail = document.querySelector("#summary-detail");
    const percent = document.querySelector("#percent");
    const bar = document.querySelector("#bar");
    const steps = document.querySelector("#steps");
    const notes = document.querySelector("#privacy-notes");
    const message = document.querySelector("#message");

    function headers() {
      const token = tokenInput.value.trim();
      return token ? { "Authorization": `Bearer ${token}` } : {};
    }

    function render(flow) {
      const ready = flow.ready_for_user;
      title.textContent = ready ? "Rako listo para asignar" : "Rako todavía necesita configuración";
      detail.textContent = flow.next_action || "Solo queda realizar la prueba física manual antes de entregar.";
      percent.textContent = `${flow.completion_percent}%`;
      bar.style.width = `${flow.completion_percent}%`;
      message.textContent = flow.warnings.length ? `Advertencias: ${flow.warnings.join(" · ")}` : "";
      message.className = flow.warnings.length ? "error" : "";
      steps.replaceChildren(...flow.steps.map(renderStep));
      notes.replaceChildren(...flow.privacy_notes.map((note) => {
        const item = document.createElement("li");
        item.textContent = note;
        return item;
      }));
    }

    function renderStep(step) {
      const article = document.createElement("article");
      article.className = "step";
      const badge = document.createElement("span");
      badge.className = `badge ${step.status}`;
      badge.textContent = step.status;
      const body = document.createElement("div");
      const heading = document.createElement("h2");
      heading.textContent = step.title;
      const detailText = document.createElement("p");
      detailText.textContent = step.detail;
      const action = document.createElement("p");
      action.textContent = step.action;
      body.append(heading, detailText, action);
      article.append(badge, body);
      return article;
    }

    async function loadFlow() {
      refreshButton.disabled = true;
      message.textContent = "";
      try {
        const response = await fetch("/setup/flow", { headers: headers() });
        if (!response.ok) {
          throw new Error(response.status === 401 ? "Token inválido o faltante." : `HTTP ${response.status}`);
        }
        render(await response.json());
      } catch (error) {
        title.textContent = "No pude leer el setup";
        detail.textContent = "Revisa que rako-api esté corriendo y que el token sea correcto.";
        message.textContent = error.message;
        message.className = "error";
      } finally {
        refreshButton.disabled = false;
      }
    }

    refreshButton.addEventListener("click", loadFlow);
    loadFlow();
  </script>
</body>
</html>"""
