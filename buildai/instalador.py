"""Instalador automático de los puentes de BuildAI.

Detecta todas las versiones instaladas de cada programa y copia el add-on
donde el programa lo carga solo, sin pasos manuales:

  - Blender  → <perfil>\\scripts\\startup\\  (se ejecuta al arrancar, 2.80+)
  - SketchUp → <perfil>\\SketchUp\\Plugins\\ (la extensión se auto-inicia, 2014+)
  - Revit    → %APPDATA%\\pyRevit\\Extensions + activa el servidor Routes
  - AutoCAD  → no necesita instalación (COM); solo se comprueba

Uso directo:  python -m buildai.instalador
También lo usa el botón "Conectar automáticamente" de la interfaz.
"""

import configparser
import contextlib
import io
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ADDONS = Path(__file__).resolve().parent / "addons"
APPDATA = Path(os.environ.get("APPDATA") or (Path.home() / "AppData" / "Roaming"))
# Carpeta real (nunca bajo AppData) para el archivo intermedio del truco de
# copia con Python de la Store: ver `_escribir_texto`.
_CARPETA_SEGURA = Path.home()


def _es_python_de_store() -> bool:
    """Python de Microsoft Store: virtualiza las escrituras a AppData (van a su
    contenedor privado y los programas reales no las ven)."""
    exe = sys.executable.lower()
    return "windowsapps" in exe or "pythonsoftwarefoundation" in exe


def _cmd(argumentos: list) -> bool:
    r = subprocess.run(["cmd", "/c"] + argumentos, capture_output=True)
    return r.returncode == 0


def _crear_carpeta(carpeta: Path) -> None:
    if os.name == "nt" and _es_python_de_store():
        # mkdir de cmd escapa del contenedor de la Store y crea intermedias
        if not carpeta.is_dir():
            _cmd(["mkdir", str(carpeta)])
        if not carpeta.is_dir():
            raise OSError(f"No se pudo crear {carpeta}")
        return
    carpeta.mkdir(parents=True, exist_ok=True)


def _copiar_archivo(origen: Path, destino: Path) -> None:
    _crear_carpeta(destino.parent)
    if os.name == "nt" and _es_python_de_store():
        if not _cmd(["copy", "/y", str(origen), str(destino)]):
            raise OSError(f"No se pudo copiar a {destino}")
        return
    shutil.copy2(origen, destino)


def _copiar_carpeta(origen: Path, destino: Path) -> None:
    if os.name == "nt" and _es_python_de_store():
        _crear_carpeta(destino.parent)
        if not _cmd(["xcopy", "/e", "/i", "/y", str(origen), str(destino)]):
            raise OSError(f"No se pudo copiar la carpeta a {destino}")
        return
    shutil.copytree(origen, destino, dirs_exist_ok=True)


def _escribir_texto(destino: Path, texto: str) -> None:
    _crear_carpeta(destino.parent)
    if os.name == "nt" and _es_python_de_store():
        # Escribir primero fuera de AppData (no virtualizado) y copiar con cmd
        temporal = _CARPETA_SEGURA / f"_buildai_{destino.name}.tmp"
        temporal.write_text(texto, encoding="utf-8")
        try:
            if not _cmd(["copy", "/y", str(temporal), str(destino)]):
                raise OSError(f"No se pudo escribir {destino}")
        finally:
            with contextlib.suppress(OSError):
                temporal.unlink()
        return
    destino.write_text(texto, encoding="utf-8")


def _programas_files() -> list:
    rutas = []
    for var, defecto in (("ProgramFiles", r"C:\Program Files"),
                         ("ProgramFiles(x86)", r"C:\Program Files (x86)")):
        ruta = Path(os.environ.get(var, defecto))
        if ruta.is_dir() and ruta not in rutas:
            rutas.append(ruta)
    return rutas


# ---------------------------------------------------------------- Blender

