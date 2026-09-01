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

import os
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
            lineas.append("Niveles: " + ", ".join(
                "{} ({:.2f} m)".format(n.Name, n.Elevation * 0.3048)
                for n in sorted(niveles, key=lambda n: n.Elevation)))

            categorias = [
                ("Muros", DB.BuiltInCategory.OST_Walls),
                ("Puertas", DB.BuiltInCategory.OST_Doors),
                ("Ventanas", DB.BuiltInCategory.OST_Windows),
                ("Suelos", DB.BuiltInCategory.OST_Floors),
                ("Cubiertas", DB.BuiltInCategory.OST_Roofs),
                ("Habitaciones", DB.BuiltInCategory.OST_Rooms),
                ("Mobiliario", DB.BuiltInCategory.OST_Furniture),
                ("Luminarias", DB.BuiltInCategory.OST_LightingFixtures),
            ]
            for nombre, cat in categorias:
                cuenta = _contar(
                    DB.FilteredElementCollector(doc)
                    .OfCategory(cat).WhereElementIsNotElementType()
                )
                lineas.append("{}: {}".format(nombre, cuenta))

            # Tipos y familias disponibles: el agente los necesita para elegir
            # bien sin inventar nombres (se listan los primeros de cada grupo).
            try:
                tipos_muro = [
                    DB.Element.Name.GetValue(t) for t in
                    DB.FilteredElementCollector(doc).OfClass(DB.WallType)
                ]
                lineas.append("Tipos de muro ({}): {}".format(
                    len(tipos_muro), ", ".join(tipos_muro[:8]) or "(ninguno)"))
                for etiqueta, cat in (("Familias de puertas", DB.BuiltInCategory.OST_Doors),
                                      ("Familias de ventanas", DB.BuiltInCategory.OST_Windows),
                                      ("Familias de mobiliario", DB.BuiltInCategory.OST_Furniture)):
                    simbolos = list(
                        DB.FilteredElementCollector(doc)
                        .OfClass(DB.FamilySymbol).OfCategory(cat)
                    )
                    nombres = sorted(set(s.Family.Name for s in simbolos))
                    lineas.append("{} ({}): {}".format(
                        etiqueta, len(nombres), ", ".join(nombres[:6]) or "(ninguna)"))
            except Exception:
                pass
            return {"ok": True, "resultado": "\n".join(lineas)}
        except Exception:
            return {"ok": False, "error": traceback.format_exc()}

    def _vistas_para_exportar(doc):
        """Vistas que se pueden imprimir/exportar: la activa si sirve, y si no
        todas las hojas del proyecto (que es lo que se entrega en un plano)."""
        from System.Collections.Generic import List
        ids = List[DB.ElementId]()
        activa = doc.ActiveView
        if activa is not None and not activa.IsTemplate and activa.CanBePrinted:
            ids.Add(activa.Id)
            return ids
        hojas = DB.FilteredElementCollector(doc)\
            .OfClass(DB.ViewSheet).WhereElementIsNotElementType().ToElements()
        for hoja in hojas:
            ids.Add(hoja.Id)
        return ids

    @api.route("/exportar", methods=["POST"])
    def exportar(request):
        """Exporta el modelo a IFC, DWG, DXF o PDF.

        Va en su propia ruta porque Revit PROHIBE Document.Export dentro de una
        transacción, y /ejecutar abre una siempre.
        """
        try:
            datos = request.data or {}
            formato = str(datos.get("formato", "")).lower()
            carpeta = datos.get("carpeta")
            nombre = datos.get("nombre")
            doc = revit.doc
            if doc is None:
                return {"ok": False, "error": "No hay ningún documento abierto en Revit."}
            if not carpeta or not nombre:
                return {"ok": False, "error": "Faltan la carpeta o el nombre de destino."}

            # Revit decide el nombre final (a veces le añade el de la vista), así
            # que en vez de suponerlo se mira qué archivos aparecen en la carpeta.
            antes = set(os.listdir(carpeta))

            if formato == "ifc":
                opciones = DB.IFCExportOptions()
                if str(datos.get("version", "2x3")) == "4":
                    opciones.FileVersion = DB.IFCVersion.IFC4
                else:
                    opciones.FileVersion = DB.IFCVersion.IFC2x3CV2
                doc.Export(carpeta, nombre, opciones)
            elif formato in ("dwg", "dxf"):
                vistas = _vistas_para_exportar(doc)
                if vistas.Count == 0:
                    return {"ok": False, "error": (
                        "No hay ninguna vista ni hoja que se pueda exportar. Abre la "
                        "planta o la vista 3D que quieras entregar y vuelve a pedirlo.")}
                opciones = DB.DWGExportOptions() if formato == "dwg" else DB.DXFExportOptions()
                doc.Export(carpeta, nombre, vistas, opciones)
            elif formato == "pdf":
                vistas = _vistas_para_exportar(doc)
                if vistas.Count == 0:
                    return {"ok": False, "error": (
                        "No hay ninguna vista ni hoja imprimible. Abre la vista que "
                        "quieras imprimir y vuelve a pedirlo.")}
                try:
                    opciones = DB.PDFExportOptions()
                except AttributeError:
                    return {"ok": False, "error": (
                        "Esta versión de Revit no exporta PDF por sí sola (hace falta "
                        "Revit 2022 o posterior). Exporta a DWG e imprime desde AutoCAD.")}
                opciones.FileName = nombre
                doc.Export(carpeta, vistas, opciones)
            else:
                return {"ok": False, "error": "Formato no soportado: " + formato}

            nuevos = [f for f in os.listdir(carpeta)
                      if f not in antes and f.lower().endswith("." + formato)]
            if not nuevos:
                return {"ok": False, "error": (
                    "Revit no dio error pero no escribió ningún archivo " +
                    formato.upper() + ".")}
            return {"ok": True, "resultado": sorted(nuevos)[0]}
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
