/* EVA — interfaz del subagente de seriedad de llamadas.
   Todos los datos provienen de la API local (src/web/server.py), que ejecuta
   el pipeline real (main.analyze_call) y lee data/outputs/*.json. */
(function () {
  "use strict";

  // ------------------------------------------------------------------
  // Vocabulario
  // ------------------------------------------------------------------
  const CATEGORY = {
    SERIA: { label: "Probable emergencia legítima", short: "Legítima probable", cls: "ok" },
    DUDOSA: { label: "Requiere verificación", short: "Requiere verificación", cls: "warn" },
    IMPROCEDENTE: { label: "Posible llamada improcedente", short: "Posible improcedente", cls: "alert" },
  };
  const CATEGORY_ORDER = ["SERIA", "DUDOSA", "IMPROCEDENTE"];
  const RECOMMENDATION = {
    continuar: "Continuar la atención",
    pedir_mas_informacion: "Pedir más información",
    escalar_humano: "Escalar a un operador humano",
    posible_improcedente: "Posible improcedente: verificar antes de actuar",
    sin_dato: "Sin dato",
  };
  const STAGE = {
    transcripcion: "Transcripción",
    analisis_acustico: "Análisis acústico de la voz",
    analisis_semantico: "Análisis de contenido, intención y coherencia",
    puntuacion: "Puntuación y política de decisión",
    guardado: "Guardado del resultado",
  };
  const MODE = { audio: "Audio", transcript_only: "Transcripción" };
  const INDICATORS = [
    ["seriousness_audio_score", "Seriedad estimada por la voz"],
    ["stress_vocal_score", "Estrés vocal"],
    ["urgency_score", "Urgencia"],
    ["nervousness_score", "Nerviosismo"],
    ["desperation_score", "Desesperación"],
    ["calm_score", "Calma"],
    ["aggression_score", "Agresividad acústica"],
    ["voice_instability_score", "Inestabilidad vocal"],
    ["voice_tremor_score", "Temblor de voz"],
    ["audio_reliability", "Confiabilidad del audio"],
  ];
  const SAFETY_TEXT =
    "Evaluación automatizada de señales, no una determinación definitiva. Una alerta no prueba que la llamada sea una broma y no debe usarse por sí sola para negar o retrasar la atención de una emergencia.";

  const ICON = {
    ok: '<svg viewBox="0 0 24 24" aria-hidden="true" fill="currentColor"><path d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20zm-1.4 14.6L6 12l1.4-1.4 3.2 3.2 6-6L18 9.2z"/></svg>',
    warn: '<svg viewBox="0 0 24 24" aria-hidden="true" fill="currentColor"><path d="M1 21h22L12 2zm12-3h-2v-2h2zm0-4h-2v-4h2z"/></svg>',
    alert: '<svg viewBox="0 0 24 24" aria-hidden="true" fill="currentColor"><path d="M15.7 3H8.3L3 8.3v7.4L8.3 21h7.4l5.3-5.3V8.3zM13 17h-2v-2h2zm0-4h-2V7h2z"/></svg>',
    info: '<svg viewBox="0 0 24 24" aria-hidden="true" fill="currentColor"><path d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20zm1 15h-2v-6h2zm0-8h-2V7h2z"/></svg>',
    check: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 16.2 4.8 12l-1.4 1.4L9 19 21 7l-1.4-1.4z"/></svg>',
    cross: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M19 6.4 17.6 5 12 10.6 6.4 5 5 6.4 10.6 12 5 17.6 6.4 19 12 13.4 17.6 19 19 17.6 13.4 12z"/></svg>',
  };

  // ------------------------------------------------------------------
  // Utilidades
  // ------------------------------------------------------------------
  const $ = (sel, root = document) => root.querySelector(sel);
  const view = document.getElementById("view");
  const tooltip = document.getElementById("tooltip");

  function esc(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }
  function pct(v, digits = 0) {
    return v == null || isNaN(v) ? "—" : (v * 100).toFixed(digits) + "%";
  }
  function num(v, digits = 2) {
    return v == null || isNaN(v) ? "—" : Number(v).toFixed(digits);
  }
  function fmtDate(iso, withTime = true) {
    if (!iso) return "—";
    const d = new Date(iso);
    if (isNaN(d)) return esc(iso);
    const opts = withTime
      ? { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" }
      : { day: "2-digit", month: "short" };
    return d.toLocaleString("es-MX", opts);
  }
  function fmtDuration(seconds) {
    if (seconds == null) return "—";
    const s = Math.round(seconds);
    const m = Math.floor(s / 60);
    return m ? `${m} min ${s % 60} s` : `${s} s`;
  }
  function humanize(flag) {
    return String(flag || "").replace(/_/g, " ");
  }
  function badge(categoria) {
    const c = CATEGORY[categoria];
    if (!c) return '<span class="badge neutral">Sin categoría</span>';
    return `<span class="badge ${c.cls}">${ICON[c.cls]}${esc(c.short)}</span>`;
  }
  function notice(kind, html) {
    return `<div class="notice ${kind}">${ICON[kind === "info" ? "info" : kind]}<div>${html}</div></div>`;
  }

  async function api(path, options = {}) {
    let response;
    try {
      response = await fetch(path, options);
    } catch (err) {
      throw new Error("No hay conexión con el servidor de EVA. Verifique que app.py siga en ejecución.");
    }
    let body = null;
    try {
      body = await response.json();
    } catch (err) {
      body = null;
    }
    if (!response.ok) {
      const message = (body && body.error) || `Error ${response.status} del servidor.`;
      const error = new Error(message);
      error.status = response.status;
      throw error;
    }
    return body;
  }

  function showTip(evt, html) {
    tooltip.innerHTML = html;
    tooltip.hidden = false;
    const pad = 14;
    const rect = tooltip.getBoundingClientRect();
    let x = evt.clientX + pad;
    let y = evt.clientY + pad;
    if (x + rect.width > window.innerWidth - 8) x = evt.clientX - rect.width - pad;
    if (y + rect.height > window.innerHeight - 8) y = evt.clientY - rect.height - pad;
    tooltip.style.left = x + "px";
    tooltip.style.top = y + "px";
  }
  function hideTip() {
    tooltip.hidden = true;
  }
  function bindTips(root) {
    root.querySelectorAll("[data-tip]").forEach((el) => {
      el.addEventListener("mousemove", (e) => showTip(e, el.getAttribute("data-tip")));
      el.addEventListener("mouseleave", hideTip);
      el.addEventListener("focus", () => {
        const r = el.getBoundingClientRect();
        showTip({ clientX: r.left + r.width / 2, clientY: r.top }, el.getAttribute("data-tip"));
      });
      el.addEventListener("blur", hideTip);
    });
  }

  // ------------------------------------------------------------------
  // Estado del sistema (barra lateral)
  // ------------------------------------------------------------------
  let systemStatus = null;
  async function refreshStatus() {
    const pill = document.getElementById("sys-pill");
    try {
      systemStatus = await api("/api/status");
      const map = {
        operativo: ["ok", "Sistema operativo"],
        degradado: ["warn", "Operativo con limitaciones"],
        verificando: ["", "Verificando dependencias…"],
        fuera_de_servicio: ["alert", "Fuera de servicio"],
      };
      const [cls, text] = map[systemStatus.estado] || ["warn", systemStatus.estado];
      const busy = systemStatus.worker && systemStatus.worker.busy;
      pill.className = "sys " + cls;
      pill.querySelector(".sys-label").textContent = busy ? text + " · analizando" : text;
      if (systemStatus.estado === "verificando") {
        clearTimeout(refreshStatus.again);
        refreshStatus.again = setTimeout(async () => {
          await refreshStatus();
          if (location.hash.replace(/^#\/?/, "").startsWith("panel") || !location.hash) {
            const box = document.getElementById("system-box");
            if (box && systemStatus) box.innerHTML = systemPanel(systemStatus);
          }
          if (document.getElementById("dep-warnings")) drawDependencyWarnings(analyzeState.tab === "file" && (!analyzeState.file || isAudioFile(analyzeState.file)));
        }, 3000);
      }
    } catch (err) {
      systemStatus = null;
      pill.className = "sys alert";
      pill.querySelector(".sys-label").textContent = "Sin conexión con el servidor";
    }
    return systemStatus;
  }

  // ------------------------------------------------------------------
  // Router
  // ------------------------------------------------------------------
  let viewToken = 0;
  function route() {
    hideTip();
    const hash = location.hash.replace(/^#\/?/, "") || "panel";
    const [name, param] = hash.split("/");
    document.querySelectorAll(".nav a").forEach((a) => {
      const r = a.dataset.route;
      a.classList.toggle("active", r === name || (name === "analisis" && r === "historial"));
      if (r === name) a.setAttribute("aria-current", "page");
      else a.removeAttribute("aria-current");
    });
    const token = ++viewToken;
    const render = { panel: renderDashboard, analizar: renderAnalyze, historial: renderHistory, analisis: renderDetail }[name];
    (render || renderDashboard)(token, param ? decodeURIComponent(param) : null);
    view.focus({ preventScroll: true });
    window.scrollTo(0, 0);
  }
  const isCurrent = (token) => token === viewToken;

  function renderError(message, retry) {
    view.innerHTML = `
      <div class="panel">${notice("alert", `<b>No se pudo cargar esta sección.</b> ${esc(message)}`)}
        <div class="actions"><button class="btn secondary" id="retry">Reintentar</button></div>
      </div>`;
    $("#retry").addEventListener("click", retry);
  }

  // ------------------------------------------------------------------
  // Panel principal
  // ------------------------------------------------------------------
  async function renderDashboard(token) {
    view.innerHTML = `<div class="loading">Cargando panel…</div>`;
    let stats, status, list;
    try {
      [stats, status, list] = await Promise.all([api("/api/stats"), refreshStatus(), api("/api/analyses")]);
    } catch (err) {
      if (isCurrent(token)) renderError(err.message, () => renderDashboard(viewToken));
      return;
    }
    if (!isCurrent(token)) return;
    const c = stats.categorias;
    const total = stats.total;
    const share = (k) => (total ? c[k] / total : null);

    view.innerHTML = `
      <div class="page-head">
        <div>
          <h1>Panel de monitoreo</h1>
          <p>Resumen de las llamadas evaluadas por el subagente. Las cifras se calculan con los resultados guardados en el directorio de resultados.</p>
        </div>
        <span class="updated">Último análisis: ${fmtDate(stats.ultimo_analisis)}</span>
      </div>

      <section class="kpis" aria-label="Indicadores principales">
        <div class="kpi kpi-total">
          <div class="kpi-label">Llamadas analizadas</div>
          <div class="kpi-value">${total}</div>
          <div class="kpi-note">${stats.modos.audio || 0} con audio · ${stats.modos.transcript_only || 0} solo transcripción</div>
        </div>
        ${CATEGORY_ORDER.map((k) => `
          <div class="kpi">
            <div class="kpi-label"><span class="ico ico-${CATEGORY[k].cls}">${ICON[CATEGORY[k].cls]}</span>${esc(CATEGORY[k].short)}</div>
            <div class="kpi-value">${c[k]}</div>
            <div class="kpi-note">${pct(share(k))} del total</div>
          </div>`).join("")}
        <div class="kpi">
          <div class="kpi-label">Tasa de alertas</div>
          <div class="kpi-value">${pct(stats.tasa_alerta, 1)}</div>
          <div class="kpi-note">llamadas marcadas como posible improcedente</div>
        </div>
      </section>

      <div class="grid grid-3">
        <section class="panel span-2">
          <h2>Clasificación de las llamadas</h2>
          <p class="sub">Proporción de cada categoría sobre ${total} llamadas.</p>
          ${total ? distributionBar(c, total) : emptyBlock("Aún no hay llamadas analizadas.", "Analice la primera llamada para ver la distribución.")}
          <h2 style="margin-top:22px">Actividad de los últimos 14 días</h2>
          <p class="sub">Llamadas analizadas por día y categoría.</p>
          <div id="trend"></div>
        </section>

        <section class="panel">
          <h2>Estado del sistema</h2>
          <p class="sub">Componentes que usa el pipeline en este equipo.</p>
          <div id="system-box">${systemPanel(status)}</div>
        </section>

        <section class="panel">
          <h2>Recomendaciones operativas</h2>
          <p class="sub">Salida de la política de decisión conservadora.</p>
          ${recommendationBars(stats.recomendaciones)}
        </section>

        <section class="panel">
          <h2>Desempeño medido</h2>
          <p class="sub">Exactitud de la recomendación frente a etiquetas esperadas.</p>
          ${evaluationBlock(stats.evaluacion)}
          <p class="sub" style="margin-top:12px">Confianza promedio de la categoría: <b class="num">${pct(stats.confianza_promedio)}</b></p>
        </section>

        <section class="panel">
          <h2>Análisis recientes</h2>
          <p class="sub">Los cinco más recientes.</p>
          ${recentList(list.items.slice(0, 5))}
        </section>
      </div>`;
    const trendBox = $("#trend");
    const drawTrend = () => { trendBox.innerHTML = trendChart(stats.tendencia, trendBox.clientWidth); bindTips(trendBox); };
    drawTrend();
    window.onresize = () => { if (isCurrent(token) && document.body.contains(trendBox)) drawTrend(); };
    bindTips(view);
  }

  function emptyBlock(title, text, action) {
    return `<div class="empty"><h3>${esc(title)}</h3><p>${esc(text)}</p>${action || '<a class="btn" href="#/analizar">Analizar una llamada</a>'}</div>`;
  }

  function distributionBar(c, total) {
    const segs = CATEGORY_ORDER.filter((k) => c[k] > 0).map((k) => {
      const tip = `<b>${esc(CATEGORY[k].label)}</b><br>${c[k]} llamadas · ${pct(c[k] / total, 1)}`;
      return `<span class="fill-${CATEGORY[k].cls}" style="flex:${c[k]}" data-tip="${esc(tip)}" tabindex="0" aria-label="${esc(CATEGORY[k].label)}: ${c[k]}"></span>`;
    }).join("");
    const legend = CATEGORY_ORDER.map((k) =>
      `<span><i class="fill-${CATEGORY[k].cls}"></i>${esc(CATEGORY[k].short)} <b class="num">${c[k]}</b> (${pct(c[k] / total)})</span>`).join("");
    return `<div class="distribution"><div class="dist-bar" role="img" aria-label="Distribución por categoría">${segs}</div><div class="legend">${legend}</div></div>`;
  }

  function trendChart(days, width) {
    const W = Math.max(280, Math.round(width || 640)), H = 180, padL = 28, padB = 24, padT = 8;
    const innerW = W - padL, innerH = H - padB - padT;
    const totals = days.map((d) => CATEGORY_ORDER.reduce((s, k) => s + d[k], 0));
    const max = Math.max(1, ...totals);
    const step = max <= 4 ? 1 : Math.ceil(max / 4);
    const top = Math.ceil(max / step) * step;
    const y = (v) => padT + innerH - (v / top) * innerH;
    const band = innerW / days.length;
    const bw = Math.min(24, band * 0.6);
    let grid = "";
    for (let v = 0; v <= top; v += step) {
      grid += `<line class="grid-line" x1="${padL}" x2="${W}" y1="${y(v)}" y2="${y(v)}"/>`;
      grid += `<text class="axis-text" x="${padL - 6}" y="${y(v) + 4}" text-anchor="end">${v}</text>`;
    }
    let bars = "", labels = "", hits = "";
    days.forEach((d, i) => {
      const x = padL + i * band + (band - bw) / 2;
      let acc = 0;
      const present = CATEGORY_ORDER.filter((k) => d[k] > 0);
      present.forEach((k, j) => {
        const y0 = y(acc), y1 = y(acc + d[k]);
        const h = Math.max(0, y0 - y1 - (j > 0 ? 2 : 0));
        const isTop = j === present.length - 1;
        bars += isTop
          ? `<path class="fill-${CATEGORY[k].cls}" d="${roundTop(x, y1, bw, h)}"/>`
          : `<rect class="fill-${CATEGORY[k].cls}" x="${x}" y="${y1}" width="${bw}" height="${h}"/>`;
        acc += d[k];
      });
      const date = new Date(d.fecha + "T12:00:00");
      if (i % 2 === (days.length - 1) % 2) {
        labels += `<text class="axis-text" x="${x + bw / 2}" y="${H - 6}" text-anchor="middle">${date.getDate()}/${date.getMonth() + 1}</text>`;
      }
      const tip = `<b>${date.toLocaleDateString("es-MX", { weekday: "long", day: "numeric", month: "long" })}</b><br>` +
        (totals[i] ? CATEGORY_ORDER.map((k) => `${esc(CATEGORY[k].short)}: ${d[k]}`).join("<br>") : "Sin análisis");
      hits += `<rect class="hit" x="${padL + i * band}" y="${padT}" width="${band}" height="${innerH}" data-tip="${esc(tip)}"/>`;
    });
    const legend = CATEGORY_ORDER.map((k) => `<span><i class="fill-${CATEGORY[k].cls}"></i>${esc(CATEGORY[k].short)}</span>`).join("");
    const sum = totals.reduce((a, b) => a + b, 0);
    const empty = sum ? "" : `<text class="axis-text" x="${padL + innerW / 2}" y="${padT + innerH / 2}" text-anchor="middle" style="font-size:13px">Sin análisis en los últimos 14 días</text>`;
    return `<div class="legend" style="margin:0 0 8px">${legend}</div>
      <svg class="chart" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" role="img" aria-label="Llamadas por día en los últimos 14 días: ${sum} en total">${grid}${bars}${labels}${hits}${empty}</svg>`;
  }
  function roundTop(x, y, w, h) {
    const r = Math.min(4, h, w / 2);
    if (h <= 0) return "";
    return `M${x},${y + h} V${y + r} Q${x},${y} ${x + r},${y} H${x + w - r} Q${x + w},${y} ${x + w},${y + r} V${y + h} Z`;
  }

  function recommendationBars(recs) {
    const entries = Object.entries(recs || {}).sort((a, b) => b[1] - a[1]);
    if (!entries.length) return `<p class="muted">Sin datos todavía.</p>`;
    const max = Math.max(...entries.map((e) => e[1]));
    return `<div class="hbars">${entries.map(([k, v]) => `
      <div class="hbar"><span>${esc(RECOMMENDATION[k] || humanize(k))}</span>
        <div class="hbar-track"><div class="hbar-fill" style="width:${(v / max) * 82}%"></div><span class="hbar-val">${v}</span></div>
      </div>`).join("")}</div>`;
  }

  function evaluationBlock(ev) {
    if (!ev) return `<p class="muted">No se encontró un reporte de evaluación en <code>reportes/</code>.</p>`;
    return `<div class="kpi-value num" style="margin:0">${pct(ev.exactitud, 1)}</div>
      <p class="sub" style="margin:4px 0 0">${ev.aciertos} de ${ev.total} guiones sintéticos con la recomendación esperada. Fuente: <code>${esc(ev.fuente)}</code>.</p>`;
  }

  function systemPanel(status) {
    if (!status) return notice("alert", "No se pudo consultar el estado del servidor.");
    const label = { operativo: "Operativo", degradado: "Operativo con limitaciones", verificando: "Verificando dependencias…", fuera_de_servicio: "Fuera de servicio" }[status.estado];
    const cls = { operativo: "ok", degradado: "warn", fuera_de_servicio: "alert" }[status.estado] || "info";
    const w = status.worker || {};
    const workerText = !w.alive ? "Procesador detenido" : w.busy ? `Analizando${w.queued ? ` · ${w.queued} en cola` : ""}` : "Procesador libre";
    return `
      <div class="state-line"><span class="ico-${cls}" style="width:18px;height:18px;display:inline-block">${ICON[cls]}</span>${esc(label)}</div>
      <p class="sub" style="margin:0 0 8px">${esc(workerText)}</p>
      <ul class="deps">${status.componentes.map((c) => {
        const icon = c.ok === true ? ["ico-ok", ICON.ok] : c.ok === false ? ["ico-warn", ICON.warn] : ["muted", ICON.info];
        const state = c.ok === true ? "disponible" : c.ok === false ? "no disponible" : "verificando…";
        return `
        <li><span class="${icon[0]}" style="width:18px;height:18px">${icon[1]}</span>
          <div><b>${esc(c.nombre)}</b> <span class="muted">· ${state}</span>
          ${c.ok === false ? `<div class="fix">Necesario para ${esc(c.requerido_para)}.${c.detalle ? ` Error: <code>${esc(c.detalle)}</code>.` : ""} Solución: <code>${esc(c.solucion)}</code></div>` : ""}</div>
        </li>`;
      }).join("")}</ul>
      ${status.python ? `<p class="sub" style="margin:10px 0 0">Python del servidor: <code>${esc(status.python.ejecutable)}</code> (${esc(status.python.version)}${status.python.entorno_virtual ? ", entorno virtual" : ", <b>fuera de un entorno virtual</b>"})</p>` : ""}`;
  }

  function recentList(items) {
    if (!items.length) return `<p class="muted">Todavía no hay análisis.</p>`;
    return `<ul class="facts">${items.map((it) => `
      <li><span><a class="row-link" href="#/analisis/${encodeURIComponent(it.id)}">${esc(it.source)}</a><br><span class="muted" style="font-size:12px">${fmtDate(it.generated_at)}</span></span>
      <span>${badge(it.categoria)}</span></li>`).join("")}</ul>`;
  }

  // ------------------------------------------------------------------
  // Análisis de llamadas
  // ------------------------------------------------------------------
  const analyzeState = { tab: "file", file: null, text: "", language: "es", model: "tiny", jobId: null, job: null, pollTimer: null, startedAt: null };

  async function renderAnalyze(token) {
    const status = systemStatus || (await refreshStatus());
    if (!isCurrent(token)) return;
    const formats = status ? status.formatos_audio.concat(status.formatos_texto) : [".wav", ".mp3", ".m4a", ".txt"];
    view.innerHTML = `
      <div class="page-head">
        <div>
          <h1>Analizar una llamada</h1>
          <p>Cargue la grabación o su transcripción. El sistema ejecuta el mismo pipeline que <code>main.py</code> y guarda el resultado en el historial.</p>
        </div>
      </div>
      <div class="grid grid-2">
        <section class="panel" aria-labelledby="in-title">
          <h2 id="in-title">Entrada</h2>
          <p class="sub">Audio (${esc(formats.filter((f) => f !== ".txt").join(", "))}) o transcripción .txt en UTF-8.</p>
          <div class="tabs" role="tablist">
            <button role="tab" id="tab-file" aria-selected="${analyzeState.tab === "file"}">Archivo</button>
            <button role="tab" id="tab-text" aria-selected="${analyzeState.tab === "text"}">Escribir transcripción</button>
          </div>
          <div id="input-area"></div>
          <div class="field-row">
            <label class="field">Idioma de la llamada
              <select id="language">
                <option value="es">Español</option>
                <option value="en">Inglés</option>
              </select>
            </label>
            <label class="field" id="model-field">Modelo de Whisper
              <select id="model">
                <option value="tiny">tiny · más rápido</option>
                <option value="base">base · equilibrado</option>
                <option value="small">small · más preciso</option>
              </select>
            </label>
          </div>
          <div id="dep-warnings" style="margin-top:14px"></div>
          <div class="actions">
            <button class="btn" id="submit">Analizar llamada</button>
            <span class="muted" id="form-msg" role="alert"></span>
          </div>
        </section>
        <section class="panel" aria-labelledby="prog-title">
          <h2 id="prog-title">Progreso del análisis</h2>
          <div id="progress"></div>
        </section>
      </div>
      <div id="result" style="margin-top:16px"></div>`;

    $("#language").value = analyzeState.language;
    $("#model").value = analyzeState.model;
    $("#language").addEventListener("change", (e) => (analyzeState.language = e.target.value));
    $("#model").addEventListener("change", (e) => (analyzeState.model = e.target.value));
    $("#tab-file").addEventListener("click", () => switchTab("file"));
    $("#tab-text").addEventListener("click", () => switchTab("text"));
    $("#submit").addEventListener("click", submitAnalysis);
    drawInputArea();
    drawProgress();
    if (analyzeState.job && analyzeState.job.status === "completado") showInlineResult(analyzeState.job.result_id);
  }

  function switchTab(tab) {
    analyzeState.tab = tab;
    $("#tab-file").setAttribute("aria-selected", tab === "file");
    $("#tab-text").setAttribute("aria-selected", tab === "text");
    drawInputArea();
  }

  function isAudioFile(file) {
    return file && !/\.txt$/i.test(file.name);
  }

  function drawInputArea() {
    const area = $("#input-area");
    if (analyzeState.tab === "text") {
      area.innerHTML = `<label class="field" for="text-input">Transcripción de la llamada</label>
        <textarea id="text-input" placeholder="Escriba o pegue lo que dijo la persona que llamó…">${esc(analyzeState.text)}</textarea>`;
      $("#text-input").addEventListener("input", (e) => (analyzeState.text = e.target.value));
    } else {
      const f = analyzeState.file;
      area.innerHTML = `<label class="drop" id="drop" tabindex="0">
          <strong>Arrastre aquí el archivo o haga clic para seleccionarlo</strong>
          <span>Máximo ${systemStatus ? systemStatus.max_upload_mb : 200} MB</span>
          <input type="file" id="file-input" accept=".wav,.mp3,.m4a,.flac,.ogg,.aac,.wma,.txt">
          ${f ? `<div class="file-chosen">${esc(f.name)} · ${(f.size / 1048576).toFixed(2)} MB</div>` : ""}
        </label>`;
      const drop = $("#drop"), input = $("#file-input");
      drop.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); input.click(); } });
      input.addEventListener("change", () => { analyzeState.file = input.files[0] || null; drawInputArea(); });
      ["dragenter", "dragover"].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.add("drag"); }));
      ["dragleave", "drop"].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.remove("drag"); }));
      drop.addEventListener("drop", (e) => { analyzeState.file = e.dataTransfer.files[0] || null; drawInputArea(); });
    }
    const audioSelected = analyzeState.tab === "file" && (!analyzeState.file || isAudioFile(analyzeState.file));
    $("#model-field").style.display = audioSelected ? "" : "none";
    drawDependencyWarnings(audioSelected);
  }

  function drawDependencyWarnings(audioSelected) {
    const box = $("#dep-warnings");
    if (!systemStatus) { box.innerHTML = ""; return; }
    const missing = Object.fromEntries(systemStatus.componentes.map((c) => [c.id, c.ok === false]));
    const detail = Object.fromEntries(systemStatus.componentes.map((c) => [c.id, c.detalle]));
    const msgs = [];
    if (audioSelected) {
      if (missing.whisper) msgs.push(`Whisper no se puede usar en el Python del servidor (<code>${esc(systemStatus.python ? systemStatus.python.ejecutable : "python")}</code>)${detail.whisper ? `: <code>${esc(detail.whisper)}</code>` : ""}. El audio se analizará sin transcripción y la categoría tenderá a «Requiere verificación». Use una transcripción .txt o corrija la instalación.`);
      if (missing.librosa) msgs.push("librosa no está instalado: no se extraerán indicadores de voz. Ejecute <code>pip install -r requirements.txt</code>.");
      if (missing.ffmpeg) msgs.push("FFmpeg no está en el PATH: los archivos .mp3 y .m4a podrían no decodificarse.");
    }
    if (missing.output_dir) msgs.push("El directorio de resultados no permite escritura; el análisis no podrá guardarse.");
    box.innerHTML = msgs.map((m) => notice("warn", m)).join("");
  }

  async function submitAnalysis() {
    const msg = $("#form-msg");
    msg.textContent = "";
    if (analyzeState.job && ["en_cola", "procesando"].includes(analyzeState.job.status)) {
      msg.textContent = "Ya hay un análisis en curso. Espere a que termine.";
      return;
    }
    const form = new FormData();
    if (analyzeState.tab === "text") {
      if (!analyzeState.text.trim()) { msg.textContent = "Escriba la transcripción antes de analizar."; return; }
      form.append("text", analyzeState.text);
    } else {
      if (!analyzeState.file) { msg.textContent = "Seleccione un archivo de audio o .txt."; return; }
      form.append("file", analyzeState.file);
    }
    form.append("language", analyzeState.language);
    form.append("model", analyzeState.model);

    const btn = $("#submit");
    btn.disabled = true;
    btn.textContent = "Enviando…";
    try {
      const job = await api("/api/analyze", { method: "POST", body: form });
      analyzeState.jobId = job.id;
      analyzeState.job = job;
      analyzeState.startedAt = Date.now();
      $("#result").innerHTML = "";
      drawProgress();
      pollJob();
    } catch (err) {
      msg.textContent = err.message;
    } finally {
      btn.disabled = false;
      btn.textContent = "Analizar llamada";
    }
  }

  function pollJob() {
    clearTimeout(analyzeState.pollTimer);
    const live = document.getElementById("nav-live");
    live.hidden = false;
    const tick = async () => {
      try {
        const job = await api(`/api/jobs/${analyzeState.jobId}`);
        analyzeState.job = job;
      } catch (err) {
        analyzeState.job = Object.assign({}, analyzeState.job, { status: "error", error: err.message });
      }
      const job = analyzeState.job;
      if ($("#progress")) drawProgress();
      if (job.status === "completado" || job.status === "error") {
        live.hidden = true;
        refreshStatus();
        if (job.status === "completado" && $("#result")) showInlineResult(job.result_id);
        return;
      }
      analyzeState.pollTimer = setTimeout(tick, 800);
    };
    tick();
  }

  function drawProgress() {
    const box = $("#progress");
    if (!box) return;
    const job = analyzeState.job;
    if (!job) {
      box.innerHTML = `<p class="sub">Aquí verá cada etapa del pipeline mientras se procesa la llamada.</p>
        <ol class="steps">${Object.values(STAGE).map((s) => `<li class="step"><span class="dot"></span><span>${esc(s)}</span></li>`).join("")}</ol>`;
      return;
    }
    const elapsed = analyzeState.startedAt ? Math.round((Date.now() - analyzeState.startedAt) / 1000) : null;
    const statusText = {
      en_cola: job.queue_position ? `En cola (posición ${job.queue_position})` : "En cola",
      procesando: "Procesando",
      completado: "Completado",
      error: "Error",
    }[job.status] || job.status;
    const stages = job.stages || Object.keys(STAGE);
    const steps = stages.map((s) => {
      let cls = "", mark = "";
      if (job.completed_stages && job.completed_stages.includes(s)) { cls = "done"; mark = ICON.check; }
      else if (job.stage === s && job.status === "procesando") cls = "current";
      else if (job.stage === s && job.status === "error") { cls = "failed"; mark = ICON.cross; }
      const right = cls === "current" && s === "transcripcion" && job.mode === "audio" ? '<span class="muted" style="font-size:12px">puede tardar varios minutos</span>' : "";
      return `<li class="step ${cls}"><span class="dot">${mark}</span><span>${esc(STAGE[s] || s)}</span>${right}</li>`;
    }).join("");
    let footer = "";
    if (job.status === "error") {
      footer = notice("alert", `<b>El análisis no se completó.</b> ${esc(job.error || "Error desconocido.")}`) +
        `<div class="actions"><button class="btn secondary" id="retry-job">Corregir y reintentar</button></div>`;
    } else if (job.status === "completado") {
      footer = notice("info", `Resultado guardado como <b>${esc(job.result_id)}</b>.`) +
        `<div class="actions"><a class="btn secondary" href="#/analisis/${encodeURIComponent(job.result_id)}">Abrir en el historial</a><button class="btn secondary" id="new-job">Analizar otra llamada</button></div>`;
    }
    box.innerHTML = `
      <div class="progress-meta">
        <span>Estado: <b>${esc(statusText)}</b></span>
        <span>Entrada: <b>${esc(job.source_name)}</b> (${esc(MODE[job.mode] || job.mode)})</span>
        ${elapsed != null && job.status !== "completado" && job.status !== "error" ? `<span>Tiempo: <b class="num">${elapsed} s</b></span>` : ""}
      </div>
      <ol class="steps" aria-label="Etapas del pipeline">${steps}</ol>
      <div style="margin-top:12px">${footer}</div>`;
    const retry = $("#retry-job");
    if (retry) retry.addEventListener("click", resetJob);
    const again = $("#new-job");
    if (again) again.addEventListener("click", () => { resetJob(); analyzeState.file = null; analyzeState.text = ""; drawInputArea(); });
  }

  function resetJob() {
    clearTimeout(analyzeState.pollTimer);
    analyzeState.job = null;
    analyzeState.jobId = null;
    if ($("#result")) $("#result").innerHTML = "";
    drawProgress();
  }

  async function showInlineResult(resultId) {
    const box = $("#result");
    if (!box) return;
    box.innerHTML = `<div class="loading">Cargando resultado…</div>`;
    try {
      const detail = await api(`/api/analyses/${encodeURIComponent(resultId)}`);
      if ($("#result") === box) {
        box.innerHTML = resultView(detail);
        bindTips(box);
      }
    } catch (err) {
      box.innerHTML = notice("alert", esc(err.message));
    }
  }

  // ------------------------------------------------------------------
  // Vista de resultado (compartida por Analizar y Detalle)
  // ------------------------------------------------------------------
  function resultView(detail) {
    const p = detail.payload;
    const cat = detail.category;
    const meta = CATEGORY[cat.categoria] || { label: cat.categoria, cls: "warn" };
    const score = p.score || {};
    const sem = p.semantic_analysis || {};
    const intent = p.intent_analysis || {};
    const coh = p.coherence_analysis || {};
    const ac = p.acoustic_features || {};
    const ind = ac.emergency_audio_indicators || {};
    const tr = p.transcription || {};
    const input = p.input || {};

    const warnings = (detail.warnings || []).map((w) => notice("warn", esc(w))).join("");

    const voiceMeters = INDICATORS.map(([k, label]) => meter(label, ind[k], k === "seriousness_audio_score" || k === "stress_vocal_score" || k === "urgency_score" || k === "desperation_score")).join("");
    const voiceFlags = (ind.indicator_flags || []).map((f) => `<span class="chip">${esc(humanize(f))}</span>`).join("");

    const completeness = sem.completeness_items || {};
    const compLabels = { has_location: "Ubicación", has_affected_people: "Personas afectadas", has_incident_type: "Tipo de incidente", has_minimum_detail: "Detalle mínimo (12+ palabras)" };

    return `
      <div class="stack">
        <section aria-label="Resultado de la evaluación">
          <div class="verdict ${meta.cls}">
            <div class="verdict-icon">${ICON[meta.cls]}</div>
            <div>
              <div class="verdict-kicker">Evaluación automatizada</div>
              <div class="verdict-title">${esc(meta.label)}</div>
              <div class="verdict-rec">Recomendación: <b>${esc(RECOMMENDATION[score.recommendation] || humanize(score.recommendation))}</b></div>
            </div>
            <div class="verdict-conf"><div class="v">${pct(cat.confianza)}</div><div class="l">confianza de la categoría</div></div>
          </div>
          <p class="safety">${esc(SAFETY_TEXT)}</p>
        </section>

        ${warnings ? `<section class="panel"><h2>Avisos del análisis</h2><p class="sub">Condiciones que reducen la fiabilidad de este resultado.</p>${warnings}</section>` : ""}

        <section class="grid grid-3" aria-label="Puntuaciones del modelo">
          <div class="panel">${bigMeter("Puntuación de seriedad", score.seriousness_score, "Indicios compatibles con una emergencia real.")}</div>
          <div class="panel">${bigMeter("Puntuación de improcedencia", score.improcedence_score, "Indicios de broma, incoherencia o ausencia de emergencia.")}</div>
          <div class="panel">${bigMeter("Confianza del pipeline", score.confidence, "Cantidad y calidad de la evidencia disponible.")}</div>
        </section>

        <section aria-label="Señales analizadas">
          <div class="readings">
            <div class="reading">
              <h3>Voz</h3>
              <p class="what">Indicadores paralingüísticos del audio.</p>
              ${ac.duration_seconds ? voiceMeters + (voiceFlags ? `<div class="group-label">Señales detectadas</div><div class="chips">${voiceFlags}</div>` : "")
                : `<p class="muted">${input.mode === "transcript_only" ? "No aplica: se analizó solo la transcripción." : "No se pudieron calcular los indicadores de voz."}</p>`}
            </div>
            <div class="reading">
              <h3>Contenido</h3>
              <p class="what">Palabras clave, completitud e intención del relato.</p>
              <div class="reading-score"><span class="v">${pct(sem.completeness_score)}</span><span class="l">completitud</span></div>
              <ul class="facts">${Object.keys(compLabels).map((k) => `<li><span class="k">${compLabels[k]}</span><span class="v">${completeness[k] ? "Sí" : "No"}</span></li>`).join("")}
                <li><span class="k">Intención estimada</span><span class="v">${esc(humanize(intent.intent))}</span></li>
                <li><span class="k">Palabras</span><span class="v num">${sem.word_count ?? "—"}</span></li></ul>
              ${chipGroup("Términos de alto riesgo", intent.high_risk_terms, true)}
              ${chipGroup("Palabras de emergencia", sem.emergency_keywords)}
              ${chipGroup("Tipo de incidente", sem.incident_keywords)}
              ${chipGroup("Términos de broma o burla", sem.joke_or_mockery_keywords, true)}
            </div>
            <div class="reading">
              <h3>Coherencia</h3>
              <p class="what">Consistencia interna del relato.</p>
              <div class="reading-score"><span class="v">${pct(coh.coherence_score)}</span><span class="l">coherencia</span></div>
              <ul class="facts">
                <li><span class="k">Oraciones</span><span class="v num">${coh.sentence_count ?? "—"}</span></li>
                <li><span class="k">Respuestas evasivas</span><span class="v num">${(coh.evasive_responses || []).length}</span></li>
                <li><span class="k">Contradicciones</span><span class="v num">${(coh.simple_contradictions || []).length}</span></li>
                <li><span class="k">Cambios de tema</span><span class="v num">${(coh.topic_shift_markers || []).length}</span></li>
              </ul>
              ${chipGroup("Evasivas", coh.evasive_responses, true)}
              ${chipGroup("Contradicciones", coh.simple_contradictions, true)}
              ${chipGroup("Cambios de tema", coh.topic_shift_markers)}
            </div>
          </div>
        </section>

        <div class="grid grid-2">
          <section class="panel">
            <h2>Evidencia considerada</h2>
            <p class="sub">${esc(cat.justificacion || "")}</p>
            ${(score.evidence || []).length ? `<ul class="evidence">${score.evidence.map((e) => `<li>${esc(e)}</li>`).join("")}</ul>` : '<p class="muted">El modelo no registró evidencia.</p>'}
          </section>
          <section class="panel">
            <h2>Transcripción</h2>
            <p class="sub">Motor: ${esc(tr.engine || "—")} · idioma: ${esc(tr.language || "—")} · estado: ${esc(humanize(tr.status || "—"))}</p>
            ${tr.text ? `<div class="transcript">${esc(tr.text)}</div>` : '<p class="muted">Sin texto transcrito.</p>'}
          </section>
        </div>

        <section class="panel">
          <details class="tech">
            <summary>Datos acústicos y metadatos</summary>
            <div class="kv-grid">
              <ul class="facts">
                <li><span class="k">Duración</span><span class="v">${fmtDuration(ac.duration_seconds)}</span></li>
                <li><span class="k">Calidad de audio</span><span class="v">${esc(humanize(ac.audio_quality || "—"))}</span></li>
                <li><span class="k">F0 estimada</span><span class="v num">${num(ac.estimated_f0_hz, 1)} Hz</span></li>
                <li><span class="k">Variación de F0</span><span class="v num">${num(ac.estimated_f0_std_hz, 1)} Hz</span></li>
              </ul>
              <ul class="facts">
                <li><span class="k">Energía media</span><span class="v num">${num(ac.mean_energy, 3)}</span></li>
                <li><span class="k">Proporción de silencio</span><span class="v num">${pct(ac.silence_ratio, 1)}</span></li>
                <li><span class="k">Pausas</span><span class="v num">${ac.pause_count ?? "—"}</span></li>
                <li><span class="k">Pausa más larga</span><span class="v num">${num(ac.longest_pause_seconds, 1)} s</span></li>
              </ul>
              <ul class="facts">
                <li><span class="k">Velocidad de habla</span><span class="v num">${num(ac.approx_speech_rate, 0)} pal/min</span></li>
                <li><span class="k">SNR aproximado</span><span class="v num">${num(ac.estimated_snr_db, 1)} dB</span></li>
                <li><span class="k">Jitter / shimmer</span><span class="v num">${num(ac.estimated_jitter_ratio, 3)} / ${num(ac.estimated_shimmer_ratio, 3)}</span></li>
                <li><span class="k">Centroide espectral</span><span class="v num">${num(ac.spectral_centroid_hz, 0)} Hz</span></li>
              </ul>
              <ul class="facts">
                <li><span class="k">Identificador</span><span class="v">${esc(detail.id)}</span></li>
                <li><span class="k">Fecha</span><span class="v">${fmtDate(p.generated_at)}</span></li>
                <li><span class="k">Entrada</span><span class="v">${esc(detail.source)} (${esc(MODE[input.mode] || input.mode || "—")})</span></li>
                <li><span class="k">Esquema</span><span class="v">${esc(p.schema_version || "1.0")}</span></li>
              </ul>
            </div>
            ${chipGroup("Anomalías acústicas", ac.acoustic_anomaly_flags)}
            <p class="sub" style="margin-top:12px">Archivo JSON: <code>${esc(detail.file)}</code></p>
          </details>
        </section>
      </div>`;
  }

  function meter(label, value, hot) {
    if (value == null) {
      return `<div class="meter na"><span class="name">${esc(label)}</span><span class="val">sin dato</span><div class="meter-track"></div></div>`;
    }
    const v = Math.max(0, Math.min(1, Number(value)));
    return `<div class="meter"><span class="name">${esc(label)}</span><span class="val">${v.toFixed(2)}</span>
      <div class="meter-track"><div class="meter-fill${hot && v >= 0.55 ? " hot" : ""}" style="width:${v * 100}%"></div></div></div>`;
  }
  function bigMeter(label, value, help) {
    return `<h2>${esc(label)}</h2><p class="sub">${esc(help)}</p>
      <div class="reading-score"><span class="v">${value == null ? "—" : Number(value).toFixed(2)}</span><span class="l">de 1.00</span></div>
      <div class="meter-track" style="height:8px"><div class="meter-fill" style="width:${value == null ? 0 : Math.max(0, Math.min(1, value)) * 100}%"></div></div>`;
  }
  function chipGroup(label, items, hot) {
    if (!items || !items.length) return "";
    return `<div class="group-label">${esc(label)}</div><div class="chips">${items.map((t) => `<span class="chip${hot ? " hot" : ""}">${esc(t)}</span>`).join("")}</div>`;
  }

  // ------------------------------------------------------------------
  // Historial
  // ------------------------------------------------------------------
  async function renderHistory(token) {
    view.innerHTML = `<div class="loading">Cargando historial…</div>`;
    let data;
    try {
      data = await api("/api/analyses");
    } catch (err) {
      if (isCurrent(token)) renderError(err.message, () => renderHistory(viewToken));
      return;
    }
    if (!isCurrent(token)) return;
    const items = data.items;
    view.innerHTML = `
      <div class="page-head">
        <div>
          <h1>Historial de análisis</h1>
          <p>Cada fila es un resultado guardado por el pipeline, ya sea desde esta interfaz o desde la terminal. Seleccione una fila para ver el detalle.</p>
        </div>
        <span class="updated">${items.length} resultados</span>
      </div>
      <section class="panel">
        ${items.length ? `
        <div class="filters">
          <label class="field">Mostrar
            <select id="filter-cat">
              <option value="">Todas las categorías</option>
              ${CATEGORY_ORDER.map((k) => `<option value="${k}">${esc(CATEGORY[k].short)}</option>`).join("")}
            </select>
          </label>
        </div>
        <div class="table-wrap"><table>
          <thead><tr><th>Fecha</th><th>Identificador</th><th>Entrada</th><th>Resultado</th><th>Confianza</th><th>Recomendación</th><th>Duración</th></tr></thead>
          <tbody id="hist-body"></tbody>
        </table></div>` : emptyBlock("El historial está vacío.", "Los resultados aparecerán aquí en cuanto analice una llamada.")}
      </section>`;
    if (!items.length) return;
    const body = $("#hist-body");
    const draw = (filter) => {
      const rows = items.filter((it) => !filter || it.categoria === filter);
      body.innerHTML = rows.length ? rows.map((it) => `
        <tr class="clickable" data-id="${esc(it.id)}">
          <td class="num">${fmtDate(it.generated_at)}</td>
          <td class="mono-id">${esc(it.id.replace("resultado_", ""))}</td>
          <td><a class="row-link" href="#/analisis/${encodeURIComponent(it.id)}">${esc(it.source)}</a><br><span class="muted" style="font-size:12px">${esc(MODE[it.mode] || it.mode || "—")}${it.has_warnings ? " · con avisos" : ""}</span></td>
          <td>${badge(it.categoria)}</td>
          <td class="num">${pct(it.confianza)}</td>
          <td>${esc(RECOMMENDATION[it.recommendation] || humanize(it.recommendation))}</td>
          <td class="num">${fmtDuration(it.duration_seconds)}</td>
        </tr>`).join("") : `<tr><td colspan="7" class="muted">No hay resultados en esta categoría.</td></tr>`;
    };
    draw("");
    $("#filter-cat").addEventListener("change", (e) => draw(e.target.value));
    body.addEventListener("click", (e) => {
      if (e.target.closest("a")) return;
      const tr = e.target.closest("tr[data-id]");
      if (tr) location.hash = `#/analisis/${encodeURIComponent(tr.dataset.id)}`;
    });
  }

  async function renderDetail(token, id) {
    view.innerHTML = `<div class="loading">Cargando análisis…</div>`;
    let detail;
    try {
      detail = await api(`/api/analyses/${encodeURIComponent(id || "")}`);
    } catch (err) {
      if (!isCurrent(token)) return;
      if (err.status === 404) {
        view.innerHTML = `<a class="back" href="#/historial">← Volver al historial</a><div class="panel">${emptyBlock("Este análisis no existe.", "Puede haberse movido o eliminado del directorio de resultados.", '<a class="btn" href="#/historial">Ir al historial</a>')}</div>`;
      } else {
        renderError(err.message, () => renderDetail(viewToken, id));
      }
      return;
    }
    if (!isCurrent(token)) return;
    view.innerHTML = `
      <a class="back" href="#/historial">← Volver al historial</a>
      <div class="page-head">
        <div>
          <h1>${esc(detail.source)}</h1>
          <p>Analizado el ${fmtDate(detail.payload.generated_at)} · ${esc(detail.id)}</p>
        </div>
      </div>
      ${resultView(detail)}`;
    bindTips(view);
  }

  // ------------------------------------------------------------------
  window.addEventListener("hashchange", route);
  refreshStatus();
  setInterval(refreshStatus, 15000);
  route();
})();
