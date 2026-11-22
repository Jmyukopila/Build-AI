/* BuildAI — lógica de la interfaz */

const chat = document.getElementById("chat");
const formulario = document.getElementById("formulario");
const entrada = document.getElementById("entrada");
const btnEnviar = document.getElementById("btn-enviar");

let ocupado = false;
let configuracion = null;

/* ---------- Iconos estáticos ---------- */

document.getElementById("icono-logo").innerHTML = '<img src="/ui/assets/icono-marca.png" alt="" width="40" height="40">';
document.getElementById("btn-menu").innerHTML = svgIcono("menu");
document.getElementById("btn-ajustes").innerHTML = svgIcono("ajustes");
document.getElementById("btn-nueva").innerHTML = svgIcono("mas");
document.getElementById("btn-exportar").innerHTML = svgIcono("descargar");
document.getElementById("icono-panel-sesiones").innerHTML = svgIcono("historial");
document.getElementById("btn-enviar").innerHTML = svgIcono("enviar");
document.getElementById("btn-x-ajustes").innerHTML = svgIcono("cerrar");
document.getElementById("btn-x-ayuda").innerHTML = svgIcono("cerrar");
document.getElementById("icono-manual").innerHTML = svgIcono("libro");
document.getElementById("icono-panel-programas").innerHTML = svgIcono("herramienta");
document.getElementById("icono-panel-skills").innerHTML = svgIcono("chispa");
document.getElementById("icono-cabecera-ajustes").innerHTML = svgIcono("ajustes");
document.getElementById("icono-seccion-proveedor").innerHTML = svgIcono("nube");
document.getElementById("icono-seccion-acceso").innerHTML = svgIcono("llave");
document.getElementById("icono-seccion-modelo").innerHTML = svgIcono("sliders");
document.getElementById("icono-switch-apikey").innerHTML = svgIcono("llave");
document.getElementById("icono-switch-oauth").innerHTML = svgIcono("globo");
document.getElementById("icono-oauth-btn").innerHTML = svgIcono("globo");
document.getElementById("btn-adjuntar").innerHTML = svgIcono("clip");
document.getElementById("btn-rail").innerHTML = svgIcono("panel");
document.getElementById("btn-x-rail").innerHTML = svgIcono("cerrar");
document.getElementById("icono-rail-actividad").innerHTML = svgIcono("actividad");
document.getElementById("btn-abajo").innerHTML = svgIcono("chevron");
document.getElementById("banner-icono").innerHTML = svgIcono("advertencia");
// Iconos declarados en el HTML con data-icono="nombre"
document.querySelectorAll("[data-icono]").forEach((el) => { el.innerHTML = svgIcono(el.dataset.icono); });

/* ---------- Movimiento e interactividad ---------- */

const reducirMovimiento = window.matchMedia("(prefers-reduced-motion: reduce)");

// Hace entrar una lista escalonada. El retraso por elemento baja cuanto más
// larga es la lista (tope total ~400 ms) para que no se vuelva lenta al crecer.
function escalonar(elementos) {
  const lista = Array.from(elementos);
  const paso = Math.min(50, 400 / Math.max(lista.length, 1));
  lista.forEach((el, i) => {
    el.classList.add("entra");
    el.style.animationDelay = `${Math.round(i * paso)}ms`;
  });
}

// Aviso efímero (arriba, centrado). No bloquea ni roba el foco. Tipos: ok,
// error, info y atencion; los errores se quedan más tiempo para poder leerlos.
const ICONO_AVISO = { ok: "check", error: "advertencia", info: "info", atencion: "advertencia" };
function avisar(texto, tipo = "ok") {
  let cont = document.querySelector(".avisos");
  if (!cont) {
    cont = document.createElement("div");
    cont.className = "avisos";
    cont.setAttribute("role", "status");
    cont.setAttribute("aria-live", "polite");
    document.body.appendChild(cont);
  }
  const a = document.createElement("div");
  a.className = "aviso" + (tipo === "ok" ? "" : " " + tipo);
  a.innerHTML = `<span class="icono">${svgIcono(ICONO_AVISO[tipo] || "check")}</span><span></span>`;
  a.lastElementChild.textContent = texto;
  cont.appendChild(a);
  while (cont.children.length > 3) cont.firstElementChild.remove();
  setTimeout(() => {
    a.classList.add("sale");
    a.addEventListener("animationend", () => a.remove(), { once: true });
  }, tipo === "error" ? 5200 : 2800);
}

// Aviso fijo bajo la barra: persiste mientras la causa siga ahí (sin IA
// configurada, sin conexión con el servidor). `accion` es {texto, hacer}.
const banner = document.getElementById("banner");
const bannerAccion = document.getElementById("banner-accion");
function mostrarBanner(texto, { tipo = "atencion", accion = null } = {}) {
  banner.className = "banner" + (tipo === "atencion" ? "" : " " + tipo);
  document.getElementById("banner-icono").innerHTML = svgIcono(tipo === "info" ? "info" : "advertencia");
  document.getElementById("banner-texto").textContent = texto;
  bannerAccion.classList.toggle("oculto", !accion);
  bannerAccion.textContent = accion ? accion.texto : "";
  bannerAccion.onclick = accion ? accion.hacer : null;
}
function ocultarBanner() { banner.classList.add("oculto"); }

// Texto con anillo de carga para botones que esperan al servidor
const conSpinner = (texto) => `<span class="spinner"></span>${texto}`;

// Espera a que termine la animación de un elemento; el plazo evita colgarse si
// no llega a dispararse (p. ej. pestaña en segundo plano).
function esperarAnimacion(el, plazo = 400) {
  return new Promise((resolver) => {
    const fin = () => { clearTimeout(reloj); resolver(); };
    const reloj = setTimeout(fin, plazo);
    el.addEventListener("animationend", fin, { once: true });
  });
}

// Con la ventana en segundo plano se pausan los bucles ambientales
document.addEventListener("visibilitychange", () => {
  document.documentElement.classList.toggle("pausa-ambiente", document.hidden);
});

// Scroll del chat: sigue lo nuevo solo si el usuario ya estaba abajo, y ofrece
// un botón para volver al final cuando ha subido a releer.
const btnAbajo = document.getElementById("btn-abajo");
let pintandoHistorial = false; // true mientras se repinta una sesión guardada

function distanciaAlFinal() {
  return chat.scrollHeight - chat.scrollTop - chat.clientHeight;
}
function actualizarBtnAbajo() {
  btnAbajo.classList.toggle("visible", distanciaAlFinal() > 240);
}
function bajarChat({ suave = true } = {}) {
  chat.scrollTo({ top: chat.scrollHeight, behavior: suave && !reducirMovimiento.matches ? "smooth" : "auto" });
}
chat.addEventListener("scroll", actualizarBtnAbajo, { passive: true });
btnAbajo.addEventListener("click", () => bajarChat());
// El botón flota justo encima del formulario, cuya altura cambia (adjuntos, texto largo)
new ResizeObserver(() => {
  document.getElementById("principal").style.setProperty("--alto-form", `${formulario.offsetHeight}px`);
}).observe(formulario);

