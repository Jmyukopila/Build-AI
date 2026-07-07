/* BuildAI — lógica de la interfaz */

const chat = document.getElementById("chat");
const formulario = document.getElementById("formulario");
const entrada = document.getElementById("entrada");
const btnEnviar = document.getElementById("btn-enviar");

let ocupado = false;
let configuracion = null;

/* ---------- Iconos estáticos ---------- */

document.getElementById("btn-menu").innerHTML = svgIcono("menu");
document.getElementById("btn-ajustes").innerHTML = svgIcono("ajustes");
document.getElementById("btn-nueva").innerHTML = svgIcono("mas");
document.getElementById("btn-exportar").innerHTML = svgIcono("descargar");
document.getElementById("icono-panel-sesiones").innerHTML = svgIcono("historial");
document.getElementById("btn-enviar").innerHTML = svgIcono("enviar");
document.getElementById("btn-x-ajustes").innerHTML = svgIcono("cerrar");
document.getElementById("btn-x-ayuda").innerHTML = svgIcono("cerrar");
document.getElementById("icono-manual").innerHTML = svgIcono("manual");
document.getElementById("icono-panel-programas").innerHTML = svgIcono("herramienta");
document.getElementById("icono-panel-skills").innerHTML = svgIcono("chispa");
document.getElementById("icono-cabecera-ajustes").innerHTML = svgIcono("ajustes");
document.getElementById("icono-seccion-proveedor").innerHTML = svgIcono("nube");
document.getElementById("icono-seccion-acceso").innerHTML = svgIcono("llave");
document.getElementById("icono-seccion-modelo").innerHTML = svgIcono("sliders");
document.getElementById("icono-switch-apikey").innerHTML = svgIcono("llave");
document.getElementById("icono-switch-oauth").innerHTML = svgIcono("globo");
document.getElementById("icono-oauth-btn").innerHTML = svgIcono("globo");

/* ---------- Estado y programas ---------- */

let estadoAnterior = null;

async function cargarEstado() {
  const r = await fetch("/api/estado");
  if (!r.ok) return;
  const datos = await r.json();
  const cont = document.getElementById("programas");
  cont.innerHTML = "";
  for (const p of datos.programas) {
    const d = document.createElement("div");
    d.className = "programa" + (p.conectado ? " conectado" : "");
    d.innerHTML = `<span class="punto"></span><span class="icono">${svgIcono(p.icono)}</span><span class="nombre">${p.nombre}</span>`;
    if (!p.conectado) {
      const btn = document.createElement("button");
      btn.className = "icono-btn icono-btn-chico";
      btn.title = "Ayuda para conectar " + p.nombre;
      btn.innerHTML = svgIcono("ayuda");
      btn.onclick = () => abrirAyuda(p.id);
      d.appendChild(btn);
    } else {
      const est = document.createElement("span");
      est.className = "estado-txt";
      est.textContent = "conectado";
      d.appendChild(est);
    }
    cont.appendChild(d);
  }
  const info = document.getElementById("info-modelo");
  info.classList.toggle("sin-clave", !datos.clave_configurada);
  info.textContent = datos.clave_configurada
    ? `${datos.proveedor} · ${datos.modelo}`
    : "Configura la IA en Ajustes";
  estadoAnterior = datos;
}

/* ---------- Skills ---------- */

async function cargarSkills() {
  const r = await fetch("/api/skills");
  if (!r.ok) return;
  const lista = await r.json();
  const cont = document.getElementById("skills");
  for (const s of lista) {
    const btn = document.createElement("button");
    btn.className = "skill";
    btn.innerHTML = `<span class="icono">${svgIcono(s.icono)}</span><span>${s.nombre}<small>${s.descripcion || ""}</small></span>`;
    btn.onclick = () => enviar(s.prompt);
    cont.appendChild(btn);
  }
}

/* ---------- Modal de ayuda ---------- */

