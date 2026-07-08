# Genera build_pkg\Output\BuildAI-Setup.exe desde cero: crea/actualiza el
# entorno de compilación, empaqueta con PyInstaller y compila el instalador
# con Inno Setup.
#
# Uso:  powershell -File build_installer.ps1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$venvPython = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Host "Creando entorno virtual de compilación (.venv)..."
    python -m venv .venv
}

Write-Host "Instalando dependencias de compilación..."
& $venvPython -m pip install --upgrade pip --quiet
& $venvPython -m pip install -r requirements.txt pyinstaller pywebview --quiet

Write-Host "Empaquetando BuildAI.exe con PyInstaller..."
& $venvPython -m PyInstaller build_pkg\buildai.spec --noconfirm --distpath build_pkg\dist --workpath build_pkg\work
if ($LASTEXITCODE -ne 0) { throw "PyInstaller falló" }

$iscc = Get-ChildItem -Path "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe", "C:\Program Files (x86)\Inno Setup 6\ISCC.exe", "C:\Program Files\Inno Setup 6\ISCC.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $iscc) {
    throw "No se encontró ISCC.exe (Inno Setup). Instálalo con: winget install JRSoftware.InnoSetup"
}

Write-Host "Compilando el instalador con Inno Setup..."
& $iscc.FullName build_pkg\BuildAI.iss
if ($LASTEXITCODE -ne 0) { throw "ISCC falló" }

Write-Host ""
Write-Host "Listo: build_pkg\Output\BuildAI-Setup.exe"
