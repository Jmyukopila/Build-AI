"""Dobles de prueba de los programas que BuildAI pilota.

BuildAI no modela por su cuenta: le pide a AutoCAD, Blender, SketchUp y Revit que
exporten con su propia API. Nada de eso existe fuera de Windows con esos programas
abiertos, así que estos dobles ocupan su sitio para poder probar lo que sí es
nuestro: qué orden se elige, con qué ruta, y qué se hace con la respuesta.

Los dobles imitan el efecto observable (escribir el archivo) además de la llamada,
porque el código de exportación espera a que el archivo aparezca en disco.
"""

import contextlib
import sys
import types
from pathlib import Path

from buildai.providers.base import Proveedor, RespuestaLLM
from buildai.connectors.base import Conector


# --------------------------------------------------------------- AutoCAD (COM)

class _PlotFalso:
    def __init__(self, registro, escribir):
        self._registro = registro
        self._escribir = escribir

    def PlotToFile(self, ruta, configuracion=None):
        self._registro.append(("PlotToFile", ruta, configuracion))
        if self._escribir:
            Path(ruta).write_bytes(b"%PDF-1.4 falso")
        return True


class _ConjuntosFalsos:
    def __init__(self, existentes=()):
        self._conjuntos = [types.SimpleNamespace(Name=n, Delete=self._borrar) for n in existentes]
        self.borrados = []
        self.añadidos = []

    Count = property(lambda self: len(self._conjuntos))

    def Item(self, i):
        return self._conjuntos[i]

    def Add(self, nombre):
        self.añadidos.append(nombre)
        return types.SimpleNamespace(Name=nombre)

    def _borrar(self):
        self.borrados.append(True)


class DocumentoAutoCADFalso:
    """Documento COM de AutoCAD. Registra cada llamada en `registro` y, si
    `escribir` es True, crea el archivo como haría AutoCAD de verdad."""

    def __init__(self, nombre="Dibujo1.dwg", escribir=True, conjuntos_existentes=()):
        self.Name = nombre
        self.registro = []
        self._escribir = escribir
        self.SelectionSets = _ConjuntosFalsos(conjuntos_existentes)
        self.Plot = _PlotFalso(self.registro, escribir)
        self.ModelSpace = types.SimpleNamespace(Count=0)

    def SendCommand(self, orden):
        self.registro.append(("SendCommand", orden))
        if self._escribir:
            # AutoCAD escribe la ruta que va en la propia orden.
            for trozo in orden.split("\n"):
                if trozo.endswith((".dwg", ".dxf")):
                    Path(trozo).write_bytes(b"AC1032 falso")

    def Export(self, ruta, extension, conjunto):
        self.registro.append(("Export", ruta, extension, conjunto))
        if self._escribir:
            Path(ruta).write_bytes(b"0\nSECTION\n0\nEOF\n")

    def SaveAs(self, *args, **kwargs):  # pragma: no cover - debe no llamarse nunca
        self.registro.append(("SaveAs", args))
        raise AssertionError("SaveAs renombraría el dibujo abierto del usuario")

    def ordenes(self, tipo):
        return [r for r in self.registro if r[0] == tipo]


class AplicacionAutoCADFalsa:
    """Lo que devuelve `_obtener_acad()`: la aplicación con su documento activo."""

    def __init__(self, documento=None):
        self.ActiveDocument = documento if documento is not None else DocumentoAutoCADFalso()
        self.Documents = types.SimpleNamespace(Count=1)


# ------------------------------------------------------------------ HTTP (httpx)

class RespuestaFalsa:
    """Lo mínimo de una respuesta de httpx que usan los conectores."""

    def __init__(self, datos=None, status_code=200, texto=""):
        self.status_code = status_code
        self._datos = datos
        self.text = texto

    def json(self):
        if self._datos is None:
            raise ValueError("respuesta sin JSON")
        return self._datos


