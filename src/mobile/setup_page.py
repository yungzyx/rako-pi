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
      --soft: #edf1f7;
      --text: #17202a;
      --muted: #647084;
      --line: #d8dde6;
      --ok: #0f8a5f;
      --todo: #b25500;
      --blocked: #b3261e;
      --manual: #3758a8;
      --primary: #2757d8;
    }
    @media (prefers-color-scheme: dark) {
      :root {
        --bg: #111418;
        --panel: #1a1f26;
        --soft: #222934;
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
      width: min(1080px, calc(100% - 32px));
      margin: 0 auto;
      padding: 28px 0 40px;
    }
    header, .stack { display: grid; gap: 10px; }
    h1, h2, h3, p { margin: 0; }
    h1 { font-size: clamp(1.7rem, 3vw, 2.4rem); }
    h2 { font-size: 1.05rem; }
    h3 { font-size: 0.95rem; }
    p, li { color: var(--muted); line-height: 1.45; }
    .grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 14px;
      align-items: start;
    }
    .panel {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 18px;
      margin: 14px 0;
    }
    .subpanel {
      background: var(--soft);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px;
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
      font-size: 0.86rem;
      margin-bottom: 6px;
    }
    input, select {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 11px 12px;
      font: inherit;
      background: transparent;
      color: var(--text);
    }
    input[type="checkbox"] {
      width: auto;
      margin: 0 8px 0 0;
    }
    button {
      border: 0;
      border-radius: 6px;
      padding: 11px 14px;
      font: inherit;
      font-weight: 650;
      color: white;
      background: var(--primary);
      cursor: pointer;
    }
    button.secondary {
      background: transparent;
      color: var(--primary);
      border: 1px solid currentColor;
    }
    button:disabled { opacity: 0.55; cursor: wait; }
    .row {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
    }
    .controls {
      display: grid;
      grid-template-columns: 1fr auto auto;
      gap: 10px;
      align-items: end;
    }
    .checks, .steps { display: grid; gap: 10px; }
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
    .done, .ok { color: var(--ok); }
    .todo, .optional, .warn { color: var(--todo); }
    .blocked, .fail { color: var(--blocked); }
    .manual { color: var(--manual); }
    .notes {
      padding-left: 18px;
      color: var(--muted);
      line-height: 1.45;
    }
    .message {
      min-height: 1.4em;
      margin-top: 10px;
      font-weight: 650;
    }
    .error { color: var(--blocked); }
    .success { color: var(--ok); }
    @media (max-width: 760px) {
      .grid, .row, .topline, .controls { grid-template-columns: 1fr; }
      .step { grid-template-columns: 1fr; }
      .badge { width: fit-content; }
    }
  </style>