// Lo que llega en vivo se despliega como la respuesta; el historial guardado no
function revelarEnVivo(el) {
  if (pintandoHistorial) return;
  el.classList.add("despliega");
  el.addEventListener("animationend", (e) => {
    if (e.animationName === "despliega") el.classList.remove("despliega");
  });
}

// Único punto por el que entra un mensaje al chat (antes estaba triplicado)
function insertarMensaje(d, { forzar = false } = {}) {
  const estabaAbajo = distanciaAlFinal() < 120;
  if (pintandoHistorial) d.classList.add("sin-anim");
  document.querySelector(".bienvenida")?.classList.add("oculto");
  chat.appendChild(d);
  if (forzar || estabaAbajo) bajarChat({ suave: !pintandoHistorial });
  actualizarBtnAbajo();
}

// Encargos de ejemplo de la bienvenida: rellenan la caja para que el usuario
// pueda ajustarlos antes de enviar
document.querySelectorAll(".chip").forEach((c) => {
  c.addEventListener("click", () => {
    entrada.value = c.dataset.ejemplo || c.textContent.trim();
    ajustarAltura();
    entrada.focus();
    // Destello breve: confirma que el texto llegó a la caja
    entrada.classList.remove("destello");
    void entrada.offsetWidth; // reinicia la animación si se pulsa dos veces seguidas
    entrada.classList.add("destello");
  });
});
entrada.addEventListener("animationend", () => entrada.classList.remove("destello"));

/* ---------- Estado y programas ---------- */

let estadoAnterior = null;
let firmaEstado = "";

