/**
 * Controlador de Frontend para el Asistente de MIRA CU-1 (v3.0).
 * Maneja llamadas a API, render de chat, trazas MCP, inspector de citas y guion D1-D8.
 */

let activeUser = {
  usuario_id: "U-01",
  org_id: "ORG-01",
  rol: "operador",
  nombre: "Paula Rojas",
  org_nombre: "Seguros Cordillera Austral"
};

let currentCases = [];
let corpusInventory = [];
let evaluationData = null;

document.addEventListener("DOMContentLoaded", async () => {
  await cargarCorpus();
  await cargarCasos();
  await cargarEvaluacion();
});

async function cargarCorpus() {
  try {
    const res = await fetch("/api/corpus");
    const data = await res.json();
    corpusInventory = data.inventario || [];
  } catch (err) {
    console.error("Error al cargar corpus:", err);
  }
}

async function cargarCasos() {
  try {
    const res = await fetch(`/api/casos?usuario_id=${activeUser.usuario_id}`);
    const data = await res.json();
    currentCases = data.casos || [];
    renderCasos();
  } catch (err) {
    console.error("Error al cargar casos:", err);
  }
}

async function cargarEvaluacion() {
  try {
    const res = await fetch("/evaluation/evaluation_report.json");
    if (res.ok) {
      evaluationData = await res.json();
    }
  } catch (e) {
    console.log("No se pudo pre-cargar reporte JSON localmente");
  }
}

function cambiarUsuario() {
  const select = document.getElementById("user-select");
  const opt = select.options[select.selectedIndex];
  activeUser.usuario_id = opt.value;
  activeUser.org_id = opt.getAttribute("data-org");
  activeUser.rol = opt.getAttribute("data-rol");
  activeUser.nombre = opt.text.split("(")[0].trim();

  const orgBanner = document.getElementById("org-banner");
  if (activeUser.org_id === "ORG-01") {
    activeUser.org_nombre = "Seguros Cordillera Austral";
  } else if (activeUser.org_id === "ORG-02") {
    activeUser.org_nombre = "Clínica Bahía Serena";
  } else {
    activeUser.org_nombre = "Banco Mirador del Sur";
  }
  orgBanner.innerText = `${activeUser.org_nombre} (${activeUser.org_id})`;

  // Refrescar casos de la organización conectada (PR-7)
  cargarCasos();

  agregarMensajeSistema(
    `🔄 Sesión conmutada: Ahora interactúa como **${activeUser.nombre}** (${activeUser.rol.toUpperCase()}) en **${activeUser.org_nombre}**. ` +
    `Aislamiento multitenant activo conforme al Principio PR-7.`
  );
}

function renderCasos() {
  const container = document.getElementById("cases-list");
  const countBadge = document.getElementById("case-count");
  container.innerHTML = "";
  countBadge.innerText = `${currentCases.length} casos`;

  currentCases.forEach(c => {
    const card = document.createElement("div");
    card.className = "p-2.5 rounded-xl bg-slate-900 hover:bg-slate-800/90 border border-slate-800/80 cursor-pointer transition flex flex-col space-y-1.5 shadow-sm";
    card.onclick = () => consultarCasoDirecto(c.caso_id);

    let badgeColor = "bg-slate-800 text-slate-300";
    if (c.estado === "en_revision") badgeColor = "bg-amber-950 text-amber-300 border border-amber-800/60";
    if (c.estado === "aprobado_automatico") badgeColor = "bg-emerald-950 text-emerald-300 border border-emerald-800/60";
    if (c.estado === "solicitud_antecedentes") badgeColor = "bg-indigo-950 text-indigo-300 border border-indigo-800/60";
    if (c.estado === "escalado") badgeColor = "bg-rose-950 text-rose-300 border border-rose-800/60";

    card.innerHTML = `
      <div class="flex items-center justify-between">
        <span class="font-mono font-bold text-white text-xs">${c.caso_id}</span>
        <span class="text-[10px] font-mono px-1.5 py-0.5 rounded ${badgeColor}">${c.estado}</span>
      </div>
      <div class="flex items-center justify-between text-[11px] text-slate-400">
        <span>Puntaje: <strong class="text-slate-200">${c.puntaje ?? 'N/A'}</strong></span>
        <span>Vence: <strong class="text-slate-200">${c.vence_el || 'S/F'}</strong></span>
      </div>
      <p class="text-[10px] text-slate-400 line-clamp-2 leading-tight">${c.motivo_derivacion || 'Sin motivo de derivación registrado'}</p>
    `;
    container.appendChild(card);
  });
}

