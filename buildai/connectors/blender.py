"""Conector con Blender a través del add-on BuildAI (socket TCP local)."""

import json
import socket

from .base import Conector, recortar

PUERTO_BLENDER = 8601


def _enviar(peticion: dict, timeout: float = 60.0) -> dict:
    with socket.create_connection(("127.0.0.1", PUERTO_BLENDER), timeout=timeout) as s:
        s.sendall((json.dumps(peticion) + "\n").encode("utf-8"))
        datos = b""
        while not datos.endswith(b"\n"):
            trozo = s.recv(65536)
            if not trozo:
                break
            datos += trozo
    return json.loads(datos.decode("utf-8"))


class ConectorBlender(Conector):
    id = "blender"
    nombre = "Blender"
    icono = "blender"
    ayuda = (
        "1. Pulsa «Conectar automáticamente» aquí abajo: BuildAI instala el "
        "puente en todas tus versiones de Blender (2.80 o superior).\n"
        "2. Abre (o reinicia) Blender. No hay que activar nada: el puente "
        "arranca solo y el punto se pondrá verde en unos segundos.\n"
        "\n"
        "Manual (alternativa): Edit → Preferences → Add-ons → Install… → elige "
        "addons\\blender\\buildai_blender.py y activa la casilla 'BuildAI Bridge'."
    )

    def disponible(self) -> bool:
        try:
            return _enviar({"comando": "ping"}, timeout=2.0).get("ok", False)
        except (OSError, ValueError):
            return False

    def herramientas(self) -> list:
        return [
            {
                "nombre": "blender_informacion",
                "descripcion": (
                    "Devuelve un resumen de la escena actual de Blender: objetos, "
                    "colecciones, cámaras y luces. Úsala antes de modificar nada."
                ),
                "parametros": {"type": "object", "properties": {}, "required": []},
            },
            {
                "nombre": "blender_ejecutar_python",
                "descripcion": (
                    "Ejecuta código Python dentro de Blender con el módulo `bpy` "
                    "disponible. Úsala para crear o modificar geometría, materiales, "
                    "luces, cámaras, etc. Haz cambios en pasos pequeños y usa print() "
                    "para devolver información."
                ),
                "parametros": {
                    "type": "object",
                    "properties": {
                        "codigo": {
                            "type": "string",
                            "description": "Código Python a ejecutar en Blender (bpy disponible).",
                        }
                    },
                    "required": ["codigo"],
                },
            },
        ]

    def ejecutar(self, nombre: str, argumentos: dict) -> str:
        try:
            if nombre == "blender_informacion":
                r = _enviar({"comando": "info"})
            else:
                r = _enviar({"comando": "ejecutar", "codigo": argumentos.get("codigo", "")}, timeout=120.0)
        except OSError as exc:
            return f"ERROR: no se pudo hablar con Blender ({exc}). ¿Está abierto con el add-on activado?"
        if not r.get("ok"):
            return f"ERROR en Blender: {recortar(r.get('error', 'desconocido'))}"
        return recortar(r.get("resultado", "(sin salida)"))