async function cargarEstado() {
  let datos;
  try {
    const r = await fetch("/api/estado");
    if (!r.ok) throw new Error("estado " + r.status);
    datos = await r.json();
  } catch (_) {
    mostrarBanner("Sin conexión con BuildAI. Reintentando…", { tipo: "error" });
    firmaEstado = ""; // al volver, se repinta todo
    return;
  }
  const previo = estadoAnterior;
  estadoAnterior = datos;
  // El sondeo corre cada 10 s: si nada cambió no se reescribe el DOM (evita
  // parpadeos, reinicios de animación y perder el hover sobre un programa).
  const firma = JSON.stringify(datos);
  if (firma === firmaEstado) return;
  const primera = firmaEstado === "";
  firmaEstado = firma;
  const cont = document.getElementById("programas");
  cont.innerHTML = "";
  cont.removeAttribute("aria-busy");
  for (const p of datos.programas) {
    const d = document.createElement("div");
    d.className = "programa" + (p.conectado ? " conectado" : "");
    d.innerHTML = `<span class="punto"></span><span class="icono">${svgIcono(p.icono)}</span><span class="nombre">${p.nombre}</span>`;
    if (!p.conectado) {
      const sin = document.createElement("span");
      sin.className = "estado-txt";
      sin.textContent = "sin conectar";
      d.appendChild(sin);
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
  if (primera) escalonar(cont.children);
  // Un programa que pasa a conectado merece confirmación visible
  for (const p of datos.programas) {
    const antes = previo?.programas.find((x) => x.id === p.id);
    if (p.conectado && antes && !antes.conectado) avisar(`${p.nombre} conectado`);
  }
  // La IA incluida se descarga (solo la primera vez) y arranca sola: mientras
  // tanto se enseña el progreso y se sondea más a menudo para que avance fluido.
  const ia = datos.ia_local;
  if (ia && (ia.fase === "descargando" || ia.fase === "arrancando")) {
    const pct = ia.fase === "descargando" ? ` ${Math.round(ia.progreso * 100)} %` : "";
    mostrarBanner(`${ia.mensaje}${pct}`, { tipo: "info" });
    clearTimeout(cargarEstado.siguiente);
    cargarEstado.siguiente = setTimeout(cargarEstado, 2000);
  } else if (ia && ia.fase === "error") {
    mostrarBanner(`La IA incluida no pudo prepararse: ${ia.mensaje}`,
      { tipo: "error", accion: { texto: "Elegir otra IA", hacer: () => abrirAjustes() } });
  } else if (datos.clave_configurada) ocultarBanner();
  else mostrarBanner("Aún no has elegido una IA: configúrala para empezar a conversar.",
    { accion: { texto: "Abrir ajustes", hacer: () => abrirAjustes() } });
  if (ia && previo?.ia_local && previo.ia_local.fase !== "lista" && ia.fase === "lista") avisar(ia.mensaje);
  const nombreProveedor = datos.proveedor === "local" ? "IA incluida" : datos.proveedor;
  const info = document.getElementById("info-modelo");
  info.classList.toggle("sin-clave", !datos.clave_configurada);
  info.textContent = datos.clave_configurada
    ? `${nombreProveedor} · ${datos.modelo}`
    : "Configura la IA en Ajustes";

  const conectados = datos.programas.filter((p) => p.conectado).length;
  document.getElementById("lectura-estado").innerHTML =
    `<span class="punto ${conectados > 0 ? "conectado" : ""}"></span>${conectados}/${datos.programas.length} programas`;
  document.getElementById("rail-estado").innerHTML = `
    <div class="rail-estado-fila"><span>Programas conectados</span><b>${conectados} / ${datos.programas.length}</b></div>
    <div class="rail-estado-fila"><span>Proveedor de IA</span><b>${datos.clave_configurada ? nombreProveedor : "sin configurar"}</b></div>
    <div class="rail-estado-fila"><span>Modelo</span><b>${datos.clave_configurada ? datos.modelo : "—"}</b></div>`;
}

/* ---------- Skills ---------- */

async function cargarSkills() {
  const r = await fetch("/api/skills");
  if (!r.ok) return;
  const lista = await r.json();
  const cont = document.getElementById("skills");
  cont.innerHTML = "";
  cont.removeAttribute("aria-busy");
  for (const s of lista) {
    const btn = document.createElement("button");
    btn.className = "skill";
    btn.innerHTML = `<span class="icono">${svgIcono(s.icono)}</span><span>${s.nombre}<small>${s.descripcion || ""}</small></span>`;
    btn.onclick = () => enviar(s.prompt);
    cont.appendChild(btn);
  }
  escalonar(cont.children);
}

/* ---------- Modal de ayuda ---------- */

async function abrirAyuda(programaId) {
  const modal = document.getElementById("modal-ayuda");
  const prog = (estadoAnterior?.programas || []).find((p) => p.id === programaId);
  document.getElementById("ayuda-titulo").textContent = "Conectar " + (prog ? prog.nombre : programaId);
  document.getElementById("ayuda-texto").textContent = (prog && prog.ayuda) || "Sin instrucciones disponibles.";
  document.getElementById("ayuda-resultado").classList.add("oculto");
  const btnAuto = document.getElementById("btn-conectar-auto");
  const etiquetaAuto = () => { btnAuto.innerHTML = `${svgIcono("rayo")}Conectar automáticamente`; };
  etiquetaAuto();
  btnAuto.className = "";
  btnAuto.onclick = async () => {
    btnAuto.disabled = true;
    btnAuto.innerHTML = conSpinner("Conectando…");
    const res = document.getElementById("ayuda-resultado");
    let conectado = false;
    let detalle = "";
    try {
      const r = await (await fetch("/api/conectar/" + programaId, { method: "POST" })).json();
      conectado = !!r.conectado;
      detalle = r.error || "";
    } catch (e) {
      detalle = "No hay respuesta del servidor.";
    }
    res.classList.remove("oculto", "ok", "fallo");
    res.classList.add(conectado ? "ok" : "fallo");
    res.innerHTML = conectado
      ? lineaConIcono("check", `${escapeHtml(programaId)} conectado correctamente.`)
      : lineaConIcono("advertencia", `No se pudo conectar. ${escapeHtml(detalle || "Revisa el manual.")}`);
    if (conectado) cargarEstado();
    btnAuto.disabled = false;
    etiquetaAuto();
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
const esMovil = () => window.matchMedia("(max-width: 860px)").matches;
const btnMenu = document.getElementById("btn-menu");

// En escritorio el panel se pliega al riel de iconos y recuerda su estado
function alternarPanel(abrir) {
  lateral.classList.toggle("abierto", abrir);
  btnMenu.setAttribute("aria-expanded", String(abrir));
  try { localStorage.setItem("buildai.panel", abrir ? "abierto" : "cerrado"); } catch (_) { /* sin almacenamiento */ }
}
try { if (localStorage.getItem("buildai.panel") === "abierto") lateral.classList.add("abierto"); } catch (_) { /* valor por defecto */ }
btnMenu.setAttribute("aria-expanded", String(lateral.classList.contains("abierto")));

btnMenu.addEventListener("click", () => {
  if (esMovil()) {
    lateral.classList.toggle("oculto");
    fondo.classList.toggle("oculto");
  } else {
    alternarPanel(!lateral.classList.contains("abierto"));
  }
});
fondo.addEventListener("click", () => {
  lateral.classList.add("oculto");
  fondo.classList.add("oculto");
});

/* ---------- Rail de actividad (derecha) ---------- */

const railDerecho = document.getElementById("rail-derecho");
const fondoRail = document.getElementById("fondo-rail");
const btnRail = document.getElementById("btn-rail");
function alternarRail() {
  railDerecho.classList.toggle("oculto");
  fondoRail.classList.toggle("oculto");
  btnRail.classList.remove("novedad");
}
// El cajón está plegado: un punto en su botón avisa de que hay algo nuevo
function marcarNovedadRail() {
  if (railDerecho.classList.contains("oculto") && !pintandoHistorial) btnRail.classList.add("novedad");
}
document.getElementById("btn-rail").addEventListener("click", alternarRail);
document.getElementById("btn-x-rail").addEventListener("click", alternarRail);
fondoRail.addEventListener("click", alternarRail);

/* ---------- Pestañas del panel lateral (Programas / Tareas / Historial) ---------- */

const tabsLateral = document.querySelector(".tabs-lateral");
function activarTabLateral(tab) {
  tabsLateral.dataset.tabActivo = tab;
  tabsLateral.querySelectorAll(".tab-lateral").forEach((b) => {
    b.classList.toggle("activo", b.dataset.tab === tab);
    if (b.dataset.tab === tab) b.setAttribute("aria-current", "true");
    else b.removeAttribute("aria-current");
  });
  document.querySelectorAll(".panel-tab-cuerpo").forEach((p) => {
    p.classList.toggle("oculto", p.dataset.panel !== tab);
  });
}
tabsLateral.addEventListener("click", (e) => {
  const btn = e.target.closest(".tab-lateral");
  if (!btn) return;
  const activa = btn.classList.contains("activo");
  if (esMovil()) {
    if (!activa) activarTabLateral(btn.dataset.tab);
  } else if (activa && lateral.classList.contains("abierto")) {
    alternarPanel(false);
  } else {
    activarTabLateral(btn.dataset.tab);
    alternarPanel(true);
  }
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

function agregarMensaje(tipo, contenido, opciones = {}) {
  const d = document.createElement("div");
  d.className = "mensaje " + tipo;
  if (tipo === "usuario") {
    d.innerHTML = `<div class="burbuja"></div>`;
    const burbuja = d.querySelector(".burbuja");
    if (opciones.adjuntos && opciones.adjuntos.length) {
      const cont = document.createElement("div");
      cont.className = "adjuntos-mensaje";
      for (const url of opciones.adjuntos) {
        const img = document.createElement("img");
        img.src = url;
        img.alt = "Imagen adjunta";
        img.onclick = () => abrirLightbox(url, "adjunto.jpg");
        cont.appendChild(img);
      }
      burbuja.appendChild(cont);
    }
    if (contenido) {
      const p = document.createElement("div");
      p.textContent = contenido;
      burbuja.appendChild(p);
    }
    transcripcion.push({ rol: "Tú", texto: contenido });
  } else if (tipo === "asistente") {
    d.innerHTML = `<div class="burbuja md">${md(contenido)}<button class="btn-copiar" title="Copiar respuesta"></button></div>`;
    const btn = d.querySelector(".btn-copiar");
    btn.innerHTML = svgIcono("copiar");
    btn.onclick = async () => {
      try { await navigator.clipboard.writeText(contenido); } catch (_) {
        avisar("No se pudo copiar la respuesta", "error");
        return;
      }
      btn.innerHTML = svgIcono("check");
      avisar("Respuesta copiada");
      setTimeout(() => { btn.innerHTML = svgIcono("copiar"); }, 1200);
    };
    transcripcion.push({ rol: "BuildAI", texto: contenido });
    // Remate: solo cuando la respuesta llega en vivo (no al reabrir una sesión
    // guardada) la hoja se despliega de izquierda a derecha.
    if (opciones.animarFinal) {
      const burbuja = d.querySelector(".burbuja");
      burbuja.classList.add("despliega");
      burbuja.addEventListener("animationend", (e) => {
        if (e.animationName === "despliega") burbuja.classList.remove("despliega");
      });
    }
  } else {
    d.innerHTML = `<div class="burbuja">${contenido}</div>`;
  }
  // Lo que escribe el usuario siempre se muestra, aunque estuviera leyendo más arriba
  insertarMensaje(d, { forzar: tipo === "usuario" });
}

function agregarMensajeUsuario(texto, adjuntos) {
  agregarMensaje("usuario", texto, { adjuntos });
}

/* ---------- Renders: imagen en el chat + visor ampliado ---------- */

function agregarRender(archivo) {
  const src = "/api/renders/" + encodeURIComponent(archivo);
  const d = document.createElement("div");
  d.className = "mensaje asistente render";
  // Las imágenes "plano-*" son el control de una reconstrucción de plano (lo
  // reconstruido encima del original), no un render: rotularlas como render
  // fotorrealista confundiría al usuario sobre qué está mirando.
  // Las "ref-*" son fotos reales de referencia (con su autor y licencia en el pie).
  const esPlano = archivo.startsWith("plano-");
  const esReferencia = archivo.startsWith("ref-");
  const etiqueta = esPlano ? "Plano" : esReferencia ? "Referencia" : "Render";
  const pie = esPlano ? "Reconstrucción sobre el plano original"
    : esReferencia ? "Foto de referencia (autor y licencia en la imagen)" : "Render fotorrealista";
  d.innerHTML = `<div class="burbuja burbuja-render">
    <span class="tag-artefacto">${etiqueta}</span>
    <img class="imagen-render" loading="lazy" alt="${pie}">
    <div class="pie-render"><span>${svgIcono(esPlano ? "planta" : esReferencia ? "imagen" : "chispa")} ${pie}</span></div>
  </div>`;
  const img = d.querySelector("img");
  img.src = src;
  img.onclick = () => abrirLightbox(src, archivo);
  img.onerror = () => d.remove(); // el archivo ya no existe (sesión antigua)
  revelarEnVivo(d.querySelector(".burbuja"));
  insertarMensaje(d);
  transcripcion.push({ rol: "render", archivo });
  agregarEntregableRail(archivo, src);
}

/* ---------- Entregables: archivos reales exportados de cada programa ---------- */

function tamanoLegible(bytes, sufijo = "") {
  if (!bytes) return "";
  const u = ["B", "KB", "MB", "GB"];
  let i = 0, n = bytes;
  while (n >= 1024 && i < u.length - 1) { n /= 1024; i++; }
  return `${n < 10 && i > 0 ? n.toFixed(1) : Math.round(n)} ${u[i]}${sufijo}`;
}

function agregarEntregable(ev) {
  const src = "/api/entregables/" + encodeURIComponent(ev.archivo);
  const d = document.createElement("div");
  d.className = "mensaje asistente entregable";
  d.innerHTML = `<div class="burbuja burbuja-entregable">
    <span class="entregable-formato">${escapeHtml(ev.formato)}</span>
    <span class="entregable-datos">
      <b></b>
      <small>${escapeHtml(tamanoLegible(ev.bytes, " · "))}listo para abrir en tu programa</small>
    </span>
    <a class="btn-entregable">${svgIcono("descargar")}<span>Descargar</span></a>
  </div>`;
  d.querySelector(".entregable-datos b").textContent = ev.archivo;
  const enlace = d.querySelector(".btn-entregable");
  enlace.href = src;
  enlace.setAttribute("download", ev.archivo);
  revelarEnVivo(d.querySelector(".burbuja"));
  insertarMensaje(d);
  transcripcion.push({ rol: "entregable", archivo: ev.archivo, formato: ev.formato });
  agregarEntregableArchivoRail(ev, src);
}

/* ---------- Rail: entregables (renders y archivos) y actividad ---------- */

function marcarVacioRail(idLista) {
  const lista = document.getElementById(idLista);
  const vacio = document.querySelector(`.rail-vacio[data-vacio-de="${idLista}"]`);
  if (vacio) vacio.classList.toggle("oculto", lista.children.length > 0);
}

function agregarEntregableRail(archivo, src) {
  const cont = document.getElementById("rail-entregables");
  const d = document.createElement("button");
  d.type = "button";
  d.className = "entregable-thumb";
  d.title = archivo;
  d.innerHTML = `<img src="${src}" loading="lazy" alt="">`;
  d.onclick = () => abrirLightbox(src, archivo);
  d.querySelector("img").onerror = () => { d.remove(); marcarVacioRail("rail-entregables"); };
  if (pintandoHistorial) d.classList.add("sin-anim");
  cont.prepend(d);
  marcarVacioRail("rail-entregables");
  marcarNovedadRail();
}

function agregarEntregableArchivoRail(ev, src) {
  const cont = document.getElementById("rail-entregables");
  const a = document.createElement("a");
  a.className = "entregable-archivo";
  a.title = `${ev.archivo} (${tamanoLegible(ev.bytes)})`;
  a.href = src;
  a.setAttribute("download", ev.archivo);
  a.innerHTML = `${svgIcono("archivo")}<span>${escapeHtml(ev.formato)}</span>`;
  if (pintandoHistorial) a.classList.add("sin-anim");
  cont.prepend(a);
  marcarVacioRail("rail-entregables");
  marcarNovedadRail();
}

function agregarActividadRail(ev) {
  const cont = document.getElementById("rail-actividad");
  const d = document.createElement("div");
  d.className = "actividad-item";
  d.innerHTML = `<span class="icono">${svgIcono((ev.programa || "").toLowerCase())}</span>
    <span class="actividad-item-texto"><b>${escapeHtml(ev.nombre)}</b><small>${escapeHtml(ev.programa || "")}</small></span>`;
  if (pintandoHistorial) d.classList.add("sin-anim");
  cont.prepend(d);
  // Se limita el historial visible del rail para que no crezca sin fin en
  // sesiones largas; la conversación completa sigue íntegra en el chat.
  while (cont.children.length > 30) cont.lastElementChild.remove();
  marcarVacioRail("rail-actividad");
  marcarNovedadRail();
}

function abrirLightbox(src, archivo) {
  const caja = document.getElementById("lightbox");
  const img = document.getElementById("lightbox-img");
  const enlace = document.getElementById("lightbox-descargar");
  img.src = src;
  enlace.href = src;
  enlace.setAttribute("download", archivo || "render.png");
  caja.classList.remove("oculto");
}

document.getElementById("lightbox").addEventListener("click", (e) => {
  if (e.target.id !== "lightbox-descargar") {
    document.getElementById("lightbox").classList.add("oculto");
  }
});
document.getElementById("lightbox-descargar").addEventListener("click", (e) => e.stopPropagation());

function agregarActividadHerramienta(ev) {
  const detalle = ev.detalle ? `<pre>${escapeHtml(ev.detalle)}</pre>` : "";
  agregarMensaje("actividad",
    `<details><summary>${icono((ev.programa || "").toLowerCase())} ${escapeHtml(ev.nombre)}</summary>${detalle}</details>`);
  transcripcion.push({ rol: "herramienta", nombre: `${ev.programa} · ${ev.nombre}`, detalle: ev.detalle || "" });
  agregarActividadRail(ev);
}

function lineaConIcono(icono, texto) {
  return `<span class="linea-icono">${svgIcono(icono)} ${texto}</span>`;
}

/* ---------- Tira de fases ----------
   Recibir → pensar → actuar → entregar. Es el único elemento de la interfaz con
   movimiento continuo: cada fase tiene su icono giratorio y su propio
   vocabulario, y la entrega cierra con un trazo que se dibuja. */

const rayoRueda = [[16, 12, 21, 12], [14.83, 14.83, 18.36, 18.36], [12, 16, 12, 21], [9.17, 14.83, 5.64, 18.36],
  [8, 12, 3, 12], [9.17, 9.17, 5.64, 5.64], [12, 8, 12, 3], [14.83, 9.17, 18.36, 5.64]]
  .map(([a, b, c, d]) => `<line x1="${a}" y1="${b}" x2="${c}" y2="${d}"/>`).join("");

const SVG_FASE = {
  recibir: `<svg viewBox="0 0 24 24" class="ic-radar"><circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="1.5" fill="currentColor"/><g class="barrido"><line x1="12" y1="12" x2="12" y2="3"/></g></svg>`,
  pensar: `<svg viewBox="0 0 24 24" class="ic-orbita"><circle cx="12" cy="12" r="1.8" fill="currentColor"/><g class="orbita-1"><circle cx="12" cy="3.5" r="1.6" fill="currentColor"/></g><g class="orbita-2"><circle cx="12" cy="12" r="6.5" stroke-dasharray="2 4"/><circle cx="18.5" cy="12" r="1.4" fill="currentColor"/></g></svg>`,
  actuar: `<svg viewBox="0 0 24 24" class="ic-rueda"><circle cx="12" cy="12" r="1.8" fill="currentColor"/><g class="rayos">${rayoRueda}</g></svg>`,
  detener: `<svg viewBox="0 0 24 24" class="ic-parar"><rect class="cuadro" x="7" y="7" width="10" height="10" rx="2" fill="currentColor"/></svg>`,
  entregar: `<svg viewBox="0 0 24 24" class="ic-entrega"><circle class="onda" cx="12" cy="12" r="9"/><circle class="aro" cx="12" cy="12" r="10" transform="rotate(-90 12 12)"/><path class="visto" d="M7.5 12.5 L10.5 15.5 L16.5 9"/></svg>`,
};

// `paso` es la posición en la tira de cuatro pasos; las palabras rotan mientras dura la fase
const FASES = {
  recibir: { paso: 0, palabras: ["Recibiendo", "Leyendo tu encargo", "Interpretando"],
    anuncio: "Recibiendo tu encargo" },
  pensar: { paso: 1, palabras: ["Meditando", "Trazando ideas", "Proporcionando", "Acotando", "Replanteando"],
    anuncio: "La IA está pensando" },
  actuar: { paso: 2, palabras: ["Levantando", "Modelando", "Colocando", "Encofrando", "Nivelando", "Escuadrando"],
    anuncio: "Trabajando sobre tu programa" },
  detener: { paso: 1, palabras: ["Deteniendo"], anuncio: "Deteniendo la tarea" },
  entregar: { paso: 3, palabras: ["Listo"], anuncio: "Resultado listo" },
};
const MIN_RECIBIR_MS = 800; // que "recibir" llegue a leerse aunque el servidor responda al instante
const PERMANENCIA_ENTREGA_MS = 2200;

const panelFases = document.getElementById("fases");
const elPalabra = document.getElementById("fase-palabra");
let faseActual = null;
let faseDesde = 0;
let indicePalabra = 0;
let inicioTrabajo = 0;
let timerPalabra = null;
let timerTiempo = null;
let timerCierre = null;
let timerPendiente = null;

function textoTiempo() {
  const s = Math.round((Date.now() - inicioTrabajo) / 1000);
  if (s < 3) return "";
  return s < 60 ? `${s} s` : `${Math.floor(s / 60)} min ${String(s % 60).padStart(2, "0")} s`;
}

function pintarPalabra() {
  const palabras = FASES[faseActual].palabras;
  elPalabra.textContent = palabras[indicePalabra % palabras.length];
  elPalabra.style.animation = "none";
  void elPalabra.offsetWidth; // reinicia la entrada de la palabra
  elPalabra.style.animation = "";
}

function irAFase(fase, detalle = "") {
  clearTimeout(timerCierre);
  clearTimeout(timerPendiente);
  panelFases.classList.remove("oculto");
  document.getElementById("fase-detalle").textContent = detalle;
  if (fase === faseActual) return;
  faseActual = fase;
  faseDesde = Date.now();
  panelFases.dataset.fase = fase;
  document.getElementById("fase-icono").innerHTML = SVG_FASE[fase];
  const def = FASES[fase];
  panelFases.querySelectorAll(".fase-pasos li").forEach((li, i) => {
    li.classList.toggle("actual", i === def.paso && fase !== "entregar");
    li.classList.toggle("hecho", i < def.paso);
    if (i === def.paso && fase !== "entregar") li.setAttribute("aria-current", "step");
    else li.removeAttribute("aria-current");
  });
  // Cada vez que cambia la fase se anuncia una sola vez a lectores de pantalla
  document.getElementById("fase-anuncio").textContent = def.anuncio;
  indicePalabra = fase === "recibir" ? 0 : Math.floor(Math.random() * def.palabras.length);
  pintarPalabra();
  clearInterval(timerPalabra);
  timerPalabra = def.palabras.length > 1
    ? setInterval(() => { indicePalabra++; pintarPalabra(); }, 2600)
    : null;
  document.getElementById("fase-tiempo").textContent = fase === "entregar" ? "" : textoTiempo();
}

// Cambia de fase respetando la permanencia mínima de "recibir"
function solicitarFase(fase, detalle = "") {
  const restante = MIN_RECIBIR_MS - (Date.now() - faseDesde);
  clearTimeout(timerPendiente);
  if (faseActual === "recibir" && restante > 0) {
    timerPendiente = setTimeout(() => irAFase(fase, detalle), restante);
  } else {
    irAFase(fase, detalle);
  }
}

function comenzarTrabajo() {
  inicioTrabajo = Date.now();
  clearInterval(timerTiempo);
  timerTiempo = setInterval(() => {
    if (faseActual && faseActual !== "entregar") document.getElementById("fase-tiempo").textContent = textoTiempo();
  }, 1000);
  faseActual = null;
  irAFase("recibir");
}

function ocultarFases() {
  clearTimeout(timerCierre);
  clearTimeout(timerPendiente);
  clearInterval(timerPalabra);
  clearInterval(timerTiempo);
  timerPalabra = timerTiempo = null;
  faseActual = null;
  panelFases.classList.add("oculto");
}

// Entrega: la tira se cierra en verde con el visto dibujado y luego se retira
function entregarResultado() {
  clearTimeout(timerPendiente);
  irAFase("entregar");
  clearInterval(timerTiempo);
  timerTiempo = null;
  timerCierre = setTimeout(ocultarFases, PERMANENCIA_ENTREGA_MS);
}

/* ---------- Adjuntar imágenes y vídeos ---------- */

// Reducimos las imágenes en el navegador antes de enviarlas: menos peso para
// guardar la sesión y menos coste/tokens en los modelos de visión. 1568 px es
// el lado máximo que aprovechan los modelos actuales sin perder detalle útil.
const MAX_LADO = 1568;
const CALIDAD_JPEG = 0.85;
const FOTOGRAMAS_VIDEO = 4; // fotogramas repartidos que se extraen de un vídeo

// Cada elemento: { url (data URL para la miniatura), kind, imagenes: [{media_type, datos}] }
// Un vídeo es un solo elemento con varios fotogramas dentro de `imagenes`.
let adjuntosPendientes = [];
const inputArchivos = document.getElementById("input-archivos");

function lienzoADataUrl(fuente, w, h) {
  const escala = Math.min(1, MAX_LADO / Math.max(w, h));
  const c = document.createElement("canvas");
  c.width = Math.max(1, Math.round(w * escala));
  c.height = Math.max(1, Math.round(h * escala));
  c.getContext("2d").drawImage(fuente, 0, 0, c.width, c.height);
  return c.toDataURL("image/jpeg", CALIDAD_JPEG);
}

function procesarImagen(file) {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file);
    const img = new Image();
    img.onload = () => {
      URL.revokeObjectURL(url);
      const dataUrl = lienzoADataUrl(img, img.naturalWidth, img.naturalHeight);
      resolve({ url: dataUrl, kind: "imagen", imagenes: [{ media_type: "image/jpeg", datos: dataUrl.split(",")[1] }] });
    };
    img.onerror = () => { URL.revokeObjectURL(url); reject(new Error("no se pudo leer la imagen")); };
    img.src = url;
  });
}

function procesarVideo(file) {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file);
    const video = document.createElement("video");
    video.muted = true;
    video.preload = "auto";
    // Salta a `t` y espera al nuevo fotograma. Si el navegador no dispara
    // `seeked` (asignar el mismo tiempo no genera evento, o el contenedor no
    // permite buscar), sigue tras un margen: así un vídeo raro no cuelga la
    // carga de adjuntos para siempre.
    const irA = (t) => new Promise((res) => {
      let resuelto = false;
      const fin = () => {
        if (resuelto) return;
        resuelto = true;
        video.onseeked = null;
        clearTimeout(reloj);
        res();
      };
      const reloj = setTimeout(fin, 2000);
      video.onseeked = fin;
      video.currentTime = t;
    });
    video.onloadeddata = async () => {
      const dur = isFinite(video.duration) && video.duration > 0 ? video.duration : 0;
      const w = video.videoWidth, h = video.videoHeight;
      const imagenes = [];
      let portada = null;
      try {
        // Con duración desconocida no se puede repartir el muestreo: usamos el
        // fotograma ya cargado en vez de buscar (buscar a 0 no dispara `seeked`).
        const tiempos = dur
          ? Array.from({ length: FOTOGRAMAS_VIDEO }, (_, i) => (dur * (i + 1)) / (FOTOGRAMAS_VIDEO + 1))
          : [null];
        for (const t of tiempos) {
          if (t !== null) await irA(t);
          const dataUrl = lienzoADataUrl(video, w, h);
          if (!portada) portada = dataUrl;
          imagenes.push({ media_type: "image/jpeg", datos: dataUrl.split(",")[1] });
        }
      } catch (e) {
        URL.revokeObjectURL(url);
        reject(e);
        return;
      }
      URL.revokeObjectURL(url);
      resolve({ url: portada, kind: "video", imagenes });
    };
    video.onerror = () => { URL.revokeObjectURL(url); reject(new Error("no se pudo leer el vídeo")); };
    video.src = url;
  });
}