def _versiones_blender() -> set:
    """Versiones (como '4.2') detectadas por perfil de usuario o instalación."""
    versiones = set()
    perfil = APPDATA / "Blender Foundation" / "Blender"
    if perfil.is_dir():
        for d in perfil.iterdir():
            if d.is_dir() and re.fullmatch(r"\d+\.\d+", d.name):
                versiones.add(d.name)
    for pf in _programas_files():
        base = pf / "Blender Foundation"
        if base.is_dir():
            for inst in base.glob("Blender*"):
                for d in inst.iterdir() if inst.is_dir() else []:
                    if d.is_dir() and re.fullmatch(r"\d+\.\d+", d.name):
                        versiones.add(d.name)
        steam = pf / "Steam" / "steamapps" / "common" / "Blender"
        if steam.is_dir():
            for d in steam.iterdir():
                if d.is_dir() and re.fullmatch(r"\d+\.\d+", d.name):
                    versiones.add(d.name)
    return versiones


def _instalar_blender() -> dict:
    origen = ADDONS / "blender" / "buildai_blender.py"
    versiones = _versiones_blender()
    instaladas, antiguas = [], []
    for v in sorted(versiones):
        if tuple(int(x) for x in v.split(".")) < (2, 80):
            antiguas.append(v)
            continue
        destino = APPDATA / "Blender Foundation" / "Blender" / v / "scripts" / "startup"
        _copiar_archivo(origen, destino / "buildai_blender.py")
        # si alguna vez se instaló como add-on clásico, mantener esa copia al día
        addon_clasico = destino.parent / "addons" / "buildai_blender.py"
        if addon_clasico.exists():
            _copiar_archivo(origen, addon_clasico)
        instaladas.append(v)
    if not instaladas:
        if antiguas:
            return {"ok": False, "mensaje": (
                "Se encontró Blender " + ", ".join(antiguas) + " pero BuildAI necesita "
                "Blender 2.80 o superior. Actualiza Blender (blender.org) y vuelve a pulsar aquí."
            )}
        return {"ok": False, "mensaje": (
            "No se encontró Blender en este equipo. Si lo tienes instalado en una ruta "
            "poco habitual, instala el puente a mano: Edit → Preferences → Add-ons → "
            "Install… y elige addons\\blender\\buildai_blender.py."
        )}
    return {"ok": True, "mensaje": (
        "Puente instalado para Blender " + ", ".join(instaladas) + ". "
        "Abre (o reinicia) Blender y el punto se pondrá verde solo: no hay que activar nada."
    )}


# --------------------------------------------------------------- SketchUp

def _instalar_sketchup() -> dict:
    origen = ADDONS / "sketchup" / "buildai_sketchup.rb"
    base = APPDATA / "SketchUp"
    instaladas = []
    if base.is_dir():
        for d in sorted(base.iterdir()):
            if not (d.is_dir() and re.fullmatch(r"SketchUp \d{4}", d.name)):
                continue
            interior = d / "SketchUp"
            if not interior.is_dir():
                continue
            plugins = interior / "Plugins"
            _copiar_archivo(origen, plugins / "buildai_sketchup.rb")
            instaladas.append(d.name.replace("SketchUp ", ""))
    if not instaladas:
        return {"ok": False, "mensaje": (
            "No se encontró SketchUp (2014 o posterior) en este equipo. Si lo acabas de "
            "instalar, ábrelo una vez, ciérralo y vuelve a pulsar aquí. También puedes "
            "copiar a mano addons\\sketchup\\buildai_sketchup.rb a la carpeta Plugins."
        )}
    return {"ok": True, "mensaje": (
        "Puente instalado para SketchUp " + ", ".join(instaladas) + ". "
        "Abre (o reinicia) SketchUp y el punto se pondrá verde solo: la extensión se inicia sola."
    )}


# ------------------------------------------------------------------ Revit

