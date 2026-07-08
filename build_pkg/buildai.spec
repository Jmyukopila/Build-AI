# -*- mode: python ; coding: utf-8 -*-
# Genera dist/BuildAI/BuildAI.exe (modo onedir: arranque más rápido y menos
# falsos positivos de antivirus que onefile). Se compila con:
#   .venv\Scripts\pyinstaller build_pkg\buildai.spec --noconfirm
from pathlib import Path

RAIZ = Path(SPECPATH).resolve().parent

a = Analysis(
    [str(RAIZ / "build_pkg" / "run_buildai.py")],
    pathex=[str(RAIZ)],
    binaries=[],
    datas=[
        (str(RAIZ / "buildai" / "ui"), "buildai/ui"),
        (str(RAIZ / "buildai" / "skills_data"), "buildai/skills_data"),
        (str(RAIZ / "buildai" / "addons"), "buildai/addons"),
        # No se importan como módulos: se leen como texto y se inyectan como
        # fuente en Blender/Revit, así que PyInstaller no los detecta solo.
        (str(RAIZ / "buildai" / "connectors" / "blender_kit.py"), "buildai/connectors"),
        (str(RAIZ / "buildai" / "connectors" / "revit_kit.py"), "buildai/connectors"),
    ],
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