// Planos PDF o DXF: el navegador no sabe convertirlos en imagen, así que los
// convierte el servidor, que además guarda el original (la alta resolución del
// PDF y la geometría exacta del DXF) para las herramientas de planos.
function esPlanoVectorial(file) {
  return /\.(pdf|dxf)$/i.test(file.name) || file.type === "application/pdf";
}

function leerBase64(file) {
  return new Promise((resolve, reject) => {
    const lector = new FileReader();
    lector.onload = () => resolve(String(lector.result).split(",")[1] || "");
    lector.onerror = () => reject(new Error("no se pudo leer el archivo"));
    lector.readAsDataURL(file);
  });
}

async function procesarPlano(file) {
  const datos = await leerBase64(file);
  const r = await fetch("/api/planos/importar", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ nombre: file.name, datos }),
  });
  const res = await r.json();
  if (!res.ok) throw new Error(res.error || "el servidor no pudo convertirlo");
  const primera = res.adjuntos[0];
  return { url: `data:${primera.media_type};base64,${primera.datos}`, kind: "plano", imagenes: res.adjuntos };
}

async function agregarArchivos(files) {
  for (const file of files) {
    try {
      if (esPlanoVectorial(file)) {
        adjuntosPendientes.push(await procesarPlano(file));
      } else if (file.type.startsWith("image/")) {
        adjuntosPendientes.push(await procesarImagen(file));
      } else if (file.type.startsWith("video/")) {
        adjuntosPendientes.push(await procesarVideo(file));
      } else {
        continue;
      }
    } catch (e) {
      agregarMensaje("error", lineaConIcono("advertencia",
        `No pude leer «${file.name}»: ${e.message}. Prueba con una imagen, un vídeo o un plano (JPG, PNG, MP4, PDF, DXF).`));
    }
  }
  renderAdjuntosPrevia();
}

