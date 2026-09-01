"""Entregables: archivos de trabajo reales que los conectores exportan.

A diferencia de los renders (imágenes PNG que produce Blender), un entregable es
un archivo profesional generado por el propio programa del usuario: IFC de
Revit, DWG/DXF de AutoCAD, PDF de planos, mallas 3D de Blender… BuildAI no los
construye, solo pide la exportación y recoge el resultado.

Circuito: la herramienta del conector guarda el archivo en CARPETA_ENTREGABLES e
imprime `ARCHIVO_GUARDADO: <ruta>`. El agente detecta la marca y avisa a la
interfaz, que descarga el archivo por /api/entregables/{nombre}.
"""

import re
import time
from pathlib import Path

CARPETA_ENTREGABLES = Path.home() / ".buildai" / "entregables"
MARCA = "ARCHIVO_GUARDADO:"

# Extensiones exportables y su nombre visible. Es lista blanca a propósito: el
# nombre del archivo viaja a la interfaz y vuelve como petición HTTP, así que
# solo pueden servirse formatos de dibujo, nunca ejecutables ni configuración.
FORMATOS = {
    "ifc": "IFC",
    "dwg": "DWG",
    "dxf": "DXF",
    "pdf": "PDF",
    "gltf": "glTF",
    "glb": "glTF",
    "obj": "OBJ",
    "fbx": "FBX",
    "usd": "USD",
    "usdz": "USD",
    "dae": "COLLADA",
    "stl": "STL",
}


def extension_valida(nombre: str) -> bool:
    return Path(nombre).suffix.lstrip(".").lower() in FORMATOS


def ruta_para(nombre_base: str, extension: str) -> Path:
    """Ruta de destino para una exportación, ya con la carpeta creada.

    El nombre lo propone el modelo, así que se reduce a caracteres seguros: sin
    barras, sin acentos y sin puntos que puedan colar una extensión distinta.
    """
    limpio = re.sub(r"[^A-Za-z0-9_-]+", "-", (nombre_base or "").strip()).strip("-")
    ext = extension.lstrip(".").lower()
    if ext not in FORMATOS:
        raise ValueError(f"Formato no exportable: {extension}")
    CARPETA_ENTREGABLES.mkdir(parents=True, exist_ok=True)
    return CARPETA_ENTREGABLES / f"{limpio or 'entregable'}-{int(time.time())}.{ext}"


def entregables_en_resultado(resultado: str) -> list:
    """Entregables anunciados en la salida de una herramienta.

    Solo se aceptan archivos reales dentro de la carpeta de entregables: el
    nombre viaja a la interfaz, que los pide por /api/entregables/{nombre}.
    """
    encontrados = []
    for linea in str(resultado).splitlines():
        if not linea.startswith(MARCA):
            continue
        ruta = Path(linea[len(MARCA):].strip())
        try:
            if not ruta.is_file() or ruta.parent.resolve() != CARPETA_ENTREGABLES.resolve():
                continue
            ext = ruta.suffix.lstrip(".").lower()
            if ext not in FORMATOS:
                continue
            encontrados.append(
                {"archivo": ruta.name, "formato": FORMATOS[ext], "bytes": ruta.stat().st_size}
            )
        except OSError:
            continue
    return encontrados
