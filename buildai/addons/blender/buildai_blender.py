"""BuildAI Bridge para Blender.

Add-on que abre un pequeño servidor local (puerto 8601) para que BuildAI
pueda consultar la escena y ejecutar código Python dentro de Blender.
Solo acepta conexiones desde este mismo ordenador (127.0.0.1).

Compatible con Blender 2.80 en adelante (incluidas las series 3.x y 4.x).

Instalación automática: BuildAI copia este archivo a scripts\\startup del
perfil de Blender, donde se ejecuta solo al arrancar (sin activar nada).
Instalación manual: Edit → Preferences → Add-ons → Install… → elegir este
archivo y activar la casilla "BuildAI Bridge".
"""

bl_info = {
    "name": "BuildAI Bridge",
    "author": "BuildAI",
    "version": (1, 1, 0),
    "blender": (2, 80, 0),
    "location": "Se ejecuta en segundo plano",
    "description": "Permite que BuildAI controle Blender desde la app local",
    "category": "System",
}

import contextlib
import io
import json
import os
import queue
import socket
import threading
import traceback

import bpy

PUERTO = 8601

_trabajos = queue.Queue()   # (peticion: dict, respuesta: dict, listo: threading.Event)
_servidor = None
_detener = threading.Event()


def _info_escena() -> str:
    escena = bpy.context.scene
    lineas = [
        f"Blender {bpy.app.version_string}",
        f"Escena: {escena.name}",
        f"Objetos: {len(escena.objects)}",
    ]
    for obj in list(escena.objects)[:120]:
        pos = ", ".join(f"{v:.2f}" for v in obj.location)
        lineas.append(f"  - {obj.name} ({obj.type}) en ({pos})")
    if len(escena.objects) > 120:
        lineas.append(f"  … y {len(escena.objects) - 120} objetos más")
    lineas.append(f"Colecciones: {', '.join(c.name for c in bpy.data.collections) or '(ninguna)'}")
    return "\n".join(lineas)


def _procesar(peticion: dict) -> dict:
    """Se ejecuta SIEMPRE en el hilo principal de Blender."""
    comando = peticion.get("comando")
    if comando == "ping":
        return {"ok": True, "resultado": "pong"}
    if comando == "info":
        return {"ok": True, "resultado": _info_escena()}
    if comando == "ejecutar":
        salida = io.StringIO()
        try:
            with contextlib.redirect_stdout(salida):
                exec(peticion.get("codigo", ""), {"bpy": bpy})
            return {"ok": True, "resultado": salida.getvalue() or "Código ejecutado (sin salida)."}
        except Exception:
            return {"ok": False, "error": traceback.format_exc(limit=6) + "\nSalida previa:\n" + salida.getvalue()}
    return {"ok": False, "error": f"Comando desconocido: {comando}"}


def _bombear_trabajos():
    """Timer de Blender: ejecuta los trabajos pendientes en el hilo principal."""
    while True:
        try:
            peticion, respuesta, listo = _trabajos.get_nowait()
        except queue.Empty:
            break
        try:
            respuesta.update(_procesar(peticion))
        except Exception:
            respuesta.update({"ok": False, "error": traceback.format_exc(limit=4)})
        finally:
            listo.set()
    return 0.15 if not _detener.is_set() else None


def _atender_cliente(conexion: socket.socket):
    try:
        conexion.settimeout(130.0)
        datos = b""
        while not datos.endswith(b"\n"):
            trozo = conexion.recv(65536)
            if not trozo:
                return
            datos += trozo
        peticion = json.loads(datos.decode("utf-8"))
        respuesta: dict = {}
        listo = threading.Event()
        _trabajos.put((peticion, respuesta, listo))
        if not listo.wait(timeout=125.0):
            respuesta = {"ok": False, "error": "Tiempo de espera agotado en Blender."}
        conexion.sendall((json.dumps(respuesta) + "\n").encode("utf-8"))
    except Exception:
        with contextlib.suppress(Exception):
            conexion.sendall(
                (json.dumps({"ok": False, "error": traceback.format_exc(limit=3)}) + "\n").encode("utf-8")
            )
    finally:
        with contextlib.suppress(Exception):
            conexion.close()


def _bucle_servidor(servidor: socket.socket):
    while not _detener.is_set():
        try:
            conexion, _ = servidor.accept()
        except OSError:
            break
        threading.Thread(target=_atender_cliente, args=(conexion,), daemon=True).start()


def register():
    global _servidor
    if _servidor is not None:
        # Ya registrado (p. ej. instalado a la vez como script de inicio y add-on)
        return
    _detener.clear()
    servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    if os.name != "nt":
        # En Windows, SO_REUSEADDR permitiría dos servidores en el mismo puerto
        servidor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        servidor.bind(("127.0.0.1", PUERTO))
    except OSError:
        with contextlib.suppress(Exception):
            servidor.close()
        print(f"[BuildAI] El puerto {PUERTO} ya está en uso (¿otro Blender abierto?). "
              "Este Blender no atenderá a BuildAI.")
        return
    servidor.listen(4)
    _servidor = servidor
    threading.Thread(target=_bucle_servidor, args=(servidor,), daemon=True).start()
    bpy.app.timers.register(_bombear_trabajos, persistent=True)
    print(f"[BuildAI] Servidor escuchando en 127.0.0.1:{PUERTO}")


def unregister():
    _detener.set()
    global _servidor
    if _servidor is not None:
        with contextlib.suppress(Exception):
            _servidor.close()
        _servidor = None
    print("[BuildAI] Servidor detenido")


if __name__ == "__main__":
    register()