async function abrirAyuda(programaId) {
  const modal = document.getElementById("modal-ayuda");
  const prog = (estadoAnterior?.programas || []).find((p) => p.id === programaId);
  document.getElementById("ayuda-titulo").textContent = "Conectar " + (prog ? prog.nombre : programaId);
  document.getElementById("ayuda-texto").textContent = (prog && prog.ayuda) || "Sin instrucciones disponibles.";
  document.getElementById("ayuda-resultado").classList.add("oculto");
  const btnAuto = document.getElementById("btn-conectar-auto");
  btnAuto.textContent = "⚡ Conectar automáticamente";
  btnAuto.className = "";
  btnAuto.onclick = async () => {
    btnAuto.disabled = true;
    btnAuto.textContent = "Conectando…";
    const r = await (await fetch("/api/conectar/" + programaId, { method: "POST" })).json();
    const res = document.getElementById("ayuda-resultado");
    res.classList.remove("oculto");
    if (r.conectado) {
      res.textContent = "✅ " + programaId + " conectado correctamente.";
      cargarEstado();
    } else {
      res.textContent = "❌ No se pudo conectar. " + (r.error || "Revisa el manual.");
    }
    btnAuto.disabled = false;
    btnAuto.textContent = "⚡ Conectar automáticamente";
  };
  modal.classList.remove("oculto");
}

document.getElementById("btn-cerrar-ayuda").addEventListener("click", () => {
  document.getElementById("modal-ayuda").classList.add("oculto");
});
document.getElementById("btn-x-ayuda").addEventListener("click", () => {
  document.getElementById("modal-ayuda").classList.add("oculto");
});

/* ---------- Menú lateral responsive ---------- */

const lateral = document.getElementById("lateral");
const fondo = document.getElementById("fondo-lateral");
document.getElementById("btn-menu").addEventListener("click", () => {
  lateral.classList.toggle("oculto");
  fondo.classList.toggle("oculto");
});
fondo.addEventListener("click", () => {
  lateral.classList.add("oculto");
  fondo.classList.add("oculto");
});

/* ---------- Pestañas del panel lateral (Programas / Tareas / Historial) ---------- */

const tabsLateral = document.querySelector(".tabs-lateral");
function activarTabLateral(tab) {
  tabsLateral.dataset.tabActivo = tab;
  tabsLateral.querySelectorAll(".tab-lateral").forEach((b) => {
    b.classList.toggle("activo", b.dataset.tab === tab);
  });
  document.querySelectorAll(".panel-tab-cuerpo").forEach((p) => {
    p.classList.toggle("oculto", p.dataset.panel !== tab);
  });
}
tabsLateral.addEventListener("click", (e) => {
  const btn = e.target.closest(".tab-lateral");
  if (!btn || btn.classList.contains("activo")) return;
  activarTabLateral(btn.dataset.tab);
});

/* ---------- Formato de texto ---------- */