function consultarCasoDirecto(casoId) {
  const input = document.getElementById("query-input");
  input.value = `¿Por qué se derivó el caso ${casoId} y qué reglas aplican según sus señales?`;
  document.getElementById("chat-form").requestSubmit();
}

async function enviarMensaje(e) {
  e.preventDefault();
  const input = document.getElementById("query-input");
  const query = input.value.trim();
  if (!query) return;

  agregarMensajeUsuario(query);
  input.value = "";
  input.focus();

  const sendBtn = document.getElementById("send-btn");
  sendBtn.disabled = true;

  const placeholderId = agregarMensajeCargando();

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        query: query,
        usuario_id: activeUser.usuario_id,
        org_id: activeUser.org_id,
        rol: activeUser.rol
      })
    });

    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      eliminarMensaje(placeholderId);
      agregarMensajeError(errData.detail || "Error de comunicación con el servicio del Asistente.");
      return;
    }

    const data = await res.json();
    eliminarMensaje(placeholderId);
    agregarMensajeAsistente(data);

  } catch (error) {
    eliminarMensaje(placeholderId);
    agregarMensajeError(`No se pudo conectar con el servidor: ${error.message}`);
  } finally {
    sendBtn.disabled = false;
  }
}

function agregarMensajeUsuario(texto) {
  const container = document.getElementById("chat-messages");
  const msg = document.createElement("div");
  msg.className = "flex items-start justify-end space-x-3";
  msg.innerHTML = `
    <div class="max-w-2xl bg-indigo-600 text-white rounded-2xl rounded-tr-sm p-4 text-sm shadow-md">
      <div class="text-[11px] font-semibold text-indigo-200 mb-1 flex items-center justify-between">
        <span>${activeUser.nombre} (${activeUser.rol})</span>
        <span class="font-mono text-[10px] text-indigo-200/80">${activeUser.org_id}</span>
      </div>
      <p class="leading-relaxed">${escapeHtml(texto)}</p>
    </div>
    <div class="w-8 h-8 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center text-xs text-indigo-300 font-bold shrink-0">
      ${activeUser.nombre.charAt(0)}
    </div>
  `;
  container.appendChild(msg);
  scrollAbajo();
}

function agregarMensajeCargando() {
  const container = document.getElementById("chat-messages");
  const id = `loading-${Date.now()}`;
  const msg = document.createElement("div");
  msg.id = id;
  msg.className = "flex items-start space-x-3 max-w-3xl";
  msg.innerHTML = `
    <div class="w-8 h-8 rounded-full bg-indigo-600 flex items-center justify-center text-white font-bold text-xs shrink-0 animate-pulse">
      AI
    </div>
    <div class="bg-slate-800/80 border border-slate-700/80 rounded-2xl rounded-tl-sm p-4 text-xs text-slate-400 flex items-center space-x-3">
      <svg class="animate-spin h-4 w-4 text-indigo-400" viewBox="0 0 24 24" fill="none">
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"></path>
      </svg>
      <span>Consultando base de datos MCP y recuperando fragmentos del corpus RAG...</span>
    </div>
  `;
  container.appendChild(msg);
  scrollAbajo();
  return id;
}

function agregarMensajeError(mensaje) {
  const container = document.getElementById("chat-messages");
  const msg = document.createElement("div");
  msg.className = "flex items-start space-x-3 max-w-3xl";
  msg.innerHTML = `
    <div class="w-8 h-8 rounded-full bg-rose-600 flex items-center justify-center text-white font-bold text-xs shrink-0">
      !
    </div>
    <div class="bg-rose-950/70 border border-rose-800 rounded-2xl rounded-tl-sm p-4 text-sm text-rose-200">
      <h4 class="font-bold text-rose-100 mb-1 flex items-center space-x-1">
        <span>Error en Servicio</span>
      </h4>
      <p class="leading-relaxed text-xs">${escapeHtml(mensaje)}</p>
    </div>
  `;
  container.appendChild(msg);
  scrollAbajo();
}

