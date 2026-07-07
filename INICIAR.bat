@echo off
title BuildAI
cd /d "%~dp0"
set PYTHONUTF8=1
python -m buildai.main
if errorlevel 1 (
    echo.
    echo  [ERROR] BuildAI no pudo arrancar. Si es la primera vez, ejecuta antes INSTALAR.bat
    pause
)