function escapeHtml(texto) {
  return String(texto)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

/* Mini-Markdown para las respuestas del asistente (negrita, listas, código,
   títulos, enlaces). Escapa siempre el HTML antes de dar formato. */
function md(texto) {
  let t = escapeHtml(texto);
  const bloques = [];
  t = t.replace(/```\w*\n?([\s\S]*?)```/g, (_, cod) => {
    bloques.push(`<pre><code>${cod.replace(/\n$/, "")}</code></pre>`);
    return `\u0000${bloques.length - 1}\u0000`;
  });
  t = t.replace(/`([^`\n]+)`/g, "<code>$1</code>");
  t = t.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  t = t.replace(/(^|[\s(])\*([^*\n]+)\*(?=[\s).,;:!?]|$)/gm, "$1<em>$2</em>");
  t = t.replace(/\[([^\]]+)\]\((https?:[^)\s]+)\)/g,
    '<a href="$2" target="_blank" rel="noopener">$1</a>');

  let html = "";
  let lista = null;
  let parrafo = [];
  const cierraParrafo = () => {
    if (parrafo.length) { html += `<p>${parrafo.join("<br>")}</p>`; parrafo = []; }
  };
  const cierraLista = () => {
    if (lista) { html += `</${lista}>`; lista = null; }
  };
  for (const linea of t.split("\n")) {
    const bloque = linea.match(/^\u0000(\d+)\u0000\s*$/);
    const h = linea.match(/^(#{1,3})\s+(.*)/);
    const ul = linea.match(/^\s*[-*•]\s+(.*)/);
    const ol = linea.match(/^\s*\d+[.)]\s+(.*)/);
    if (bloque) { cierraParrafo(); cierraLista(); html += bloques[+bloque[1]]; }
    else if (h) { cierraParrafo(); cierraLista(); const n = h[1].length; html += `<h${n}>${h[2]}</h${n}>`; }
    else if (ul) { cierraParrafo(); if (lista !== "ul") { cierraLista(); html += "<ul>"; lista = "ul"; } html += `<li>${ul[1]}</li>`; }
    else if (ol) { cierraParrafo(); if (lista !== "ol") { cierraLista(); html += "<ol>"; lista = "ol"; } html += `<li>${ol[1]}</li>`; }
    else if (!linea.trim()) { cierraParrafo(); cierraLista(); }
    else { cierraLista(); parrafo.push(linea); }
  }
  cierraParrafo();
  cierraLista();
  // Bloques de código que quedaron dentro de un párrafo
  return html.replace(/\u0000(\d+)\u0000/g, (_, i) => bloques[+i]);
}

/* ---------- Chat ---------- */

let transcripcion = []; // conversación visible, para exportarla a Markdown

function agregarMensaje(tipo, contenido) {
  const d = document.createElement("div");
  d.className = "mensaje " + tipo;
  if (tipo === "usuario") {
    d.innerHTML = `<div class="burbuja"></div>`;
    d.querySelector(".burbuja").textContent = contenido;
    transcripcion.push({ rol: "Tú", texto: contenido });
  } else if (tipo === "asistente") {
    d.innerHTML = `<div class="burbuja md">${md(contenido)}<button class="btn-copiar" title="Copiar respuesta"></button></div>`;
    const btn = d.querySelector(".btn-copiar");
    btn.innerHTML = svgIcono("copiar");
    btn.onclick = async () => {
      try { await navigator.clipboard.writeText(contenido); } catch (_) { return; }
      btn.innerHTML = svgIcono("check");
      setTimeout(() => { btn.innerHTML = svgIcono("copiar"); }, 1200);
    };
    transcripcion.push({ rol: "BuildAI", texto: contenido });
  } else {
    d.innerHTML = `<div class="burbuja">${contenido}</div>`;
  }
  const escribiendo = chat.querySelector(".escribiendo");
  if (escribiendo) escribiendo.before(d);
  else chat.appendChild(d);
  chat.scrollTop = chat.scrollHeight;
}

function agregarMensajeUsuario(texto) {
  agregarMensaje("usuario", texto);
}

function agregarActividadHerramienta(ev) {
  const detalle = ev.detalle ? `<pre>${escapeHtml(ev.detalle)}</pre>` : "";
  agregarMensaje("actividad",
    `<details><summary>${svgIcono((ev.programa || "").toLowerCase())} ${escapeHtml(ev.nombre)}</summary>${detalle}</details>`);
  transcripcion.push({ rol: "herramienta", nombre: `${ev.programa} · ${ev.nombre}`, detalle: ev.detalle || "" });
}

function lineaConIcono(icono, texto) {
  return `<span class="linea-icono">${svgIcono(icono)} ${texto}</span>`;
}

/* Indicador de trabajo estilo Claude: chispa animada + estado en vivo + tiempo */

let inicioTrabajo = 0;
let timerEstado = null;

function textoTiempo() {
  const s = Math.round((Date.now() - inicioTrabajo) / 1000);
  return s >= 3 ? `${s} s` : "";
}

function actualizarTiempoEstado() {
  const t = chat.querySelector(".escribiendo .tiempo-estado");
  if (t) t.textContent = textoTiempo();
}

function mostrarEscribiendo(texto) {
  let e = chat.querySelector(".escribiendo");
  if (!e) {
    e = document.createElement("div");
    e.className = "mensaje asistente escribiendo";
    e.innerHTML = `<div class="burbuja"><span class="chispa">${svgIcono("chispa")}</span><span class="estado-texto"></span><span class="tiempo-estado"></span></div>`;
    chat.appendChild(e);
  }
  e.querySelector(".estado-texto").textContent = texto || "Pensando…";
  e.querySelector(".tiempo-estado").textContent = textoTiempo();
  chat.scrollTop = chat.scrollHeight;
}

function ocultarEscribiendo() {
  const e = chat.querySelector(".escribiendo");
  if (e) e.remove();
}

/* ---------- Enviar mensaje ---------- */

formulario.addEventListener("submit", (e) => {
  e.preventDefault();
  if (ocupado) {
    detenerTarea();
    return;
  }
  const texto = entrada.value.trim();
  if (!texto) return;
  entrada.value = "";
  ajustarAltura();
  enviar(texto);
});

// Enter envía; Mayús+Enter hace salto de línea
entrada.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
    e.preventDefault();
    if (!ocupado) formulario.requestSubmit();
  }
});

async function detenerTarea() {
  mostrarEscribiendo("Deteniendo… (termino el paso en curso para no dejar nada a medias)");
  try {
    await fetch("/api/cancelar", { method: "POST" });
  } catch (_) { /* si falla, el flujo termina igualmente */ }
}

function ajustarAltura() {
  entrada.style.height = "auto";
  entrada.style.height = Math.min(entrada.scrollHeight, 160) + "px";
}
entrada.addEventListener("input", ajustarAltura);

async function enviar(texto) {
  if (ocupado) return;
  agregarMensajeUsuario(texto);

  if (!estadoAnterior || !estadoAnterior.clave_configurada) {
    agregarMensaje("error", lineaConIcono("advertencia",
      "Antes de hablar conmigo, abre Ajustes (icono de engranaje arriba) y elige un proveedor de IA con su clave."));
    return;
  }

  ocupado = true;
  btnEnviar.classList.add("detener");
  btnEnviar.innerHTML = svgIcono("detener");
  btnEnviar.title = "Detener la tarea";
  inicioTrabajo = Date.now();
  timerEstado = setInterval(actualizarTiempoEstado, 1000);
  mostrarEscribiendo();

  try {
    const r = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mensaje: texto }),
    });
    const reader = r.body.getReader();
    const dec = new TextDecoder();
    let buffer = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += dec.decode(value, { stream: true });
      const partes = buffer.split("\n\n");
      buffer = partes.pop() || "";
      for (const p of partes) {
        if (!p.startsWith("data: ")) continue;
        const ev = JSON.parse(p.slice(6));
        if (ev.tipo === "respuesta") {
          ocultarEscribiendo();
          agregarMensaje("asistente", ev.texto);
        } else if (ev.tipo === "error") {
          ocultarEscribiendo();
          agregarMensaje("error", lineaConIcono("advertencia", ev.texto));
        } else if (ev.tipo === "herramienta") {
          // Se inserta encima del indicador, que sigue mostrando actividad
          agregarActividadHerramienta(ev);
        } else if (ev.tipo === "estado") {
          mostrarEscribiendo(ev.texto);
        }
      }
    }
  } catch (err) {
    ocultarEscribiendo();
    agregarMensaje("error", lineaConIcono("advertencia", "Error de conexión: " + err.message));
  }

  ocupado = false;
  ocultarEscribiendo();
  clearInterval(timerEstado);
  timerEstado = null;
  btnEnviar.classList.remove("detener");
  btnEnviar.innerHTML = svgIcono("enviar");
  btnEnviar.title = "Enviar (Enter)";
  entrada.focus();
  cargarSesiones(); // el título y la fecha de la sesión acaban de cambiar
}

/* ---------- Historial de sesiones ---------- */

function fechaCorta(ts) {
  const f = new Date(ts * 1000);
  const hoy = new Date();
  const ayer = new Date(hoy);
  ayer.setDate(hoy.getDate() - 1);
  const hora = f.toLocaleTimeString("es", { hour: "2-digit", minute: "2-digit" });
  if (f.toDateString() === hoy.toDateString()) return "hoy " + hora;
  if (f.toDateString() === ayer.toDateString()) return "ayer " + hora;
  return f.toLocaleDateString("es", { day: "numeric", month: "short" }) + " " + hora;
}

async function cargarSesiones() {
  let datos;
  try {
    datos = await (await fetch("/api/sesiones")).json();
  } catch (_) {
    return;
  }
  const cont = document.getElementById("sesiones");
  cont.innerHTML = "";
  if (!datos.sesiones.length) {
    cont.innerHTML = `<p class="pista sin-sesiones">Aún no hay conversaciones guardadas.</p>`;
    return;
  }
  for (const s of datos.sesiones) {
    const d = document.createElement("div");
    d.className = "sesion" + (s.id === datos.actual ? " activa" : "");
    const info = document.createElement("button");
    info.type = "button";
    info.className = "sesion-info";
    info.title = "Abrir esta conversación";
    info.innerHTML = `<span class="sesion-titulo"></span><small></small>`;
    info.querySelector(".sesion-titulo").textContent = s.titulo;
    info.querySelector("small").textContent =
      `${fechaCorta(s.actualizada)} · ${s.mensajes} mensaje${s.mensajes === 1 ? "" : "s"}`;
    info.onclick = () => abrirSesion(s.id);
    const borrar = document.createElement("button");
    borrar.type = "button";
    borrar.className = "icono-btn icono-btn-chico sesion-borrar";
    borrar.title = "Borrar esta conversación";
    borrar.innerHTML = svgIcono("papelera");
    borrar.onclick = async () => {
      if (!confirm(`¿Borrar la conversación «${s.titulo}» definitivamente?`)) return;
      const r = await (await fetch("/api/sesiones/" + s.id, { method: "DELETE" })).json();
      if (!r.ok) {
        agregarMensaje("error", lineaConIcono("advertencia", r.error));
        return;
      }
      if (s.id === datos.actual) limpiarConversacion();
      cargarSesiones();
    };
    d.appendChild(info);
    d.appendChild(borrar);
    cont.appendChild(d);
  }
}

async function abrirSesion(id) {
  if (ocupado) return;
  const r = await (await fetch(`/api/sesiones/${id}/abrir`, { method: "POST" })).json();
  if (!r.ok) {
    agregarMensaje("error", lineaConIcono("advertencia", r.error));
    return;
  }
  pintarConversacion(r.mensajes);
  cargarSesiones();
  // En pantallas pequeñas el panel tapa el chat: cerrarlo al elegir sesión
  if (window.matchMedia("(max-width: 860px)").matches) {
    lateral.classList.add("oculto");
    fondo.classList.add("oculto");
  }
  entrada.focus();
}

function limpiarConversacion() {
  chat.querySelectorAll(".mensaje:not(.bienvenida)").forEach((m) => m.remove());
  document.querySelector(".bienvenida").classList.remove("oculto");
  transcripcion = [];
}

function pintarConversacion(mensajes) {
  limpiarConversacion();
  document.querySelector(".bienvenida").classList.toggle("oculto", mensajes.length > 0);
  for (const ev of mensajes) {
    if (ev.tipo === "usuario") agregarMensaje("usuario", ev.texto);
    else if (ev.tipo === "respuesta") agregarMensaje("asistente", ev.texto);
    else if (ev.tipo === "herramienta") agregarActividadHerramienta(ev);
  }
  chat.scrollTop = chat.scrollHeight;
}

/* ---------- Exportar conversación ---------- */

document.getElementById("btn-exportar").addEventListener("click", () => {
  if (!transcripcion.length) {
    agregarMensaje("error", lineaConIcono("advertencia",
      "Todavía no hay nada que exportar: escribe algo primero."));
    return;
  }
  const fecha = new Date();
  let texto = `# Conversación BuildAI — ${fecha.toLocaleString("es")}\n`;
  for (const t of transcripcion) {
    if (t.rol === "herramienta") {
      texto += `\n> 🔧 ${t.nombre}\n`;
      if (t.detalle) texto += `\n\`\`\`\n${t.detalle}\n\`\`\`\n`;
    } else {
      texto += `\n**${t.rol}:**\n\n${t.texto}\n`;
    }
  }
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([texto], { type: "text/markdown" }));
  a.download = `BuildAI-${fecha.toISOString().slice(0, 16).replace(/[T:]/g, "-")}.md`;
  a.click();
  URL.revokeObjectURL(a.href);
});