class HttpFalso:
    """Sustituye a httpx.post/get y guarda url, cuerpo y plazo de cada llamada."""

    def __init__(self, respuesta):
        self.respuesta = respuesta
        self.llamadas = []

    def __call__(self, url, json=None, timeout=None, **kwargs):
        self.llamadas.append({"url": url, "json": json, "timeout": timeout})
        if isinstance(self.respuesta, Exception):
            raise self.respuesta
        return self.respuesta

    @property
    def ultima(self):
        return self.llamadas[-1]


# ------------------------------------------------------------------ Blender (bpy)

class _OperadorFalso:
    def __init__(self, registro, nombre, fallar=False):
        self._registro = registro
        self._nombre = nombre
        self._fallar = fallar

    def __call__(self, filepath=None, **opciones):
        self._registro.append({"operador": self._nombre, "filepath": filepath, "opciones": opciones})
        if self._fallar:
            raise RuntimeError(f"{self._nombre} no disponible en esta versión")
        Path(filepath).write_bytes(b"modelo 3d falso")


class _FamiliaOperadores:
    def __init__(self, registro, familia, disponibles, fallan):
        self._registro = registro
        self._familia = familia
        self._disponibles = disponibles
        self._fallan = fallan

    def __getattr__(self, nombre):
        completo = f"{self._familia}.{nombre}"
        if completo not in self._disponibles:
            raise AttributeError(completo)
        return _OperadorFalso(self._registro, completo, fallar=completo in self._fallan)


class _OpsFalsos:
    def __init__(self, registro, disponibles, fallan):
        self._registro = registro
        self._disponibles = disponibles
        self._fallan = fallan

    def __getattr__(self, familia):
        return _FamiliaOperadores(self._registro, familia, self._disponibles, self._fallan)


# Operadores de exportación que trae un Blender moderno (4.x).
OPERADORES_BLENDER_4 = {
    "export_scene.gltf", "export_scene.fbx", "wm.obj_export",
    "wm.usd_export", "wm.stl_export", "wm.collada_export",
}
# Blender 3.x antiguo: el exportador de OBJ vivía en otro sitio.
OPERADORES_BLENDER_3 = (OPERADORES_BLENDER_4 - {"wm.obj_export", "wm.stl_export"}) | {
    "export_scene.obj", "export_mesh.stl",
}


@contextlib.contextmanager
def stubs_blender(disponibles=None, fallan=()):
    """Instala `bpy` y `mathutils` falsos para poder importar `blender_kit`.

    `blender_kit.py` importa ambos sin protección, así que fuera de Blender no se
    puede ni importar. Devuelve la lista de operadores invocados.
    """
    registro = []
    bpy = types.ModuleType("bpy")
    bpy.ops = _OpsFalsos(registro, OPERADORES_BLENDER_4 if disponibles is None else disponibles, set(fallan))
    bpy.data = types.SimpleNamespace(materials=types.SimpleNamespace(get=lambda n: None))
    bpy.context = types.SimpleNamespace(scene=None)
    bpy.types = types.SimpleNamespace(Material=type("Material", (), {}))
    bpy.app = types.SimpleNamespace(timers=types.SimpleNamespace(register=lambda *a, **k: None))
    mathutils = types.ModuleType("mathutils")
    mathutils.Vector = tuple

    previos = {n: sys.modules.get(n) for n in ("bpy", "mathutils")}
    sys.modules["bpy"], sys.modules["mathutils"] = bpy, mathutils
    try:
        yield registro
    finally:
        for nombre, modulo in previos.items():
            if modulo is None:
                sys.modules.pop(nombre, None)
            else:
                sys.modules[nombre] = modulo