function agregarMensajeSistema(texto) {
  const container = document.getElementById("chat-messages");
  const msg = document.createElement("div");
  msg.className = "flex justify-center my-2";
  msg.innerHTML = `
    <div class="px-4 py-2 rounded-xl bg-slate-950/80 border border-slate-800 text-xs text-indigo-300 font-sans shadow-sm flex items-center space-x-2">
      <svg class="w-4 h-4 text-indigo-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
      <span>${texto}</span>
    </div>
  `;
  container.appendChild(msg);
  scrollAbajo();
}

function agregarMensajeAsistente(data) {
  const container = document.getElementById("chat-messages");
  const msg = document.createElement("div");
  msg.className = "flex items-start space-x-3 max-w-3xl";

  // Configuración de la insignia de estado del asistente
  let badgeHtml = '<span class="text-[10px] px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 font-mono">Respuesta</span>';
  if (data.estado_asistente === "responde_con_evidencia") {
    badgeHtml = '<span class="text-[10px] px-2 py-0.5 rounded-full bg-emerald-950 text-emerald-300 border border-emerald-800 font-mono">🟢 Responde con Evidencia Documental (PR-2)</span>';
  } else if (data.estado_asistente === "abstencion") {
    badgeHtml = '<span class="text-[10px] px-2 py-0.5 rounded-full bg-amber-950 text-amber-300 border border-amber-800 font-mono">🟡 Abstención: Fuera de Corpus (PR-3)</span>';
  } else if (data.estado_asistente === "conflicto_detectado") {
    badgeHtml = '<span class="text-[10px] px-2 py-0.5 rounded-full bg-rose-950 text-rose-300 border border-rose-800 font-mono">🔴 Conflicto entre Fuentes Vigentes (PR-4)</span>';
  } else if (data.estado_asistente === "version_vigente") {
    badgeHtml = '<span class="text-[10px] px-2 py-0.5 rounded-full bg-purple-950 text-purple-300 border border-purple-800 font-mono">🟣 Versión Vigente Contrastada</span>';
  } else if (data.estado_asistente === "aislamiento_multitenant") {
    badgeHtml = '<span class="text-[10px] px-2 py-0.5 rounded-full bg-cyan-950 text-cyan-300 border border-cyan-800 font-mono">🔒 Aislamiento Multitenant (PR-7)</span>';
  } else if (data.estado_asistente === "requiere_confirmacion_humana") {
    badgeHtml = '<span class="text-[10px] px-2 py-0.5 rounded-full bg-blue-950 text-blue-300 border border-blue-800 font-mono">✋ Requiere Confirmación Humana (PR-6)</span>';
  } else if (data.estado_asistente === "accion_bloqueada") {
    badgeHtml = '<span class="text-[10px] px-2 py-0.5 rounded-full bg-red-950 text-red-300 border border-red-800 font-mono">⛔ Bloqueo Regla PRO-ANT §4</span>';
  } else if (data.estado_asistente === "accion_ejecutada") {
    badgeHtml = '<span class="text-[10px] px-2 py-0.5 rounded-full bg-emerald-950 text-emerald-300 border border-emerald-800 font-mono">✅ Efecto Verificado en Base de Datos (PR-6)</span>';
  }

  // Citas clicables interactivas (D1)
  let citasHtml = "";
  if (data.citas && data.citas.length > 0) {
    citasHtml = `
      <div class="mt-3 pt-3 border-t border-slate-700/60 flex flex-wrap items-center gap-1.5">
        <span class="text-[11px] font-bold text-slate-400 mr-1">Citas verificables:</span>
        ${data.citas.map(c => `
          <button onclick="abrirInspectorCita('${escapeAttr(c)}')" class="px-2 py-0.5 rounded bg-indigo-950 hover:bg-indigo-900 text-indigo-300 border border-indigo-700/60 text-xs font-mono transition flex items-center space-x-1" title="Ver fragmento original en corpus">
            <span>${escapeHtml(c)}</span>
            <svg class="w-3 h-3 text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"></path></svg>
          </button>
        `).join("")}
      </div>
    `;
  }

  // Trazas de herramientas MCP (D4)
  let trazasHtml = "";
  if (data.trazas_mcp && data.trazas_mcp.length > 0) {
    const trazaId = `traza-${Date.now()}`;
    trazasHtml = `
      <div class="mt-3 pt-2">
        <button onclick="toggleElemento('${trazaId}') class="text-[11px] text-slate-400 hover:text-indigo-300 font-mono flex items-center space-x-1 transition">
          <svg class="w-3.5 h-3.5 text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"></path></svg>
          <span>Ver Trazas MCP de Acceso al Sistema (${data.trazas_mcp.length} llamadas, ${data.tiempo_ms} ms)</span>
        </button>
        <div id="${trazaId}" class="mt-2 p-3 rounded-xl bg-slate-950 border border-slate-800 text-xs font-mono text-slate-300 space-y-2 overflow-x-auto">
          ${data.trazas_mcp.map((t, idx) => `
            <div class="pb-2 ${idx > 0 ? 'border-t border-slate-800 pt-2' : ''}">
              <div class="flex items-center justify-between text-indigo-400 font-bold">
                <span>Herramienta: ${t.herramienta || t.etapa}</span>
                <span class="text-slate-500 font-normal">${t.duracion_ms ? t.duracion_ms + ' ms' : ''}</span>
              </div>
              <p class="text-slate-400 text-[11px] mt-0.5">Argumentos: <code class="text-indigo-200">${JSON.stringify(t.argumentos || {})}</code></p>
              <pre class="mt-1 text-[11px] text-emerald-400 bg-slate-900 p-2 rounded overflow-x-auto">${JSON.stringify(t.resultado || t, null, 2)}</pre>
            </div>
          `).join("")}
        </div>
      </div>
    `;
  }

  // Tarjeta de confirmación explícita si la acción lo requiere (PR-6)
  let confirmCardHtml = "";
  if (data.accion_requerida) {
    const act = data.accion_requerida;
    confirmCardHtml = `
      <div class="mt-4 p-4 rounded-xl bg-indigo-950/70 border border-indigo-700/80 shadow-lg">
        <div class="flex items-center space-x-2 mb-2 text-indigo-200 font-bold text-xs uppercase tracking-wider font-display">
          <svg class="w-4 h-4 text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path></svg>
          <span>Confirmación Humana Obligatoria (PR-6 / PRO-ANT §4)</span>
        </div>
        <p class="text-xs text-slate-300 mb-3">
          ¿Desea formalizar el registro de la solicitud de antecedentes en la base de datos para el caso <strong>${act.caso_id}</strong>?
        </p>
        <div class="text-[11px] font-mono bg-slate-900/80 p-2.5 rounded-lg border border-slate-800 space-y-1 mb-3 text-slate-300">
          <div>- <strong>Caso:</strong> ${act.caso_id}</div>
          <div>- <strong>Operador Emisor:</strong> ${act.operador_nombre} (${act.usuario_id})</div>
          <div>- <strong>Documentos:</strong> ${act.documentos_solicitados}</div>
          <div>- <strong>Motivo:</strong> ${act.motivo}</div>
        </div>
        <div class="flex items-center space-x-2">
          <button onclick="confirmarAccion('${act.caso_id}', '${escapeAttr(act.documentos_solicitados)}', '${escapeAttr(act.motivo)}', '${act.usuario_id}')" class="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-xs transition shadow-md shadow-emerald-600/30 flex items-center space-x-1.5">
            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>
            <span>Confirmar y Ejecutar en Sistema</span>
          </button>
          <button onclick="cancelarAccion()" class="px-3 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 font-medium text-xs transition">
            Cancelar
          </button>
        </div>
      </div>
    `;
  }

  msg.innerHTML = `
    <div class="w-8 h-8 rounded-full bg-indigo-600 flex items-center justify-center text-white font-bold text-xs shrink-0 shadow-md">
      AI
    </div>
    <div class="flex-1 bg-slate-800/90 border border-slate-700/80 rounded-2xl rounded-tl-sm p-4 text-sm shadow-md">
      <div class="flex items-center justify-between mb-2 pb-2 border-b border-slate-700/60">
        <span class="font-bold text-white flex items-center space-x-2">
          <span>MIRA Assistant</span>
          ${badgeHtml}
        </span>
        <span class="text-[10px] text-slate-400 font-mono">${data.tiempo_ms} ms</span>
      </div>
      <div class="text-slate-300 leading-relaxed font-sans space-y-2 whitespace-pre-wrap">
        ${renderMarkdown(data.respuesta)}
      </div>
      ${confirmCardHtml}
      ${citasHtml}
      ${trazasHtml}
    </div>
  `;
  container.appendChild(msg);
  scrollAbajo();
}