/* ---------- Ajustes ---------- */

const modalAjustes = document.getElementById("modal-ajustes");
const selProveedor = document.getElementById("sel-proveedor");
const inpClave = document.getElementById("inp-clave");
const inpModelo = document.getElementById("inp-modelo");

async function abrirAjustes() {
  configuracion = await (await fetch("/api/config")).json();
  selProveedor.innerHTML = "";
  for (const [id, info] of Object.entries(configuracion.proveedores)) {
    const op = document.createElement("option");
    op.value = id;
    op.textContent = info.nombre;
    if (id === configuracion.proveedor) op.selected = true;
    selProveedor.appendChild(op);
  }
  refrescarCamposProveedor();
  modalAjustes.classList.remove("oculto");
}

let peticionModelos = 0; // evita que una respuesta lenta pise al proveedor recién elegido

async function cargarModelosProveedor(id) {
  const listaDatos = document.getElementById("lista-modelos");
  const estadoModelos = document.getElementById("estado-modelos");
  listaDatos.innerHTML = "";
  estadoModelos.textContent = id === "ollama" ? "Buscando tus modelos locales…" : "Cargando modelos…";
  const peticion = ++peticionModelos;
  let datos;
  try {
    datos = await (await fetch("/api/modelos/" + id)).json();
  } catch (e) {
    datos = { disponible: false, modelos: [], nota: "No se pudo cargar la lista de modelos." };
  }
  if (peticion !== peticionModelos || selProveedor.value !== id) return;
  for (const m of datos.modelos) {
    const opcion = document.createElement("option");
    opcion.value = m.id;
    opcion.label = m.nombre;
    listaDatos.appendChild(opcion);
  }
  estadoModelos.textContent = (datos.disponible ? "" : "⚠️ ") + (datos.nota || "");
  // Si el modelo configurado no existe en Ollama, proponer el primero detectado
  if (id === "ollama" && datos.modelos.length &&
      !datos.modelos.some((m) => m.id === inpModelo.value)) {
    inpModelo.value = datos.modelos[0].id;
  }
}