</head>
<body>
  <main>
    <header>
      <h1>Configurar Rako</h1>
      <p>Completa el perfil, consentimiento, WhatsApp, WiFi y memoria inicial. No se guardan contraseñas WiFi en SQLite.</p>
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
          <label for="token">Token local</label>
          <input id="token" type="password" autocomplete="off" placeholder="Bearer token si RAKO_API_TOKEN está activo">
        </div>
        <button id="refresh" type="button" class="secondary">Actualizar</button>
        <button id="load-current" type="button">Cargar datos</button>
      </div>
      <p id="message" class="message"></p>
    </section>

    <section class="grid">
      <form id="profile-form" class="panel stack">
        <h2>Perfil</h2>
        <div class="row">
          <div>
            <label for="preferred_name">Nombre</label>
            <input id="preferred_name" name="preferred_name" autocomplete="given-name" maxlength="80">
          </div>
          <div>
            <label for="timezone">Zona horaria</label>
            <input id="timezone" name="timezone" value="America/Santiago" maxlength="64">
          </div>
        </div>
        <div class="row">
          <div>
            <label for="university">Universidad</label>
            <input id="university" name="university" maxlength="120">
          </div>
          <div>
            <label for="program">Carrera</label>
            <input id="program" name="program" maxlength="120">
          </div>
        </div>
        <button type="submit">Guardar perfil</button>
      </form>

      <form id="channels-form" class="panel stack">
        <h2>Canales y WiFi</h2>
        <div class="row">
          <div>
            <label for="wifi_ssid">WiFi SSID</label>
            <input id="wifi_ssid" name="wifi_ssid" maxlength="64">
          </div>
          <div>
            <label for="whatsapp_number">WhatsApp</label>
            <input id="whatsapp_number" name="whatsapp_number" placeholder="+569..." maxlength="32">
          </div>
        </div>
        <div class="row">
          <div>
            <label for="wellbeing_unit_name">Unidad bienestar</label>
            <input id="wellbeing_unit_name" name="wellbeing_unit_name" maxlength="160">
          </div>
          <div>
            <label for="wellbeing_unit_phone">Teléfono bienestar</label>
            <input id="wellbeing_unit_phone" name="wellbeing_unit_phone" maxlength="32">
          </div>
        </div>
        <button type="submit">Guardar canales</button>
      </form>

      <form id="consent-form" class="panel stack">
        <h2>Consentimiento</h2>
        <label><input type="checkbox" name="whatsapp_enabled"> Activar WhatsApp</label>
        <label><input type="checkbox" name="progress_reports_enabled"> Reportes de progreso</label>
        <label><input type="checkbox" name="proactive_messages_enabled"> Check-ins proactivos</label>
        <label><input type="checkbox" name="sensitive_memory_enabled"> Memoria sensible editable</label>
        <label><input type="checkbox" name="wellbeing_escalation_enabled"> Derivación a bienestar si corresponde</label>
        <button type="submit">Guardar consentimiento</button>
      </form>

      <form id="memory-form" class="panel stack">
        <h2>Memoria inicial</h2>
        <label for="memory_text">Preferencia o rutina útil</label>
        <input id="memory_text" name="text" maxlength="240" placeholder="Prefiero bloques cortos en la mañana">
        <div class="row">
          <div>
            <label for="memory_category">Categoría</label>
            <select id="memory_category" name="category">
              <option value="preference">preferencia</option>
              <option value="routine">rutina</option>
              <option value="study">estudio</option>
              <option value="motivation">motivación</option>
              <option value="boundary">límite</option>
            </select>
          </div>
          <div>
            <label for="memory_sensitivity">Sensibilidad</label>
            <select id="memory_sensitivity" name="sensitivity">
              <option value="normal">normal</option>
              <option value="sensitive">sensible</option>
            </select>
          </div>
        </div>
        <button type="submit">Agregar memoria</button>
      </form>
    </section>

    <section class="panel">
      <div class="topline">
        <div>
          <h2>Pasos de setup</h2>
          <p>Estado real calculado desde la configuración local.</p>
        </div>
        <button id="open-hotspot" type="button" class="secondary">Ver hotspot</button>
      </div>
      <div class="steps" id="steps" style="margin-top: 12px;"></div>
    </section>

    <section class="grid">
      <section class="panel">
        <h2>Checks de hardware</h2>
        <div id="hardware-checks" class="checks" style="margin-top: 12px;"></div>
      </section>
      <section class="panel">
        <h2>Plan de producción</h2>
        <div id="provisioning" class="stack" style="margin-top: 12px;"></div>
      </section>
    </section>

    <section class="panel">
      <h2>Privacidad</h2>
      <ul class="notes" id="privacy-notes"></ul>
    </section>
  </main>

  <script>
    const tokenInput = document.querySelector("#token");
    const refreshButton = document.querySelector("#refresh");
    const loadCurrentButton = document.querySelector("#load-current");
    const hotspotButton = document.querySelector("#open-hotspot");
    const title = document.querySelector("#summary-title");
    const detail = document.querySelector("#summary-detail");
    const percent = document.querySelector("#percent");
    const bar = document.querySelector("#bar");
    const steps = document.querySelector("#steps");
    const notes = document.querySelector("#privacy-notes");
    const message = document.querySelector("#message");
    const hardwareChecks = document.querySelector("#hardware-checks");
    const provisioning = document.querySelector("#provisioning");

    const profileForm = document.querySelector("#profile-form");
    const channelsForm = document.querySelector("#channels-form");
    const consentForm = document.querySelector("#consent-form");
    const memoryForm = document.querySelector("#memory-form");

    function headers(extra = {}) {
      const token = tokenInput.value.trim();
      return {
        ...(token ? { "Authorization": `Bearer ${token}` } : {}),
        ...extra,
      };
    }

    async function fetchJson(path, options = {}) {
      const response = await fetch(path, {
        ...options,
        headers: headers({
          ...(options.body ? { "Content-Type": "application/json" } : {}),
          ...(options.headers || {}),
        }),
      });
      if (!response.ok) {
        throw new Error(response.status === 401 ? "Token inválido o faltante." : `HTTP ${response.status}`);
      }
      return response.json();
    }

    function collectText(form) {
      const data = {};
      for (const field of new FormData(form).entries()) {
        const [key, value] = field;
        const clean = String(value).trim();
        if (clean) data[key] = clean;
      }
      return data;
    }

    function collectConsent(form) {
      const data = {};
      for (const input of form.querySelectorAll("input[type='checkbox']")) {
        data[input.name] = input.checked;
      }
      return data;
    }

    function setMessage(text, kind = "") {
      message.textContent = text;
      message.className = `message ${kind}`.trim();
    }

    function fillForm(form, payload) {
      for (const [key, value] of Object.entries(payload || {})) {
        const input = form.elements[key];
        if (!input) continue;
        if (input.type === "checkbox") input.checked = Boolean(value);
        else input.value = value || "";
      }
    }

    function render(flow) {
      const ready = flow.ready_for_user;
      title.textContent = ready ? "Rako listo para asignar" : "Rako todavía necesita configuración";
      detail.textContent = flow.next_action || "Solo queda realizar la prueba física manual antes de entregar.";
      percent.textContent = `${flow.completion_percent}%`;
      bar.style.width = `${flow.completion_percent}%`;
      steps.replaceChildren(...flow.steps.map(renderStep));
      notes.replaceChildren(...flow.privacy_notes.map((note) => {
        const item = document.createElement("li");
        item.textContent = note;
        return item;
      }));
      if (flow.warnings.length) setMessage(`Advertencias: ${flow.warnings.join(" · ")}`, "error");
    }

    function renderStep(step) {
      const article = document.createElement("article");
      article.className = "step";
      const badge = document.createElement("span");
      badge.className = `badge ${step.status}`;
      badge.textContent = step.status;
      const body = document.createElement("div");
      const heading = document.createElement("h3");
      heading.textContent = step.title;
      const detailText = document.createElement("p");
      detailText.textContent = step.detail;
      const action = document.createElement("p");
      action.textContent = step.action;
      body.append(heading, detailText, action);
      article.append(badge, body);
      return article;
    }

    function renderFactory(report) {
      const manualItems = report.acceptance.items.filter((item) => item.status === "manual");
      hardwareChecks.replaceChildren(...manualItems.map((item) => {
        const card = document.createElement("article");
        card.className = "subpanel";
        const heading = document.createElement("h3");
        heading.textContent = `${item.category}: ${item.name}`;
        const text = document.createElement("p");
        text.textContent = item.detail;
        card.append(heading, text);
        return card;
      }));
    }

    function renderProvisioning(plan) {
      const summary = document.createElement("div");
      summary.className = "subpanel";
      summary.innerHTML = `<h3>${plan.ready_for_handoff ? "Lista para entregar" : "Aún hay bloqueos"}</h3>
        <p>Imagen: ${plan.ready_for_image ? "lista" : "pendiente"} · Hotspot: ${plan.hotspot.status} · OTA: ${plan.update.decision}</p>`;
      const blockers = plan.steps
        .filter((step) => step.status === "fail" || step.status === "warn")
        .slice(0, 6)
        .map((step) => {
          const card = document.createElement("article");
          card.className = "subpanel";
          card.innerHTML = `<h3>${step.area}: ${step.name}</h3><p>${step.detail}</p><p>${step.action}</p>`;
          return card;
        });
      provisioning.replaceChildren(summary, ...blockers);
    }

    async function loadFlow() {
      refreshButton.disabled = true;
      setMessage("");
      try {
        render(await fetchJson("/setup/flow"));
        renderFactory(await fetchJson("/factory/report"));
        renderProvisioning(await fetchJson("/factory/provisioning-plan"));
      } catch (error) {
        title.textContent = "No pude leer el setup";
        detail.textContent = "Revisa que rako-api esté corriendo y que el token sea correcto.";
        setMessage(error.message, "error");
      } finally {
        refreshButton.disabled = false;
      }
    }

    async function loadCurrentConfig() {
      loadCurrentButton.disabled = true;
      try {
        const [profile, consent, channels] = await Promise.all([
          fetchJson("/user/profile"),
          fetchJson("/user/consent"),
          fetchJson("/user/channels"),
        ]);
        fillForm(profileForm, profile);
        fillForm(consentForm, consent);
        fillForm(channelsForm, channels);
        setMessage("Datos actuales cargados.", "success");
      } catch (error) {
        setMessage(error.message, "error");
      } finally {
        loadCurrentButton.disabled = false;
      }
    }

    async function submitJson(event, path, body) {
      event.preventDefault();
      const button = event.currentTarget.querySelector("button[type='submit']");
      button.disabled = true;
      try {
        await fetchJson(path, { method: "PATCH", body: JSON.stringify(body) });
        setMessage("Guardado.", "success");
        await loadFlow();
      } catch (error) {
        setMessage(error.message, "error");
      } finally {
        button.disabled = false;
      }
    }

    profileForm.addEventListener("submit", (event) => submitJson(event, "/user/profile", collectText(profileForm)));
    channelsForm.addEventListener("submit", (event) => submitJson(event, "/user/channels", collectText(channelsForm)));
    consentForm.addEventListener("submit", (event) => submitJson(event, "/user/consent", collectConsent(consentForm)));
    memoryForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const button = memoryForm.querySelector("button[type='submit']");
      button.disabled = true;
      try {
        await fetchJson("/user/memory", { method: "POST", body: JSON.stringify(collectText(memoryForm)) });
        memoryForm.reset();
        memoryForm.elements.category.value = "preference";
        memoryForm.elements.sensitivity.value = "normal";
        setMessage("Memoria agregada.", "success");
        await loadFlow();
      } catch (error) {
        setMessage(error.message, "error");
      } finally {
        button.disabled = false;
      }
    });
    hotspotButton.addEventListener("click", async () => {
      try {
        const plan = await fetchJson("/setup/hotspot/plan");
        setMessage(`Hotspot ${plan.ssid}: ${plan.status}. ${plan.setup_url}`, plan.status === "ready" ? "success" : "");
      } catch (error) {
        setMessage(error.message, "error");
      }
    });
    refreshButton.addEventListener("click", loadFlow);
    loadCurrentButton.addEventListener("click", loadCurrentConfig);
    loadFlow();
  </script>
</body>
</html>"""