def _pyrevit_detectado() -> bool:
    if shutil.which("pyrevit"):
        return True
    candidatos = [APPDATA / "pyRevit-Master", APPDATA / "pyRevit" / "pyRevit-Master"]
    programdata = Path(os.environ.get("ProgramData", r"C:\ProgramData"))
    candidatos += list(programdata.glob("pyRevit*"))
    for pf in _programas_files():
        candidatos += list(pf.glob("pyRevit*"))
    return any(c.exists() for c in candidatos)


def _revit_detectado() -> bool:
    return any((pf / "Autodesk").is_dir() and list((pf / "Autodesk").glob("Revit 20*"))
               for pf in _programas_files())


def _instalar_revit() -> dict:
    origen = ADDONS / "revit" / "BuildAI.extension"
    destino = APPDATA / "pyRevit" / "Extensions" / "BuildAI.extension"
    _copiar_carpeta(origen, destino)

    # Activar el servidor Routes de pyRevit en su configuración
    ini = APPDATA / "pyRevit" / "pyRevit_config.ini"
    cp = configparser.ConfigParser()
    cp.optionxform = str
    if ini.exists():
        cp.read(ini, encoding="utf-8")
    if not cp.has_section("routes"):
        cp.add_section("routes")
    cp.set("routes", "enabled", "true")
    contenido = io.StringIO()
    cp.write(contenido)
    _escribir_texto(ini, contenido.getvalue())

    if not _pyrevit_detectado():
        aviso = ("Falta pyRevit (gratuito): instálalo desde "
                 "github.com/pyrevitlabs/pyRevit/releases y reinicia Revit. "
                 "La extensión BuildAI ya quedó preparada.")
        if not _revit_detectado():
            aviso += " (No se detectó Revit en este equipo.)"
        return {"ok": False, "mensaje": aviso}
    return {"ok": True, "mensaje": (
        "Extensión instalada y servidor Routes activado. Reinicia Revit y abre un "
        "proyecto: el punto se pondrá verde solo."
    )}


# ---------------------------------------------------------------- AutoCAD

def _instalar_autocad() -> dict:
    try:
        from .connectors.autocad import _obtener_acad
        acad = _obtener_acad()
        abiertos = acad.Documents.Count
        return {"ok": True, "mensaje": (
            f"AutoCAD conectado ({abiertos} dibujo(s) abiertos). No necesita instalación."
        )}
    except Exception:
        pass
    instalado = any((pf / "Autodesk").is_dir() and list((pf / "Autodesk").glob("AutoCAD*"))
                    for pf in _programas_files())
    if instalado:
        return {"ok": True, "mensaje": (
            "AutoCAD no necesita instalación: solo ábrelo con un dibujo y el punto se "
            "pondrá verde. Si no conecta, ejecuta AutoCAD y BuildAI con el mismo nivel "
            "de permisos (ambos normales o ambos como administrador). "
            "Nota: AutoCAD LT no está soportado (no ofrece automatización COM)."
        )}
    return {"ok": False, "mensaje": (
        "No se encontró AutoCAD en este equipo. Funciona con AutoCAD completo 2004 o "
        "posterior (no con AutoCAD LT)."
    )}


def aviso_instalacion_arriesgada() -> str | None:
    """Detecta si el propio paquete quedó instalado bajo una ruta de AppData
    con Python de la Store: entonces el truco de `cmd copy` no podría leer el
    origen (cmd.exe ve el AppData real, no el contenedor virtualizado) y la
    instalación de puentes fallaría en silencio, como ya pasó una vez.
    Devuelve un aviso en texto si aplica, o None si todo está bien.
    """
    if not (os.name == "nt" and _es_python_de_store()):
        return None
    if "appdata" not in str(ADDONS).lower():
        return None
    return (
        "Atención: BuildAI se instaló con el Python de Microsoft Store dentro de una "
        "carpeta de AppData (p. ej. con 'pip install --user'). Ese Python virtualiza "
        "esas rutas: los puentes a Blender/SketchUp/Revit podrían no copiarse de "
        "verdad aunque el instalador diga que salió bien. Solución: crea un entorno "
        "virtual en una carpeta normal (no AppData) y reinstala ahí, por ejemplo:\n"
        "  python -m venv %USERPROFILE%\\buildai-env\n"
        "  %USERPROFILE%\\buildai-env\\Scripts\\activate\n"
        "  pip install buildai   (o la ruta al proyecto)"
    )