function refrescarCamposProveedor() {
  const id = selProveedor.value;
  const info = configuracion.proveedores[id];
  const nota = document.getElementById("nota-proveedor");
  nota.innerHTML = `${info.nota} <a href="${info.url_clave}" target="_blank" rel="noopener">${info.url_texto || "Obtener clave ↗"}</a>`;
  inpClave.value = "";
  const necesitaClave = info.requiere_clave !== false;
  document.getElementById("campo-clave").classList.toggle("oculto", !necesitaClave);
  document.getElementById("estado-clave").textContent = !necesitaClave
    ? "Este proveedor no necesita clave: funciona en tu propio ordenador."
    : configuracion.claves_configuradas[id]
      ? "Ya hay una clave guardada para este proveedor. Déjalo vacío para no cambiarla."
      : "Aún no hay clave guardada para este proveedor.";

  // Alternar entre Clave API y OAuth (según si el proveedor ofrece OAuth)
  const toggle = document.getElementById("toggle-auth");
  const txtOauthProv = document.getElementById("oauth-proveedor");
  if (info.oauth_disponible) {
    toggle.classList.remove("oculto");
    txtOauthProv.textContent = info.nombre;
  } else {
    toggle.classList.add("oculto");
  }
  establecerModoAcceso("apikey");

  inpModelo.value = configuracion.modelos[id] || configuracion.modelos_por_defecto[id];
  cargarModelosProveedor(id);
}
selProveedor.addEventListener("change", refrescarCamposProveedor);

