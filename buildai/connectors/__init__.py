"""Registro de conectores a programas de arquitectura."""

from .blender import ConectorBlender
from .autocad import ConectorAutoCAD
from .sketchup import ConectorSketchUp
from .revit import ConectorRevit

CONECTORES = [
    ConectorBlender(),
    ConectorAutoCAD(),
    ConectorSketchUp(),
    ConectorRevit(),
]


def conectores_disponibles():
    """Conectores cuyo programa está abierto y responde ahora mismo."""
    return [c for c in CONECTORES if c.disponible()]


def buscar_herramienta(nombre: str):
    """Devuelve (conector, herramienta) para un nombre de herramienta, o None."""
    for conector in CONECTORES:
        for herramienta in conector.herramientas():
            if herramienta["nombre"] == nombre:
                return conector, herramienta
    return None
