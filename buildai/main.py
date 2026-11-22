"""Servidor local de BuildAI: API + interfaz web, mostrada en una ventana nativa.

Arranque:  python -m buildai.main   (o el acceso directo «BuildAI»)
Interfaz:  http://127.0.0.1:8600  (servida dentro de la ventana, no en el navegador)
"""

import asyncio
import json
import os
import queue
import sys
import threading
import time
import urllib.request
import webbrowser
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

# Empaquetado con PyInstaller en modo ventana (--noconsole): no hay stdout/stderr
# real y las llamadas a print() revientan con AttributeError sobre None.
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

from . import config as cfg
from . import instalador
from . import modelos as catalogo_modelos
from . import entregables
from . import sesiones
from .agent import CARPETA_RENDERS, ejecutar_turno
from .connectors import CONECTORES
from . import conocimiento
from . import ia_local
from .planos import importar as importar_planos
from .providers import ErrorProveedor, probar_conexion
from .providers.claves import ClaveInvalida, aviso_proveedor, limpiar as limpiar_clave

PUERTO = 8600
CARPETA_UI = Path(__file__).resolve().parent / "ui"

app = FastAPI(title="BuildAI")

# Conversación activa (aplicación local de un solo usuario). Cada conversación
# es una sesión persistida en disco; se puede retomar desde el historial.
_historial: list = []
_sesion_id = sesiones.nuevo_id()
_ocupado = threading.Lock()
_cancelar = threading.Event()


@app.get("/")
def portada():
    return FileResponse(CARPETA_UI / "index.html")


@app.get("/manual")
def manual():
    return FileResponse(CARPETA_UI / "manual.html")


@app.get("/api/renders/{nombre}")
def ver_render(nombre: str):
    """Sirve un render generado por Blender. Solo nombres simples de archivo
    dentro de la carpeta de renders (el nombre viene de eventos propios, pero
    se valida igualmente para que no pueda salir de esa carpeta)."""
    ruta = CARPETA_RENDERS / nombre
    # PNG: renders y controles de plano; JPEG: fotos de referencia descargadas.
    tipos = {".png": "image/png", ".jpg": "image/jpeg"}
    if (
        "/" in nombre or "\\" in nombre or nombre.startswith(".")
        or ruta.suffix.lower() not in tipos or not ruta.is_file()
    ):
        return Response(status_code=404)
    return FileResponse(ruta, media_type=tipos[ruta.suffix.lower()])


@app.get("/api/entregables/{nombre}")
def descargar_entregable(nombre: str):
    """Sirve un archivo exportado (IFC, DWG, DXF, PDF…). Mismas cautelas que los
    renders: solo nombres simples dentro de la carpeta de entregables y solo
    extensiones de la lista blanca."""
    ruta = entregables.CARPETA_ENTREGABLES / nombre
    if (
        "/" in nombre or "\\" in nombre or nombre.startswith(".")
        or not entregables.extension_valida(nombre) or not ruta.is_file()
    ):
        return Response(status_code=404)
    return FileResponse(
        ruta,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{ruta.name}"'},
    )


def _disponible_seguro(conector) -> bool:
    try:
        return conector.disponible()
    except Exception:
        return False


@app.get("/api/estado")
def estado():
    configuracion = cfg.cargar()
    proveedor = configuracion["proveedor"]
    # Comprobar los conectores en paralelo: en serie, cada programa cerrado
    # suma su timeout y el estado tarda varios segundos en responder
    with ThreadPoolExecutor(max_workers=len(CONECTORES)) as pool:
        conectados = list(pool.map(_disponible_seguro, CONECTORES))
    return {
        "programas": [
            {
                "id": c.id,
                "nombre": c.nombre,
                "icono": c.icono,
                "conectado": conectado,
                "ayuda": c.ayuda,
            }
            for c, conectado in zip(CONECTORES, conectados)
        ],
        "proveedor": proveedor,
        "modelo": cfg.modelo_activo(configuracion),
        "clave_configurada": cfg.proveedor_listo(configuracion),
        # Progreso de la IA incluida (descarga la primera vez, arranque del motor).
        "ia_local": ia_local.estado() if proveedor == "local" else None,
    }


@app.get("/api/config")
def leer_config():
    configuracion = cfg.cargar()
    # No devolvemos las claves completas, solo si existen
    return {
        "proveedor": configuracion["proveedor"],
        "modelos": configuracion["modelos"],
        "claves_configuradas": {k: bool(v) for k, v in configuracion["claves"].items()},
        # Claves de servicios opcionales (bancos de imágenes): tampoco se devuelven.
        "servicios_configurados": {k: bool(v) for k, v in configuracion["servicios"].items()},
        "servicios": cfg.SERVICIOS,
        "proveedores": cfg.PROVEEDORES,
        "modelos_por_defecto": cfg.MODELOS_POR_DEFECTO,
    }