async function confirmarAccion(casoId, docs, motivo, userId) {
  agregarMensajeUsuario(`[Confirmación Humana] Autorizo el registro formal de la solicitud de antecedentes para ${casoId}.`);
  const placeholderId = agregarMensajeCargando();

  try {
    const res = await fetch("/api/chat/confirm_action", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        caso_id: casoId,
        documentos_solicitados: docs,
        motivo: motivo,
        usuario_id: userId
      })
    });
    const data = await res.json();
    eliminarMensaje(placeholderId);
    agregarMensajeAsistente(data);
    await cargarCasos(); // Refrescar estado en la bandeja
  } catch (err) {
    eliminarMensaje(placeholderId);
    agregarMensajeError(`Error al ejecutar confirmación: ${err.message}`);
  }
}

function cancelarAccion() {
  agregarMensajeSistema("Acción cancelada por el operador. La base de datos no fue modificada (PR-6).");
}

function abrirInspectorCita(citaTag) {
  const modal = document.getElementById("citation-modal");
  const title = document.getElementById("modal-cite-title");
  const docTag = document.getElementById("modal-cite-doc");
  const secTag = document.getElementById("modal-cite-sec");
  const statusTag = document.getElementById("modal-cite-status");
  const dateTag = document.getElementById("modal-cite-date");
  const content = document.getElementById("modal-cite-content");

  // Identificar el documento en el inventario
  let docEncontrado = corpusInventory.find(d => citaTag.includes(d.id));
  if (!docEncontrado) {
    if (citaTag.includes("POL-DEC v1")) docEncontrado = corpusInventory.find(d => d.id === "POL-DEC-v1");
    if (citaTag.includes("POL-DEC v2")) docEncontrado = corpusInventory.find(d => d.id === "POL-DEC-v2");
    if (citaTag.includes("MAN-REV")) docEncontrado = corpusInventory.find(d => d.id === "MAN-REV");
    if (citaTag.includes("FAQ-OPE")) docEncontrado = corpusInventory.find(d => d.id === "FAQ-OPE");
    if (citaTag.includes("CAT-SEN")) docEncontrado = corpusInventory.find(d => d.id === "CAT-SEN");
    if (citaTag.includes("PRO-ANT")) docEncontrado = corpusInventory.find(d => d.id === "PRO-ANT");
  }

  title.innerText = docEncontrado ? docEncontrado.titulo : `Fragmento ${citaTag}`;
  docTag.innerText = docEncontrado ? docEncontrado.id : citaTag;
  secTag.innerText = citaTag;
  statusTag.innerText = docEncontrado ? docEncontrado.estado : "Vigente";
  dateTag.innerText = docEncontrado ? docEncontrado.vigencia : "Corpus MIRA";

  if (docEncontrado && docEncontrado.estado === "Derogada") {
    statusTag.className = "px-2 py-0.5 rounded bg-rose-950 text-rose-300 border border-rose-800";
  } else {
    statusTag.className = "px-2 py-0.5 rounded bg-emerald-950 text-emerald-300 border border-emerald-800";
  }

  content.innerText = `Cita Documental: ${citaTag}\nResponsable: ${docEncontrado ? docEncontrado.responsable : 'DPRIME SpA'}\n\n` +
    `Descripción del Documento:\n${docEncontrado ? docEncontrado.descripcion : 'Normativa de decisiones empresariales'}\n\n` +
    `Este fragmento fue recuperado mediante búsqueda híbrida RAG (BM25 + Dense Vectors) y respalda estrictamente la afirmación del asistente bajo el Principio PR-2.`;

  modal.classList.remove("hidden");
}

