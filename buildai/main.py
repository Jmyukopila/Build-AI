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
from . import sesiones
from .agent import CARPETA_RENDERS, ejecutar_turno
from .connectors import CONECTORES
from .skills import cargar_skills

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
    if (
        "/" in nombre or "\\" in nombre or nombre.startswith(".")
        or ruta.suffix.lower() != ".png" or not ruta.is_file()
    ):
        return Response(status_code=404)
    return FileResponse(ruta, media_type="image/png")


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
    }


@app.get("/api/config")
def leer_config():
    configuracion = cfg.cargar()
    # No devolvemos las claves completas, solo si existen
    return {
        "proveedor": configuracion["proveedor"],
        "modelos": configuracion["modelos"],
        "claves_configuradas": {k: bool(v) for k, v in configuracion["claves"].items()},
        "proveedores": cfg.PROVEEDORES,
        "modelos_por_defecto": cfg.MODELOS_POR_DEFECTO,
    }


@app.post("/api/config")
async def guardar_config(peticion: Request):
    datos = await peticion.json()
    configuracion = cfg.cargar()
    if datos.get("proveedor") in cfg.PROVEEDORES:
        configuracion["proveedor"] = datos["proveedor"]
    for nombre, clave in (datos.get("claves") or {}).items():
        if nombre in configuracion["claves"] and clave:  # vacío = no cambiar
            configuracion["claves"][nombre] = clave.strip()
    for nombre, modelo in (datos.get("modelos") or {}).items():
        if nombre in configuracion["modelos"] and modelo:
            configuracion["modelos"][nombre] = modelo.strip()
    cfg.guardar(configuracion)
    return {"ok": True}


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
    return cargar_skills()


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


@app.post("/api/chat")
async def chat(peticion: Request):
    datos = await peticion.json()
    mensaje = (datos.get("mensaje") or "").strip()

    async def flujo():
        if not mensaje:
            yield _sse({"tipo": "error", "texto": "Escribe un mensaje primero."})
            return
        if not _ocupado.acquire(blocking=False):
            yield _sse({"tipo": "error", "texto": "El asistente ya está trabajando en otra tarea. Espera a que termine."})
            return
        _cancelar.clear()
        cola: queue.Queue = queue.Queue()
        FIN = object()

        def trabajo():
            try:
                ejecutar_turno(_historial, mensaje, cola.put, cancelado=_cancelar.is_set)
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