@app.post("/api/config")
async def guardar_config(peticion: Request):
    datos = await peticion.json()
    configuracion = cfg.cargar()
    if datos.get("proveedor") in cfg.PROVEEDORES:
        configuracion["proveedor"] = datos["proveedor"]
    avisos = []
    for nombre, clave in (datos.get("claves") or {}).items():
        if nombre not in configuracion["claves"] or not isinstance(clave, str):
            continue
        try:
            clave = limpiar_clave(clave)
        except ClaveInvalida as exc:
            # No se guarda nada: mejor decirlo ahora que fallar en el primer encargo.
            return {"ok": False, "error": str(exc)}
        if clave:  # vacío = no cambiar
            configuracion["claves"][nombre] = clave
            aviso = aviso_proveedor(clave, nombre)
            if aviso:
                avisos.append(aviso)
    for nombre, modelo in (datos.get("modelos") or {}).items():
        if nombre in configuracion["modelos"] and modelo:
            configuracion["modelos"][nombre] = modelo.strip()
    for nombre, clave in (datos.get("servicios") or {}).items():
        if nombre in configuracion["servicios"] and isinstance(clave, str) and clave.strip():
            configuracion["servicios"][nombre] = clave.strip()  # vacío = no cambiar
    cfg.guardar(configuracion)
    return {"ok": True, "avisos": avisos}


@app.post("/api/config/probar")
async def probar_config():
    """Prueba de verdad la clave y el modelo guardados (petición mínima)."""
    try:
        mensaje = await asyncio.to_thread(probar_conexion, cfg.cargar())
    except ErrorProveedor as exc:
        return {"ok": False, "error": str(exc)}
    except Exception as exc:  # nunca un 500 en Ajustes: el usuario necesita un mensaje
        return {"ok": False, "error": f"No se pudo comprobar la conexión: {exc}"}
    return {"ok": True, "mensaje": mensaje}


_OAUTH_CLIENT_ID = "buildai"


@app.get("/api/oauth/login")
def oauth_login(proveedor: str):
    info = cfg.PROVEEDORES.get(proveedor)
    if not info or not info.get("oauth_disponible"):
        return {"error": "OAuth no disponible para este proveedor"}
    params = (
        f"response_type=token"
        f"&client_id={_OAUTH_CLIENT_ID}"
        f"&redirect_uri=http://127.0.0.1:{PUERTO}/api/oauth/callback"
        f"&scope=openid"
    )
    return RedirectResponse(f"{info['oauth_url']}?{params}")


@app.get("/api/oauth/callback")
def oauth_callback():
    return HTMLResponse("""<!DOCTYPE html>
<html>
<body>
<script>
(async()=>{
  const h = new URLSearchParams(window.location.hash.slice(1));
  const token = h.get('access_token');
  if (token) {
    await fetch('/api/oauth/save', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({token})
    });
    document.body.innerHTML = '<p style="font:16px sans-serif;text-align:center;margin-top:40px">'
      + '\\u2705 Token guardado correctamente.</p>';
  } else {
    document.body.innerHTML = '<p style="font:16px sans-serif;text-align:center;margin-top:40px;color:#d33">'
      + '\\u2716 No se recibi\\u00f3 ning\\u00fan token.</p>';
  }
  setTimeout(window.close, 2000);
})();
</script>
</body>
</html>""")


@app.post("/api/oauth/save")
async def oauth_save(peticion: Request):
    datos = await peticion.json()
    token = (datos.get("token") or "").strip()
    if not token:
        return {"ok": False, "error": "Token vacío"}
    config = cfg.cargar()
    for prov, info in cfg.PROVEEDORES.items():
        if info.get("oauth_disponible"):
            config["claves"][prov] = token
            break
    cfg.guardar(config)
    return {"ok": True}


@app.post("/api/conectar/{programa_id}")
def conectar(programa_id: str):
    resultado = instalador.instalar(programa_id)
    conector = next((c for c in CONECTORES if c.id == programa_id), None)
    resultado["conectado"] = bool(conector and conector.disponible())
    return resultado


@app.get("/api/modelos/{proveedor}")
def modelos_de(proveedor: str):
    return catalogo_modelos.listar(proveedor)


@app.get("/api/skills")
def skills():
    return conocimiento.recetas_boton()


@app.post("/api/conocimiento")
async def guardar_conocimiento(peticion: Request):
    datos = await peticion.json()
    resultado = conocimiento.guardar_receta(datos)
    return resultado


@app.post("/api/reiniciar")
def reiniciar():
    # Vaciar el historial con el agente en marcha rompería el emparejado
    # herramienta/resultado que exigen las APIs de los proveedores
    global _sesion_id
    if _ocupado.locked():
        return {"ok": False, "error": "Espera a que el asistente termine (o pulsa Detener) antes de empezar una conversación nueva."}
    _historial.clear()
    _sesion_id = sesiones.nuevo_id()
    return {"ok": True}