function renderAdjuntosPrevia() {
  const cont = document.getElementById("adjuntos-previa");
  cont.innerHTML = "";
  cont.classList.toggle("oculto", adjuntosPendientes.length === 0);
  adjuntosPendientes.forEach((a, i) => {
    const chip = document.createElement("div");
    chip.className = "adjunto-chip";
    chip.innerHTML = `<img alt="">
      <span class="adjunto-marca">${svgIcono(a.kind === "video" ? "video" : a.kind === "plano" ? "archivo" : "imagen")}</span>
      <button type="button" class="adjunto-quitar" title="Quitar">${svgIcono("cerrar")}</button>`;
    chip.querySelector("img").src = a.url;
    chip.querySelector(".adjunto-quitar").onclick = () => {
      adjuntosPendientes.splice(i, 1);
      renderAdjuntosPrevia();
    };
    cont.appendChild(chip);
  });
}

document.getElementById("btn-adjuntar").addEventListener("click", () => inputArchivos.click());
inputArchivos.addEventListener("change", () => {
  agregarArchivos(Array.from(inputArchivos.files || []));
  inputArchivos.value = ""; // permite volver a elegir el mismo archivo
});

// Pegar (Ctrl+V) una imagen y arrastrar archivos sobre la caja también adjuntan
entrada.addEventListener("paste", (e) => {
  const files = Array.from(e.clipboardData?.files || []);
  if (files.length) { e.preventDefault(); agregarArchivos(files); }
});
formulario.addEventListener("dragover", (e) => { e.preventDefault(); formulario.classList.add("arrastrando"); });
formulario.addEventListener("dragleave", (e) => { if (e.target === formulario) formulario.classList.remove("arrastrando"); });
formulario.addEventListener("drop", (e) => {
  e.preventDefault();
  formulario.classList.remove("arrastrando");
  const files = Array.from(e.dataTransfer?.files || [])
    .filter((f) => f.type.startsWith("image/") || f.type.startsWith("video/"));
  if (files.length) agregarArchivos(files);
});

