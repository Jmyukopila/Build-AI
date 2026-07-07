"""Conector con SketchUp a través de la extensión BuildAI (HTTP local)."""

import httpx

from .base import Conector, recortar

PUERTO_SKETCHUP = 8602
BASE = f"http://127.0.0.1:{PUERTO_SKETCHUP}"


class ConectorSketchUp(Conector):
    id = "sketchup"
    nombre = "SketchUp"
    icono = "sketchup"
    ayuda = (
        "1. Pulsa «Conectar automáticamente» aquí abajo: BuildAI instala la "
        "extensión en todas tus versiones de SketchUp (2014 o superior).\n"
        "2. Abre (o reinicia) SketchUp. La extensión se inicia sola y el punto "
        "se pondrá verde en unos segundos.\n"
        "\n"
        "Manual (alternativa): copia addons\\sketchup\\buildai_sketchup.rb a la "
        "carpeta Plugins de SketchUp (%APPDATA%\\SketchUp\\SketchUp 20XX\\"
        "SketchUp\\Plugins) y reinicia SketchUp."
    )

    def disponible(self) -> bool:
        try:
            r = httpx.get(f"{BASE}/ping", timeout=2.0)
            return r.status_code == 200
        except httpx.HTTPError:
            return False

    def herramientas(self) -> list:
        return [
            {
                "nombre": "sketchup_informacion",
                "descripcion": (
                    "Devuelve un resumen del modelo actual de SketchUp: nombre, "
                    "entidades, componentes, materiales y capas/etiquetas."
                ),
                "parametros": {"type": "object", "properties": {}, "required": []},
            },
            {
                "nombre": "sketchup_ejecutar_ruby",
                "descripcion": (
                    "Ejecuta código Ruby dentro de SketchUp usando su API "
                    "(Sketchup.active_model, etc.). Úsala para crear o modificar "
                    "geometría, grupos, componentes y materiales. El valor de la "
                    "última expresión (o lo impreso con puts) se devuelve como texto."
                ),
                "parametros": {
                    "type": "object",
                    "properties": {
                        "codigo": {
                            "type": "string",
                            "description": "Código Ruby a ejecutar en SketchUp.",
                        }
                    },
                    "required": ["codigo"],
                },
            },
        ]

    def ejecutar(self, nombre: str, argumentos: dict) -> str:
        try:
            if nombre == "sketchup_informacion":
                r = httpx.get(f"{BASE}/info", timeout=30.0)
            else:
                r = httpx.post(
                    f"{BASE}/ejecutar",
                    json={"codigo": argumentos.get("codigo", "")},
                    timeout=120.0,
                )
        except httpx.HTTPError as exc:
            return (
                f"ERROR: no se pudo hablar con SketchUp ({exc}). "
                "¿Está abierto con la extensión BuildAI iniciada?"
            )
        datos = r.json()
        if not datos.get("ok"):
            return f"ERROR en SketchUp: {recortar(datos.get('error', 'desconocido'))}"
        return recortar(datos.get("resultado", "(sin salida)"))