document.getElementById("btn-ajustes").addEventListener("click", abrirAjustes);
function cerrarAjustes() {
  modalAjustes.classList.add("oculto");
}
document.getElementById("btn-cerrar-ajustes").addEventListener("click", cerrarAjustes);
document.getElementById("btn-x-ajustes").addEventListener("click", cerrarAjustes);
const btnGuardarAjustes = document.getElementById("btn-guardar-ajustes");
btnGuardarAjustes.addEventListener("click", async () => {
  const id = selProveedor.value;
  btnGuardarAjustes.disabled = true;
  btnGuardarAjustes.textContent = "Guardando…";
  try {
    await fetch("/api/config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        proveedor: id,
        claves: { [id]: inpClave.value },
        modelos: { [id]: inpModelo.value },
      }),
    });
    cerrarAjustes();
    cargarEstado();
  } finally {
    btnGuardarAjustes.disabled = false;
    btnGuardarAjustes.textContent = "Guardar cambios";
  }
});

// Deslizador entre Clave API y OAuth: solo el panel del modo elegido queda visible
function establecerModoAcceso(modo) {
  const toggle = document.getElementById("toggle-auth");
  const modoApikey = document.getElementById("modo-apikey");
  const modoOauth = document.getElementById("modo-oauth");
  toggle.dataset.modoActivo = modo;
  toggle.querySelectorAll(".switch-opcion").forEach((b) => {
    b.classList.toggle("activo", b.dataset.modo === modo);
  });
  const mostrar = modo === "apikey" ? modoApikey : modoOauth;
  const ocultar = modo === "apikey" ? modoOauth : modoApikey;
  ocultar.classList.add("oculto");
  mostrar.classList.remove("oculto");
  mostrar.classList.remove("entrada-suave");
  void mostrar.offsetWidth; // fuerza reflow para reiniciar la animación de entrada
  mostrar.classList.add("entrada-suave");
}