/* ---------- Enviar mensaje ---------- */

formulario.addEventListener("submit", (e) => {
  e.preventDefault();
  if (ocupado) {
    detenerTarea();
    return;
  }
  const texto = entrada.value.trim();
  if (!texto && !adjuntosPendientes.length) return;
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
  irAFase("detener", "Termino el paso en curso para no dejar nada a medias");
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
  // Se toman los adjuntos preparados en la bandeja y se incorporan al mensaje.
  const grupos = adjuntosPendientes;
  const imagenesEnviar = grupos.flatMap((g) => g.imagenes);
  const urlsPrevia = grupos.map((g) => g.url);
  adjuntosPendientes = [];
  renderAdjuntosPrevia();
  agregarMensajeUsuario(texto, urlsPrevia);

  if (!estadoAnterior || !estadoAnterior.clave_configurada) {
    agregarMensaje("error", lineaConIcono("advertencia",
      "Antes de hablar conmigo, abre Ajustes (icono de engranaje arriba) y elige un proveedor de IA con su clave."));
    return;
  }

  ocupado = true;
  btnEnviar.classList.add("detener");
  btnEnviar.innerHTML = svgIcono("detener");
  btnEnviar.title = "Detener la tarea";
  comenzarTrabajo();

  try {
    const r = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mensaje: texto, adjuntos: imagenesEnviar }),
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
          agregarMensaje("asistente", ev.texto, { animarFinal: true });
          entregarResultado();
        } else if (ev.tipo === "error") {
          ocultarFases();
          agregarMensaje("error", lineaConIcono("advertencia", ev.texto));
        } else if (ev.tipo === "herramienta") {
          // A partir de aquí ya no solo "piensa": está actuando sobre el
          // programa conectado, así que el indicador cambia de fase.
          solicitarFase("actuar", `${ev.programa || "Programa"} · ${ev.nombre}`);
          // Se inserta encima del indicador, que sigue mostrando actividad
          agregarActividadHerramienta(ev);
        } else if (ev.tipo === "render") {
          agregarRender(ev.archivo);
        } else if (ev.tipo === "entregable") {
          agregarEntregable(ev);
        } else if (ev.tipo === "estado") {
          solicitarFase("pensar", /^pensando/i.test(ev.texto || "") ? "" : (ev.texto || ""));
        }
      }
    }
  } catch (err) {
    ocultarFases();
    agregarMensaje("error", lineaConIcono("advertencia", "Error de conexión: " + err.message));
  }

  ocupado = false;
  // Si acabó con una entrega, la tira se retira sola tras su remate
  if (faseActual !== "entregar") ocultarFases();
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
  const activa = datos.sesiones.find((s) => s.id === datos.actual);
  const hayConversacion = document.querySelector(".bienvenida").classList.contains("oculto");
  document.getElementById("titulo-barra").textContent =
    hayConversacion && activa ? activa.titulo : "Nueva conversación";
  const cont = document.getElementById("sesiones");
  cont.innerHTML = "";
  cont.removeAttribute("aria-busy");
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
    let reloj = null;
    const cancelarConfirmacion = () => {
      clearTimeout(reloj);
      d.classList.remove("confirmando");
      borrar.classList.remove("confirmar");
      borrar.innerHTML = svgIcono("papelera");
      borrar.title = "Borrar esta conversación";
    };
    borrar.onclick = async () => {
      // Primer clic: pide confirmar en el propio elemento (el diálogo nativo
      // bloquea la ventana y rompe el estilo). Segundo clic en 3 s: borra.
      if (!borrar.classList.contains("confirmar")) {
        d.classList.add("confirmando");
        borrar.classList.add("confirmar");
        borrar.innerHTML = `${svgIcono("papelera")}¿Borrar?`;
        borrar.title = `Confirmar: borrar «${s.titulo}» definitivamente`;
        reloj = setTimeout(cancelarConfirmacion, 3000);
        return;
      }
      clearTimeout(reloj);
      const r = await (await fetch("/api/sesiones/" + s.id, { method: "DELETE" })).json();
      if (!r.ok) {
        cancelarConfirmacion();
        agregarMensaje("error", lineaConIcono("advertencia", r.error));
        return;
      }
      d.classList.add("saliendo");
      await esperarAnimacion(d);
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
  document.getElementById("titulo-barra").textContent = "Nueva conversación";
  transcripcion = [];
  adjuntosPendientes = [];
  renderAdjuntosPrevia();
  document.getElementById("rail-actividad").innerHTML = "";
  document.getElementById("rail-entregables").innerHTML = "";
  marcarVacioRail("rail-actividad");
  marcarVacioRail("rail-entregables");
}

