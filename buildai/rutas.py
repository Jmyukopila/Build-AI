"""Rutas de datos persistentes del usuario (config, sesiones).

Se guardan bajo el directorio personal del usuario (`~/.buildai`) y no junto
al código instalado: una vez empaquetado, el código puede vivir en site-packages
(de solo lectura o compartido entre usuarios), así que los datos de cada
persona deben vivir aparte. Usar `Path.home()` en vez de `%APPDATA%` también
evita el problema conocido del Python de Microsoft Store, que virtualiza las
escrituras a AppData (el proceso las ve, pero no llegan al disco real).
"""

import shutil
from pathlib import Path

CARPETA_DATOS = Path.home() / ".buildai"

# Ubicación anterior (junto al código, usada cuando el proyecto se ejecutaba
# solo como checkout en desarrollo). Si existe y la nueva carpeta está vacía,
# se migra automáticamente para no perder claves ni conversaciones guardadas.
_RAIZ_PROYECTO = Path(__file__).resolve().parent.parent


def _migrar_si_hace_falta(nombre: str) -> None:
    origen = _RAIZ_PROYECTO / nombre
    destino = CARPETA_DATOS / nombre
    if destino.exists() or not origen.exists():
        return
    CARPETA_DATOS.mkdir(parents=True, exist_ok=True)
    if origen.is_dir():
        shutil.copytree(origen, destino)
    else:
        shutil.copy2(origen, destino)


def ruta_config() -> Path:
    _migrar_si_hace_falta("config.json")
    return CARPETA_DATOS / "config.json"


def carpeta_sesiones() -> Path:
    _migrar_si_hace_falta("sesiones")
    return CARPETA_DATOS / "sesiones"