@app.get("/api/sesiones")
def listar_sesiones():
    return {"actual": _sesion_id, "sesiones": sesiones.listar()}


@app.post("/api/sesiones/{sesion_id}/abrir")
def abrir_sesion(sesion_id: str):
    global _sesion_id
    if _ocupado.locked():
        return {"ok": False, "error": "Espera a que el asistente termine (o pulsa Detener) antes de cambiar de conversación."}
    historial = sesiones.cargar(sesion_id)
    if historial is None:
        return {"ok": False, "error": "Esa conversación ya no existe."}
    _historial.clear()
    _historial.extend(historial)
    _sesion_id = sesion_id
    return {"ok": True, "mensajes": sesiones.para_ui(historial)}


@app.delete("/api/sesiones/{sesion_id}")
def borrar_sesion(sesion_id: str):
    global _sesion_id
    if _ocupado.locked() and sesion_id == _sesion_id:
        return {"ok": False, "error": "No puedo borrar la conversación mientras el asistente trabaja en ella."}
    sesiones.borrar(sesion_id)
    if sesion_id == _sesion_id:
        _historial.clear()
        _sesion_id = sesiones.nuevo_id()
    return {"ok": True}


@app.post("/api/cancelar")
def cancelar():
    if _ocupado.locked():
        _cancelar.set()
    return {"ok": True}


# Límites de adjuntos: la interfaz ya reduce las imágenes, pero validamos aquí
# para no aceptar payloads gigantes ni tipos no soportados por los modelos.
_MAX_ADJUNTOS = 12
_MAX_BYTES_ADJUNTO = 8 * 1024 * 1024  # ~8 MB por imagen ya en base64


def _sanear_origen(origen):
    """Metadatos de un plano importado (PDF o DXF), o None si no son válidos.

    El `id` apunta a un archivo de ~/.buildai/planos/: solo se acepta con el
    formato exacto que genera el importador, así el navegador no puede hacer
    que una herramienta lea otra ruta del disco.
    """
    if not isinstance(origen, dict) or origen.get("tipo") not in ("pdf", "dxf"):
        return None
    if importar_planos.ruta_guardada(origen.get("id"), "png" if origen["tipo"] == "pdf" else "dxf") is None:
        return None
    limpio = {"tipo": origen["tipo"], "id": origen["id"], "nombre": str(origen.get("nombre") or "plano")[:120]}
    if origen["tipo"] == "pdf":
        try:
            limpio["pagina"] = int(origen.get("pagina") or 1)
            limpio["paginas"] = int(origen.get("paginas") or 1)
            escala = float(origen.get("escala_vista") or 1.0)
        except (TypeError, ValueError):
            return None
        limpio["escala_vista"] = escala if 0 < escala <= 1 else 1.0
    return limpio


def _sanear_adjuntos(bruto) -> list:
    """Filtra la lista de adjuntos recibida: solo imágenes con base64 válido."""
    import base64

    limpios = []
    for a in (bruto or []):
        if len(limpios) >= _MAX_ADJUNTOS:
            break
        if not isinstance(a, dict):
            continue
        media = str(a.get("media_type") or "").lower()
        datos = a.get("datos")
        if not media.startswith("image/") or not isinstance(datos, str) or not datos:
            continue
        if len(datos) > _MAX_BYTES_ADJUNTO:
            continue
        try:
            base64.b64decode(datos, validate=True)
        except Exception:
            continue
        adjunto = {"media_type": media, "datos": datos}
        origen = _sanear_origen(a.get("origen"))
        if origen:
            adjunto["origen"] = origen
        limpios.append(adjunto)
    return limpios


# Un DXF de un proyecto completo pesa decenas de MB; el PDF de un plano, menos.
_MAX_BYTES_PLANO = 40 * 1024 * 1024


