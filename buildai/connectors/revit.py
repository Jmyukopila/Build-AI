"""Conector con Revit a través de la extensión BuildAI para pyRevit (Routes API)."""

import httpx

from .base import Conector, recortar

PUERTO_REVIT = 48884  # puerto por defecto del servidor Routes de pyRevit
BASE = f"http://127.0.0.1:{PUERTO_REVIT}/buildai"


class ConectorRevit(Conector):
    id = "revit"
    nombre = "Revit"
    icono = "revit"
    ayuda = (
        "Revit necesita pyRevit (gratuito, compatible con Revit 2014+):\n"
        "1. Si no tienes pyRevit, instálalo desde "
        "github.com/pyrevitlabs/pyRevit/releases (siguiente → siguiente).\n"
        "2. Pulsa «Conectar automáticamente» aquí abajo: BuildAI instala la "
        "extensión y activa el servidor Routes por ti.\n"
        "3. Abre (o reinicia) Revit con un proyecto: el punto se pondrá verde solo."
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
                "nombre": "revit_informacion",
                "descripcion": (
                    "Devuelve información del documento activo de Revit: nombre, "
                    "niveles y recuento de elementos por categoría principal."
                ),
                "parametros": {"type": "object", "properties": {}, "required": []},
            },
            {
                "nombre": "revit_ejecutar_python",
                "descripcion": (
                    "Ejecuta código Python (IronPython) dentro de Revit vía pyRevit. "
                    "Variables disponibles: `doc` (documento activo), `uidoc`, `DB` "
                    "(Autodesk.Revit.DB) y `salida` (lista: añade con salida.append(...) "
                    "lo que quieras devolver). Las modificaciones ya se ejecutan dentro "
                    "de una transacción abierta; no crees transacciones propias."
                ),
                "parametros": {
                    "type": "object",
                    "properties": {
                        "codigo": {
                            "type": "string",
                            "description": "Código Python a ejecutar en Revit.",
                        }
                    },
                    "required": ["codigo"],
                },
            },
        ]

    def ejecutar(self, nombre: str, argumentos: dict) -> str:
        try:
            if nombre == "revit_informacion":
                r = httpx.get(f"{BASE}/info", timeout=60.0)
            else:
                r = httpx.post(
                    f"{BASE}/ejecutar",
                    json={"codigo": argumentos.get("codigo", "")},
                    timeout=180.0,
                )
        except httpx.HTTPError as exc:
            return (
                f"ERROR: no se pudo hablar con Revit ({exc}). "
                "¿Está abierto con pyRevit y el servidor Routes activado?"
            )
        try:
            datos = r.json()
        except ValueError:
            return f"ERROR: respuesta inesperada de Revit: {recortar(r.text)}"
        if not datos.get("ok"):
            return f"ERROR en Revit: {recortar(datos.get('error', 'desconocido'))}"
        return recortar(datos.get("resultado", "(sin salida)"))
