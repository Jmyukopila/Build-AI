# -*- coding: utf-8 -*-
"""BuildAI Bridge para Revit (extensión de pyRevit).

Define rutas HTTP (pyRevit Routes) para que BuildAI pueda consultar el
documento activo y ejecutar código Python dentro de Revit.

Compatible con Revit 2014+ (el fallback de recuento cubre versiones sin
GetElementCount) y con pyRevit 4.8 o superior (que trae el módulo routes),
tanto con motor IronPython como CPython.

Requisitos (el instalador de BuildAI hace los pasos 2 y 3 automáticamente):
  1. pyRevit instalado (github.com/pyrevitlabs/pyRevit).
  2. Esta carpeta (BuildAI.extension) copiada en %APPDATA%\\pyRevit\\Extensions.
  3. Servidor Routes activado ([routes] enabled = true en pyRevit_config.ini).
"""

import traceback

try:
    from pyrevit import routes
except ImportError:
    routes = None
    print("[BuildAI] Esta version de pyRevit no incluye el modulo 'routes'. "
          "Actualiza pyRevit a la 4.8 o superior para usar BuildAI.")

from pyrevit import revit, DB


def _contar(coleccion):
    """Recuento compatible: GetElementCount existe desde Revit 2016."""
    try:
        return coleccion.GetElementCount()
    except AttributeError:
        return len(list(coleccion))


if routes:
    api = routes.API("buildai")

    @api.route("/ping", methods=["GET"])
    def ping(request):
        return {"ok": True, "resultado": "pong"}

    @api.route("/info", methods=["GET"])
    def info(request):
        try:
            doc = revit.doc
            if doc is None:
                return {"ok": False, "error": "No hay ningún documento abierto en Revit."}
            lineas = []
            try:
                lineas.append("Revit {}".format(doc.Application.VersionNumber))
            except Exception:
                pass
            lineas.append("Documento: {}".format(doc.Title))

            niveles = DB.FilteredElementCollector(doc)\
                .OfClass(DB.Level).ToElements()
            lineas.append("Niveles: " + ", ".join(sorted(n.Name for n in niveles)))

            categorias = [
                ("Muros", DB.BuiltInCategory.OST_Walls),
                ("Puertas", DB.BuiltInCategory.OST_Doors),
                ("Ventanas", DB.BuiltInCategory.OST_Windows),
                ("Suelos", DB.BuiltInCategory.OST_Floors),
                ("Cubiertas", DB.BuiltInCategory.OST_Roofs),
                ("Habitaciones", DB.BuiltInCategory.OST_Rooms),
            ]
            for nombre, cat in categorias:
                cuenta = _contar(
                    DB.FilteredElementCollector(doc)
                    .OfCategory(cat).WhereElementIsNotElementType()
                )
                lineas.append("{}: {}".format(nombre, cuenta))
            return {"ok": True, "resultado": "\n".join(lineas)}
        except Exception:
            return {"ok": False, "error": traceback.format_exc()}

    @api.route("/ejecutar", methods=["POST"])
    def ejecutar(request):
        try:
            datos = request.data or {}
            codigo = datos.get("codigo", "")
            doc = revit.doc
            if doc is None:
                return {"ok": False, "error": "No hay ningún documento abierto en Revit."}

            salida = []
            entorno = {
                "doc": doc,
                "uidoc": revit.uidoc,
                "DB": DB,
                "revit": revit,
                "salida": salida,
            }
            # Transacción abierta para que el código pueda modificar el modelo
            with revit.Transaction("BuildAI"):
                exec(codigo, entorno)
            texto = "\n".join(str(x) for x in salida)
            return {"ok": True, "resultado": texto or "Código ejecutado correctamente (sin salida)."}
        except Exception:
            return {"ok": False, "error": traceback.format_exc()}