document.getElementById("toggle-auth").addEventListener("click", (e) => {
  const btn = e.target.closest(".switch-opcion");
  if (!btn || btn.classList.contains("activo")) return;
  establecerModoAcceso(btn.dataset.modo);
});

// Login OAuth
document.getElementById("btn-login-oauth").addEventListener("click", () => {
  const prov = selProveedor.value;
  window.open(`/api/oauth/login?proveedor=${prov}`, "oauth", "width=600,height=700,menubar=no,status=no");
  const iv = setInterval(async () => {
    const cfg = await (await fetch("/api/config")).json();
    if (cfg.claves_configuradas[prov]) {
      clearInterval(iv);
      refrescarCamposProveedor();
    }
  }, 800);
  setTimeout(() => clearInterval(iv), 30000);
});

/* ---------- Nueva conversación ---------- */

document.getElementById("btn-nueva").addEventListener("click", async () => {
  const r = await (await fetch("/api/reiniciar", { method: "POST" })).json();
  if (!r.ok) {
    agregarMensaje("error", lineaConIcono("advertencia", r.error));
    return;
  }
  limpiarConversacion();
  cargarSesiones();
  entrada.focus();
});

/* ---------- Comodidad: cerrar modales y foco ---------- */

// Clic fuera de la caja cierra el modal
for (const id of ["modal-ajustes", "modal-ayuda"]) {
  const modal = document.getElementById(id);
  modal.addEventListener("click", (e) => {
    if (e.target === modal) modal.classList.add("oculto");
  });
}

// Escape cierra cualquier modal abierto
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    document.querySelectorAll(".modal:not(.oculto)").forEach((m) => m.classList.add("oculto"));
  }
});

// El pie con el modelo activo abre Ajustes directamente
document.getElementById("info-modelo").addEventListener("click", abrirAjustes);

/* ---------- Arranque ---------- */

cargarEstado();
cargarSkills();
cargarSesiones();
setInterval(cargarEstado, 10000);
entrada.focus();