@contextlib.contextmanager
def kit_blender(disponibles=None, fallan=()):
    """Importa `blender_kit.py` con `bpy` falso y cede (modulo, operadores_usados).

    El kit no se importa nunca en la app (se lee como texto y se inyecta en
    Blender), así que hay que cargarlo a mano desde su ruta.
    """
    import importlib.util

    ruta = Path(__file__).resolve().parent.parent / "buildai" / "connectors" / "blender_kit.py"
    with stubs_blender(disponibles, fallan) as registro:
        spec = importlib.util.spec_from_file_location("_blender_kit_bajo_prueba", ruta)
        modulo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(modulo)
        yield modulo, registro


# ------------------------------------------------------------------ Revit (pyRevit)

class _ListaNet:
    """Imita List[T] de .NET: `List[DB.ElementId]()` construye, `.Add` y `.Count`."""

    def __init__(self):
        self._items = []

    def __class_getitem__(cls, _tipo):
        return cls

    def Add(self, item):
        self._items.append(item)

    @property
    def Count(self):
        return len(self._items)

    def __iter__(self):
        return iter(self._items)


class _Coleccion:
    def __init__(self, elementos):
        self._elementos = list(elementos)

    def OfClass(self, _clase):
        return self

    def OfCategory(self, _categoria):
        return self

    def WhereElementIsNotElementType(self):
        return self

    def ToElements(self):
        return self._elementos

    def GetElementCount(self):
        return len(self._elementos)


class _OpcionesIFC:
    def __init__(self):
        self.FileVersion = None


class _OpcionesDWG:
    pass


class _OpcionesDXF:
    pass


class _OpcionesPDF:
    def __init__(self):
        self.FileName = None


_EXTENSION_POR_OPCIONES = {
    _OpcionesIFC: "ifc", _OpcionesDWG: "dwg", _OpcionesDXF: "dxf", _OpcionesPDF: "pdf",
}


class DocumentoRevitFalso:
    """Documento de Revit. `Export` tiene tres firmas distintas según el formato,
    y escribe el archivo con el nombre que Revit usaría de verdad."""

    def __init__(self, hojas=(), vista_activa=None, escribir=True, sufijo_vista=""):
        self.Title = "Proyecto1"
        self.ActiveView = vista_activa
        self.Application = types.SimpleNamespace(VersionNumber="2024")
        self.hojas = list(hojas)
        self.exportaciones = []
        self._escribir = escribir
        self._sufijo_vista = sufijo_vista

    def Export(self, *args):
        if len(args) == 4:                       # DWG y DXF
            carpeta, nombre, vistas, opciones = args
        elif isinstance(args[1], str):           # IFC
            carpeta, nombre, opciones = args
            vistas = None
        else:                                    # PDF: el nombre va en las opciones
            carpeta, vistas, opciones = args
            nombre = opciones.FileName
        self.exportaciones.append(
            {"carpeta": carpeta, "nombre": nombre, "vistas": vistas, "opciones": opciones}
        )
        if self._escribir:
            extension = _EXTENSION_POR_OPCIONES[type(opciones)]
            Path(carpeta, f"{nombre}{self._sufijo_vista}.{extension}").write_bytes(b"falso")
        return True


class _TransaccionFalsa:
    """Si /exportar la usara, Revit lanzaría: Document.Export está prohibido
    dentro de una transacción. Por eso se registra cada uso."""

    def __init__(self, registro, nombre):
        self._registro = registro
        self._registro.append(nombre)

    def __enter__(self):
        return self

    def __exit__(self, *excepcion):
        return False