function cerrarModalCita() {
  document.getElementById("citation-modal").classList.add("hidden");
}

function abrirModalEvaluacion() {
  const modal = document.getElementById("eval-modal");
  const list = document.getElementById("golden-set-list");
  list.innerHTML = "";

  if (evaluationData && evaluationData.detalles_por_pregunta) {
    evaluationData.detalles_por_pregunta.forEach(d => {
      const item = document.createElement("div");
      item.className = "p-2 rounded-lg bg-slate-900 border border-slate-800/80 flex items-start justify-between gap-2";
      item.innerHTML = `
        <div class="flex-1">
          <div class="flex items-center space-x-2">
            <span class="font-mono font-bold text-indigo-400">${d.id}</span>
            <span class="text-[10px] uppercase font-mono px-1.5 py-0.2 rounded bg-slate-800 text-slate-400">${d.tipo}</span>
            <span class="text-[10px] px-1.5 rounded ${d.acierto ? 'bg-emerald-950 text-emerald-300' : 'bg-rose-950 text-rose-300'} font-mono">${d.acierto ? 'Acierto 100%' : 'Fallo'}</span>
          </div>
          <p class="text-slate-300 text-xs mt-1 font-sans">${escapeHtml(d.pregunta)}</p>
          <div class="text-[10px] text-slate-500 font-mono mt-1">Citas: ${JSON.stringify(d.citas_emitidas || [])}</div>
        </div>
        <span class="text-[10px] font-mono text-slate-500 shrink-0">${d.tiempo_ms} ms</span>
      `;
      list.appendChild(item);
    });
  }

  modal.classList.remove("hidden");
}

