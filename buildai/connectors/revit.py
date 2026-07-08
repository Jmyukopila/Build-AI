"""Conector con Revit a través de la extensión BuildAI para pyRevit (Routes API)."""

from pathlib import Path

import httpx

from .base import Conector, recortar

PUERTO_REVIT = 48884  # puerto por defecto del servidor Routes de pyRevit
BASE = f"http://127.0.0.1:{PUERTO_REVIT}/buildai"

# Kit BIM en metros: se antepone a cada ejecución para que el modelo no tenga
# que pelearse con los pies ni con la búsqueda de tipos/familias de la API.
# La cabecera de codificación se retira: IronPython 2 rechaza un exec() de
# texto unicode que contenga una declaración de coding.
KIT_FUENTE = (
    (Path(__file__).parent / "revit_kit.py")
    .read_text(encoding="utf-8")
    .replace("# -*- coding: utf-8 -*-\n", "", 1)
)


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
                    "Ejecuta código Python dentro de Revit vía pyRevit (motor IronPython "
                    "o CPython: escribe Python 2/3 compatible, sin f-strings). Variables "
                    "disponibles: `doc`, `uidoc`, `DB` (Autodesk.Revit.DB) y `salida` "
                    "(lista: salida.append(...) devuelve texto; el KIT ya imprime solo). "
                    "Ya hay una transacción abierta; no crees transacciones propias.\n\n"
                    "Antes de tu código se carga un KIT BIM con funciones EN METROS que "
                    "localizan solas los tipos/familias cargados (úsalo SIEMPRE en vez de "
                    "la API cruda, que trabaja en pies):\n"
                    "- niveles() — lista niveles con su cota en m. nivel(altura, nombre=None) "
                    "— devuelve el nivel en esa cota o lo crea (llámalo antes de cada planta).\n"
                    "- muro(inicio, fin, nivel_base, altura=2.7, tipo=None) — muro nativo entre "
                    "dos puntos (x, y) en m; DEVUELVE el muro: guárdalo en una variable para "
                    "insertarle huecos.\n"
                    "- suelo(contorno, nivel_base) — forjado con planta poligonal [(x, y), …].\n"
                    "- puerta(muro_obj, a, nivel_base, tipo=None) y "
                    "ventana(muro_obj, a, nivel_base, antepecho=0.9, tipo=None) — se insertan "
                    "en el muro a `a` metros de su arranque; `tipo` filtra por nombre.\n"
                    "- familias(categoria) — lista lo cargado: 'puertas', 'ventanas', "
                    "'mobiliario', 'pilares', 'luminarias', 'aparatos'. Consúltala antes de "
                    "colocar; si no hay familia adecuada, díselo al usuario y usa la más "
                    "parecida (no la inventes).\n"
                    "- colocar(categoria, posicion, nivel_base, rotacion=0, tipo=None) — "
                    "mobiliario/luminarias/aparatos en (x, y) m. pilar(posicion, nivel_base).\n"
                    "- xyz(x, y, z=0) convierte metros a DB.XYZ y borrar(elemento) elimina "
                    "(solo con permiso del usuario).\n"
                    "Para lo que el kit no cubre (cubiertas, habitaciones, vistas, "
                    "parámetros…), usa `DB` directamente recordando que la API trabaja en "
                    "PIES: pies = metros × 3.28084. Construye siempre con elementos "
                    "nativos BIM, nunca geometría suelta."
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
                # El código del modelo se compila aparte con nombre '<codigo>' para
                # que los números de línea de un error apunten a SU código, no al kit.
                codigo = (
                    KIT_FUENTE
                    + "\n_buildai_codigo = " + repr(argumentos.get("codigo", ""))
                    + "\nexec(compile(_buildai_codigo, '<codigo>', 'exec'), globals())\n"
                )
                r = httpx.post(
                    f"{BASE}/ejecutar",
                    json={"codigo": codigo},
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