@contextlib.contextmanager
def stubs_pyrevit(documento=None, con_pdf=True):
    """Carga `startup.py` de la extensión con pyRevit falso y cede sus rutas.

    La extensión importa `from pyrevit import revit, DB` sin protección y registra
    las rutas como efecto de importación, así que es la única forma de llamar a
    `/exportar` fuera de Revit.
    """
    import importlib.util

    doc = documento if documento is not None else DocumentoRevitFalso()
    transacciones = []
    manejadores = {}

    class _API:
        def __init__(self, _nombre):
            pass

        def route(self, camino, methods=None):
            def decorador(funcion):
                manejadores[camino] = funcion
                return funcion
            return decorador

    db = types.SimpleNamespace(
        FilteredElementCollector=lambda d: _Coleccion(d.hojas),
        Level=object, ViewSheet=object, View3D=object, WallType=object, FamilySymbol=object,
        ElementId=object, BuiltInCategory=types.SimpleNamespace(**{
            n: n for n in ("OST_Walls", "OST_Doors", "OST_Windows", "OST_Floors",
                           "OST_Roofs", "OST_Rooms", "OST_Furniture", "OST_LightingFixtures")}),
        Element=types.SimpleNamespace(Name=types.SimpleNamespace(GetValue=lambda t: "tipo")),
        IFCExportOptions=_OpcionesIFC,
        IFCVersion=types.SimpleNamespace(IFC4="IFC4", IFC2x3CV2="IFC2x3CV2"),
        DWGExportOptions=_OpcionesDWG,
        DXFExportOptions=_OpcionesDXF,
    )
    if con_pdf:
        db.PDFExportOptions = _OpcionesPDF

    pyrevit = types.ModuleType("pyrevit")
    pyrevit.routes = types.ModuleType("pyrevit.routes")
    pyrevit.routes.API = _API
    pyrevit.revit = types.SimpleNamespace(
        doc=doc, uidoc=None,
        Transaction=lambda nombre: _TransaccionFalsa(transacciones, nombre),
    )
    pyrevit.DB = db

    system = types.ModuleType("System")
    coleccion = types.ModuleType("System.Collections")
    generic = types.ModuleType("System.Collections.Generic")
    generic.List = _ListaNet
    coleccion.Generic = generic
    system.Collections = coleccion

    nuevos = {
        "pyrevit": pyrevit, "pyrevit.routes": pyrevit.routes,
        "System": system, "System.Collections": coleccion,
        "System.Collections.Generic": generic,
    }
    previos = {n: sys.modules.get(n) for n in nuevos}
    sys.modules.update(nuevos)
    try:
        ruta = (Path(__file__).resolve().parent.parent / "buildai" / "addons" / "revit"
                / "BuildAI.extension" / "startup.py")
        spec = importlib.util.spec_from_file_location("_startup_bajo_prueba", ruta)
        modulo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(modulo)
        yield types.SimpleNamespace(
            rutas=manejadores, doc=doc, transacciones=transacciones, modulo=modulo
        )
    finally:
        for nombre, modulo_previo in previos.items():
            if modulo_previo is None:
                sys.modules.pop(nombre, None)
            else:
                sys.modules[nombre] = modulo_previo


def peticion(datos):
    """Lo que pyRevit Routes entrega a un manejador."""
    return types.SimpleNamespace(data=datos)


# ------------------------------------------------------------------ Proveedor y conector

class ProveedorFalso(Proveedor):
    """Devuelve un guion de respuestas preparado, sin red ni clave de API."""

    def __init__(self, guion):
        self.guion = list(guion)
        self.conversaciones = []

    def conversar(self, sistema, historial, herramientas):
        self.conversaciones.append({"sistema": sistema, "herramientas": herramientas})
        return self.guion.pop(0) if self.guion else RespuestaLLM(texto="Listo.")


class ConectorFalso(Conector):
    """Conector siempre disponible con una herramienta cuya salida se fija."""

    id = "falso"
    nombre = "Programa Falso"
    icono = "tarea"

    def __init__(self, salida="", nombre_herramienta="falso_exportar"):
        self.salida = salida
        self.nombre_herramienta = nombre_herramienta
        self.ejecuciones = []

    def disponible(self):
        return True

    def herramientas(self):
        return [{
            "nombre": self.nombre_herramienta,
            "descripcion": "Herramienta de prueba.",
            "parametros": {"type": "object", "properties": {}, "required": []},
        }]

    def ejecutar(self, nombre, argumentos):
        self.ejecuciones.append((nombre, argumentos))
        return self.salida