@app.post("/api/planos/importar")
async def importar_plano(peticion: Request):
    """Convierte un PDF o DXF en adjuntos de imagen (con su original guardado)."""
    import base64

    datos = await peticion.json()
    nombre = str(datos.get("nombre") or "plano")[:120]
    contenido = datos.get("datos")
    if not isinstance(contenido, str) or not contenido or len(contenido) > _MAX_BYTES_PLANO:
        return {"ok": False, "error": "El archivo está vacío o supera los 30 MB."}
    try:
        crudo = base64.b64decode(contenido, validate=True)
    except Exception:
        return {"ok": False, "error": "El archivo no llegó bien (base64 inválido)."}
    extension = nombre.rsplit(".", 1)[-1].lower() if "." in nombre else ""
    try:
        if extension == "pdf" or crudo[:5] == b"%PDF-":
            adjuntos = await asyncio.to_thread(importar_planos.importar_pdf, crudo, nombre)
        elif extension == "dxf":
            adjuntos = await asyncio.to_thread(importar_planos.importar_dxf, crudo, nombre)
        else:
            return {"ok": False, "error": "Solo se pueden importar planos PDF o DXF (los DWG, ábrelos en AutoCAD)."}
    except importar_planos.ErrorImportacion as exc:
        return {"ok": False, "error": str(exc)}
    except Exception as exc:  # un archivo raro no debe tumbar el servidor
        return {"ok": False, "error": f"No pude leer «{nombre}»: {exc}"}
    return {
        "ok": True,
        "adjuntos": [
            {"media_type": a["media_type"], "datos": base64.b64encode(a["datos"]).decode("ascii"), "origen": a["origen"]}
            for a in adjuntos
        ],
    }


@app.post("/api/chat")
async def chat(peticion: Request):
    datos = await peticion.json()
    mensaje = (datos.get("mensaje") or "").strip()
    adjuntos = _sanear_adjuntos(datos.get("adjuntos"))

    async def flujo():
        if not mensaje and not adjuntos:
            yield _sse({"tipo": "error", "texto": "Escribe un mensaje o adjunta una imagen primero."})
            return
        if not _ocupado.acquire(blocking=False):
            yield _sse({"tipo": "error", "texto": "El asistente ya está trabajando en otra tarea. Espera a que termine."})
            return
        _cancelar.clear()
        cola: queue.Queue = queue.Queue()
        FIN = object()

        def trabajo():
            try:
                ejecutar_turno(_historial, mensaje, cola.put, cancelado=_cancelar.is_set, adjuntos=adjuntos)
            except Exception as exc:
                # Sin esto un fallo inesperado deja la interfaz esperando en
                # silencio: el turno acaba sin respuesta ni error que mostrar.
                cola.put({"tipo": "error", "texto": f"Error inesperado al procesar el mensaje: {exc}"})
            finally:
                try:
                    sesiones.guardar(_sesion_id, _historial)
                except Exception:
                    pass  # no perder la respuesta por un fallo de disco
                cola.put(FIN)
                _ocupado.release()

        threading.Thread(target=trabajo, daemon=True).start()
        while True:
            try:
                evento = cola.get_nowait()
            except queue.Empty:
                await asyncio.sleep(0.1)
                continue
            if evento is FIN:
                yield _sse({"tipo": "fin"})
                return
            yield _sse(evento)

    return StreamingResponse(flujo(), media_type="text/event-stream")


def _sse(evento: dict) -> str:
    return f"data: {json.dumps(evento, ensure_ascii=False)}\n\n"


app.mount("/ui", StaticFiles(directory=CARPETA_UI), name="ui")


def _esperar_servidor(timeout: float = 15.0) -> bool:
    """Espera a que uvicorn responda antes de abrir la ventana, para no mostrar
    una pantalla en blanco mientras arranca."""
    limite = time.monotonic() + timeout
    url = f"http://127.0.0.1:{PUERTO}"
    while time.monotonic() < limite:
        try:
            urllib.request.urlopen(url, timeout=0.5)
            return True
        except Exception:
            time.sleep(0.2)
    return False


def arrancar():
    aviso = instalador.aviso_instalacion_arriesgada()
    if aviso:
        print()
        print("  [AVISO] " + aviso.replace("\n", "\n          "))

    hilo_servidor = threading.Thread(
        target=lambda: uvicorn.run(app, host="127.0.0.1", port=PUERTO, log_level="warning"),
        daemon=True,
    )
    hilo_servidor.start()
    _esperar_servidor()
    # La IA incluida se prepara en segundo plano desde el primer segundo:
    # descarga el modelo si hace falta y arranca el motor mientras la ventana abre.
    if cfg.cargar()["proveedor"] == "local":
        ia_local.preparar_en_segundo_plano()

    try:
        import webview
    except ImportError:
        # Sin pywebview instalado (p. ej. entorno de desarrollo mínimo):
        # el navegador es la vía de emergencia, no la experiencia normal.
        print()
        print("  BuildAI esta en marcha (sin ventana nativa: falta pywebview)")
        print(f"  Abre en tu navegador:  http://127.0.0.1:{PUERTO}")
        print()
        webbrowser.open(f"http://127.0.0.1:{PUERTO}")
        hilo_servidor.join()
        return

    icono = CARPETA_UI / "assets" / "buildai.ico"
    webview.create_window(
        "BuildAI",
        f"http://127.0.0.1:{PUERTO}",
        width=1280,
        height=820,
        min_size=(960, 640),
    )
    webview.start(icon=str(icono) if icono.exists() else None)


if __name__ == "__main__":
    arrancar()