# ------------------------------------------------- Acceso directo escritorio

def crear_acceso_directo() -> dict:
    """Crea (o actualiza) el acceso directo «BuildAI» en el escritorio.

    Si el código se ejecuta desde el checkout del proyecto (existe INICIAR.bat),
    el acceso apunta al .bat; si está instalado como paquete (pip/pipx), apunta
    a `python -m buildai.main`, que funciona desde cualquier carpeta porque los
    datos viven en ~/.buildai. Se crea con PowerShell (proceso aparte), así que
    no le afecta la virtualización del Python de la Store.
    """
    if os.name != "nt":
        return {"ok": False, "mensaje": "El acceso directo solo se crea en Windows."}
    raiz = Path(__file__).resolve().parent.parent
    iniciar = raiz / "INICIAR.bat"
    if iniciar.exists():
        objetivo, argumentos, carpeta = iniciar, "", raiz
    else:
        objetivo, argumentos, carpeta = Path(sys.executable), "-m buildai.main", Path.home()
    icono = Path(__file__).resolve().parent / "ui" / "assets" / "buildai.ico"
    script = (
        "$w = New-Object -ComObject WScript.Shell; "
        "$d = [Environment]::GetFolderPath('Desktop'); "
        "$s = $w.CreateShortcut((Join-Path $d 'BuildAI.lnk')); "
        f"$s.TargetPath = '{objetivo}'; "
        f"$s.Arguments = '{argumentos}'; "
        f"$s.WorkingDirectory = '{carpeta}'; "
        "$s.Description = 'BuildAI - Asistente de IA para arquitectos'; "
        + (f"$s.IconLocation = '{icono},0'; " if icono.exists() else "")
        + "$s.Save()"
    )
    r = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True,
    )
    if r.returncode != 0:
        return {"ok": False, "mensaje": f"No se pudo crear el acceso directo: {r.stderr.decode(errors='replace').strip()}"}
    return {"ok": True, "mensaje": "Acceso directo «BuildAI» creado en el escritorio."}


# ------------------------------------------------------------------ API

_INSTALADORES = {
    "blender": _instalar_blender,
    "sketchup": _instalar_sketchup,
    "revit": _instalar_revit,
    "autocad": _instalar_autocad,
}


def instalar(programa_id: str) -> dict:
    fn = _INSTALADORES.get(programa_id)
    if fn is None:
        return {"ok": False, "mensaje": f"Programa desconocido: {programa_id}"}
    try:
        return fn()
    except Exception as exc:
        return {"ok": False, "mensaje": f"No se pudo instalar el puente: {exc}"}


def instalar_todos() -> None:
    aviso = aviso_instalacion_arriesgada()
    if aviso:
        print()
        print("  [AVISO] " + aviso.replace("\n", "\n          "))
    print()
    print("  Buscando tus programas e instalando los puentes de BuildAI...")
    print()
    for pid, fn in _INSTALADORES.items():
        resultado = instalar(pid)
        marca = "OK " if resultado["ok"] else "-- "
        print(f"  [{marca}] {pid.capitalize()}: {resultado['mensaje']}")
    try:
        acceso = crear_acceso_directo()
    except Exception as exc:
        acceso = {"ok": False, "mensaje": f"No se pudo crear el acceso directo: {exc}"}
    print(f"  [{'OK ' if acceso['ok'] else '-- '}] Escritorio: {acceso['mensaje']}")
    print()


if __name__ == "__main__":
    instalar_todos()