function pintarConversacion(mensajes) {
  limpiarConversacion();
  document.querySelector(".bienvenida").classList.toggle("oculto", mensajes.length > 0);
  // Un historial guardado aparece ya colocado: animar cien mensajes a la vez es ruido
  pintandoHistorial = true;
  for (const ev of mensajes) {
    if (ev.tipo === "usuario") {
      const urls = (ev.adjuntos || []).map((a) => `data:${a.media_type};base64,${a.datos}`);
      agregarMensaje("usuario", ev.texto, { adjuntos: urls });
    }
    else if (ev.tipo === "respuesta") agregarMensaje("asistente", ev.texto);
    else if (ev.tipo === "herramienta") agregarActividadHerramienta(ev);
    else if (ev.tipo === "render") agregarRender(ev.archivo);
    else if (ev.tipo === "entregable") agregarEntregable(ev);
  }
  pintandoHistorial = false;
  bajarChat({ suave: false });
  actualizarBtnAbajo();
}

/* ---------- Exportar conversación ---------- */

document.getElementById("btn-exportar").addEventListener("click", () => {
  if (!transcripcion.length) {
    avisar("Todavía no hay nada que exportar: escribe algo primero.", "error");
    return;
  }
  const fecha = new Date();
  let texto = `# Conversación BuildAI — ${fecha.toLocaleString("es")}\n`;
  for (const t of transcripcion) {
    if (t.rol === "herramienta") {
      texto += `\n> 🔧 ${t.nombre}\n`;
      if (t.detalle) texto += `\n\`\`\`\n${t.detalle}\n\`\`\`\n`;
    } else if (t.rol === "render") {
      texto += `\n🖼️ Render generado: ${t.archivo} (carpeta ~/.buildai/renders)\n`;
    } else if (t.rol === "entregable") {
      texto += `\n📐 ${t.formato} exportado: ${t.archivo} (carpeta ~/.buildai/entregables)\n`;
    } else {
      texto += `\n**${t.rol}:**\n\n${t.texto}\n`;
    }
  }
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([texto], { type: "text/markdown" }));
  a.download = `BuildAI-${fecha.toISOString().slice(0, 16).replace(/[T:]/g, "-")}.md`;
  a.click();
  URL.revokeObjectURL(a.href);
  avisar("Conversación descargada en Markdown");
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
  const inpPexels = document.getElementById("inp-pexels");
  inpPexels.value = "";
  inpPexels.placeholder = configuracion.servicios_configurados?.pexels
    ? "Clave guardada ✓ (escribe otra para cambiarla)"
    : "Sin clave se usan fotos de Openverse";
  modalAjustes.classList.remove("oculto");
  selProveedor.focus({ preventScroll: true });
}

let peticionModelos = 0; // evita que una respuesta lenta pise al proveedor recién elegido

