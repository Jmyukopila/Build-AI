# -*- mode: python ; coding: utf-8 -*-
# Genera dist/BuildAI/BuildAI.exe (modo onedir: arranque más rápido y menos
# falsos positivos de antivirus que onefile). Se compila con:
#   .venv\Scripts\pyinstaller empaquetado\buildai.spec --noconfirm
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

# SPECPATH es empaquetado/, la raiz del proyecto es su padre.
RAIZ = Path(SPECPATH).resolve().parent

# Planos (PDF/DXF): pypdfium2 carga pdfium como biblioteca nativa y lee su
# version.json al importarse; ezdxf trae recursos propios. Se declaran a mano
# para no depender de que la versión instalada de hooks-contrib los cubra.
_BINARIOS_LIBRERIAS = collect_dynamic_libs("pypdfium2_raw")
_DATOS_LIBRERIAS = (
    collect_data_files("pypdfium2_raw")
    + collect_data_files("pypdfium2")
    + collect_data_files("ezdxf")
)

a = Analysis(
    [str(RAIZ / "empaquetado" / "run_buildai.py")],
    pathex=[str(RAIZ)],
    binaries=_BINARIOS_LIBRERIAS,
    datas=[
        (str(RAIZ / "buildai" / "ui"), "buildai/ui"),
        (str(RAIZ / "buildai" / "conocimiento_semillas"), "buildai/conocimiento_semillas"),
        (str(RAIZ / "buildai" / "addons"), "buildai/addons"),
        # No se importan como módulos: se leen como texto y se inyectan como
        # fuente en Blender/Revit, así que PyInstaller no los detecta solo.
        (str(RAIZ / "buildai" / "connectors" / "blender_kit.py"), "buildai/connectors"),
        (str(RAIZ / "buildai" / "connectors" / "revit_kit.py"), "buildai/connectors"),
    ] + _DATOS_LIBRERIAS,
    hiddenimports=[
        "uvicorn.logging",
        "uvicorn.loops.auto",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan.on",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="BuildAI",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(RAIZ / "buildai" / "ui" / "assets" / "buildai.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="BuildAI",
)