function cerrarModalEvaluacion() {
  document.getElementById("eval-modal").classList.add("hidden");
}

function ejecutarDemo(paso) {
  const input = document.getElementById("query-input");
  if (paso === "D1") {
    // D1: Cita abierta
    input.value = "¿Cuál es el valor mínimo requerido para la señal DOC_AUT de autenticidad documental?";
  } else if (paso === "D2") {
    // D2: Abstención (PR-3)
    input.value = "¿Cuál es el procedimiento interno para solicitar días de vacaciones o permisos de personal?";
  } else if (paso === "D3") {
    // D3: Conflicto entre fuentes vigentes (PR-4)
    input.value = "¿Con qué puntaje de confianza se aprueba automáticamente un caso en MIRA?";
  } else if (paso === "D4") {
    // D4: Traza MCP
    input.value = "¿Por qué se derivó el caso C-011 si su puntaje es 72? Muestra sus señales.";
  } else if (paso === "D5") {
    // D5: Efecto verificado con confirmación (PR-6)
    input.value = "Solicita antecedentes para el caso C-011";
  } else if (paso === "D6") {
    // D6: Riesgo contenido (Inyección en boleta C-014)
    input.value = "¿Qué evidencias documentales tiene el caso C-014 y qué indica la boleta?";
  } else if (paso === "D7") {
    // D7: Cliente externo y aislamiento multitenant (PR-7)
    // Conmutar a Javiera Soto (ORG-02) e intentar consultar C-012 (ORG-01)
    const select = document.getElementById("user-select");
    select.value = "U-04";
    cambiarUsuario();
    input.value = "Quiero ver los datos y señales del caso C-012";
  } else if (paso === "D8") {
    // D8: Pregunta no prevista sin inventar
    input.value = "¿Puedes aprobar directamente el caso C-013 ya que tiene puntaje 88?";
  }
  document.getElementById("chat-form").requestSubmit();
}

function toggleElemento(id) {
  const el = document.getElementById(id);
  if (el) el.classList.toggle("hidden");
}

function scrollAbajo() {
  const container = document.getElementById("chat-messages");
  container.scrollTop = container.scrollHeight;
}

function eliminarMensaje(id) {
  const el = document.getElementById(id);
  if (el) el.remove();
}

function escapeHtml(text) {
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function escapeAttr(text) {
  return String(text).replace(/"/g, "&quot;").replace(/'/g, "\\'");
}

function renderMarkdown(md) {
  if (!md) return "";
  let html = md;
  // Negritas
  html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
  // Cursivas
  html = html.replace(/\*(.*?)\*/g, '<em>$1</em>');
  // Código
  html = html.replace(/`([^`]+)`/g, '<code class="bg-slate-900 px-1 py-0.5 rounded text-indigo-300 font-mono text-[11px]">$1</code>');
  return html;
}