async function cargarModelosProveedor(id) {
  const listaDatos = document.getElementById("lista-modelos");
  const estadoModelos = document.getElementById("estado-modelos");
  listaDatos.innerHTML = "";
  estadoModelos.classList.remove("aviso-ambar");
  estadoModelos.innerHTML = conSpinner(id === "ollama" ? "Buscando tus modelos locales…" : "Cargando modelos…");
  estadoModelos.classList.add("cargando");
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
  estadoModelos.classList.remove("cargando");
  estadoModelos.textContent = datos.nota || "";
  estadoModelos.classList.toggle("aviso-ambar", !datos.disponible);
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
  document.getElementById("estado-clave").classList.remove("aviso-rojo", "aviso-ambar");
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

// Resultado de guardar/probar la conexión, dentro de Ajustes (donde se arregla).
function mostrarEstadoClave(texto, tipo) {
  const estado = document.getElementById("estado-clave");
  estado.textContent = texto;
  estado.classList.toggle("aviso-rojo", tipo === "error");
  estado.classList.toggle("aviso-ambar", tipo === "ambar");
  estado.setAttribute("role", tipo === "error" ? "alert" : "status");
}

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
  btnGuardarAjustes.innerHTML = conSpinner("Guardando…");
  try {
    const r = await fetch("/api/config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        proveedor: id,
        claves: { [id]: inpClave.value },
        modelos: { [id]: inpModelo.value },
        servicios: { pexels: document.getElementById("inp-pexels").value },
      }),
    });
    const res = r.ok ? await r.json() : { ok: false, error: "No se pudieron guardar los ajustes." };
    if (!res.ok) {
      // La clave no se guarda (p. ej. caracteres que se colaron al copiarla):
      // el modal sigue abierto para que la corrija sin perder lo escrito.
      mostrarEstadoClave(res.error, "error");
      avisar("No se guardó: revisa la clave", "error");
      return;
    }
    // Guardado: ahora se comprueba de verdad que la clave y el modelo funcionan,
    // para que un error aparezca aquí y no a mitad del primer encargo.
    btnGuardarAjustes.innerHTML = conSpinner("Probando la conexión…");
    let prueba;
    try {
      prueba = await (await fetch("/api/config/probar", { method: "POST" })).json();
    } catch (e) {
      prueba = { ok: false, error: "No se pudo comprobar la conexión con BuildAI." };
    }
    cargarEstado();
    configuracion = await (await fetch("/api/config")).json();
    const avisosProveedor = (res.avisos || []).join(" ");
    if (!prueba.ok) {
      mostrarEstadoClave([avisosProveedor, prueba.error].filter(Boolean).join(" "), "error");
      avisar("Guardado, pero la conexión no funciona todavía", "error");
      return;
    }
    if (avisosProveedor) {
      mostrarEstadoClave(`${prueba.mensaje} Aviso: ${avisosProveedor}`, "ambar");
      return;
    }
    cerrarAjustes();
    avisar(prueba.mensaje);
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

/* ---------- Apariencia: tema y tamaño del texto ---------- */

function marcarOpcionApariencia(grupo, valor) {
  document.querySelectorAll(`.opciones[data-grupo="${grupo}"] .opcion`).forEach((b) => {
    b.setAttribute("aria-pressed", String(b.dataset.valor === valor));
  });
}
function aplicarApariencia(grupo, valor) {
  document.documentElement.dataset[grupo] = valor;
  try { localStorage.setItem("buildai." + grupo, valor); } catch (_) { /* sin almacenamiento */ }
  marcarOpcionApariencia(grupo, valor);
}
for (const grupo of ["tema", "texto"]) marcarOpcionApariencia(grupo, document.documentElement.dataset[grupo]);
document.querySelectorAll(".opciones").forEach((caja) => {
  caja.addEventListener("click", (e) => {
    const b = e.target.closest(".opcion");
    if (b) aplicarApariencia(caja.dataset.grupo, b.dataset.valor);
  });
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

document.getElementById("btn-nueva-lateral").addEventListener("click", () => {
  document.getElementById("btn-nueva").click();
  // En pantallas pequeñas el cajón tapa el chat: cerrarlo al empezar
  if (window.matchMedia("(max-width: 860px)").matches) {
    lateral.classList.add("oculto");
    fondo.classList.add("oculto");
  }
});

/* ---------- Comodidad: cerrar modales y foco ---------- */

// Clic fuera de la caja cierra el modal
for (const id of ["modal-ajustes", "modal-ayuda"]) {
  const modal = document.getElementById(id);
  modal.addEventListener("click", (e) => {
    if (e.target === modal) modal.classList.add("oculto");
  });
}

/* Foco y teclado: mientras haya un modal o un cajón abierto, el resto de la
   página queda `inert` (no se enfoca ni se lee) y al cerrar el foco vuelve a
   donde estaba. Escape cierra lo que esté encima. */
const regionesDeFondo = ["principal", "lateral", "rail-derecho"].map((id) => document.getElementById(id));
let focoPrevio = null;
function modalAbierto() { return document.querySelector(".modal:not(.oculto)"); }
function cajonRailAbierto() { return !railDerecho.classList.contains("oculto"); }
function cajonLateralAbierto() { return esMovil() && !lateral.classList.contains("oculto"); }

function sincronizarFondo() {
  const modal = modalAbierto();
  const cajon = cajonRailAbierto() || cajonLateralAbierto();
  // Un modal deja inert todo lo que no lo contiene; un cajón, todo menos él mismo
  regionesDeFondo.forEach((r) => {
    if (modal) r.inert = !modal.contains(r);
    else if (cajonRailAbierto()) r.inert = r !== railDerecho;
    else if (cajonLateralAbierto()) r.inert = r !== lateral;
    else r.inert = false;
  });
  return cajon;
}
// Último elemento enfocado fuera de modales y cajones: es donde hay que volver.
// Se sigue con focusin porque algunos modales enfocan un campo en el mismo
// instante en que se abren, antes de que nadie pueda leer el foco anterior.
let ultimoFocoFuera = null;
document.addEventListener("focusin", (e) => {
  if (!e.target.closest(".modal, #rail-derecho, #lateral.oculto")) ultimoFocoFuera = e.target;
});
function llevarFoco(contenedor) {
  if (!focoPrevio) focoPrevio = ultimoFocoFuera;
  const destino = contenedor.querySelector("button, [href], input, select, textarea");
  if (destino) destino.focus({ preventScroll: true });
}
function devolverFoco() {
  if (focoPrevio && document.contains(focoPrevio)) focoPrevio.focus({ preventScroll: true });
  focoPrevio = null;
}
document.querySelectorAll(".modal").forEach((m) => {
  new MutationObserver(() => {
    sincronizarFondo();
    if (!m.classList.contains("oculto")) llevarFoco(m);
    else if (!modalAbierto()) devolverFoco();
  }).observe(m, { attributes: true, attributeFilter: ["class"] });
});
[railDerecho, lateral].forEach((cajon) => {
  new MutationObserver(() => {
    sincronizarFondo();
    const abierto = cajon === railDerecho ? cajonRailAbierto() : cajonLateralAbierto();
    if (abierto) llevarFoco(cajon);
    else if (!modalAbierto() && !cajonRailAbierto() && !cajonLateralAbierto()) devolverFoco();
  }).observe(cajon, { attributes: true, attributeFilter: ["class"] });
});

// Escape cierra lo que esté encima: modal, cajón de actividad o cajón móvil
document.addEventListener("keydown", (e) => {
  if (e.key !== "Escape") return;
  if (modalAbierto()) {
    document.querySelectorAll(".modal:not(.oculto)").forEach((m) => m.classList.add("oculto"));
  } else if (cajonRailAbierto()) {
    alternarRail();
  } else if (cajonLateralAbierto()) {
    lateral.classList.add("oculto");
    fondo.classList.add("oculto");
  }
});

// El pie con el modelo activo abre Ajustes directamente
document.getElementById("info-modelo").addEventListener("click", abrirAjustes);
document.getElementById("info-modelo").addEventListener("keydown", (e) => {
  if (e.key === "Enter" || e.key === " ") { e.preventDefault(); abrirAjustes(); }
});

/* ---------- Arranque ---------- */

cargarEstado();
cargarSkills();
cargarSesiones();
setInterval(cargarEstado, 10000);
entrada.focus();
