@echo off
title BuildAI - Instalacion
echo.
echo  ============================================
echo   BuildAI - Instalacion (solo la primera vez)
echo  ============================================
echo.
where python >nul 2>nul
if errorlevel 1 (
    echo  [ERROR] No se encontro Python.
    echo  Instala Python 3.11 o superior desde https://www.python.org/downloads/
    echo  y marca la casilla "Add Python to PATH" durante la instalacion.
    pause
    exit /b 1
)
echo  Instalando componentes (puede tardar 1-2 minutos)...
python -m pip install --user -r "%~dp0requirements.txt"
if errorlevel 1 (
    echo.
    echo  [ERROR] La instalacion fallo. Revisa tu conexion a internet.
    pause
    exit /b 1
)
cd /d "%~dp0"
set PYTHONUTF8=1
python -m buildai.instalador
echo.
echo  Instalacion completada. Ahora ejecuta INICIAR.bat
pause
