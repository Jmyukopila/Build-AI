# Genera empaquetado\Output\BuildAI-Setup.exe desde cero: crea/actualiza el
# entorno de compilación, empaqueta con PyInstaller y compila el instalador
# con Inno Setup.
#
# Uso:  powershell -File empaquetado\build_installer.ps1
$ErrorActionPreference = "Stop"
# El script vive en empaquetado\ pero opera desde la raíz del proyecto: ahí están
# el paquete buildai, requirements.txt y el .venv de compilación.
Set-Location (Split-Path $PSScriptRoot -Parent)

$venvPython = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Host "Creando entorno virtual de compilación (.venv)..."
    python -m venv .venv
}

Write-Host "Instalando dependencias de compilación..."
& $venvPython -m pip install --upgrade pip --quiet
& $venvPython -m pip install -r requirements.txt pyinstaller pywebview --quiet

Write-Host "Empaquetando BuildAI.exe con PyInstaller..."
& $venvPython -m PyInstaller empaquetado\buildai.spec --noconfirm --distpath empaquetado\dist --workpath empaquetado\work
if ($LASTEXITCODE -ne 0) { throw "PyInstaller falló" }

# IA incluida: el motor llama.cpp (Vulkan: GPUs NVIDIA, AMD e Intel, con la CPU
# de respaldo) viaja DENTRO del instalador. Versión y hash fijados en
# buildai\ia_local.py: si se cambian allí, hay que cambiarlos aquí.
$motorZip = "empaquetado\work\llama-b12626-bin-win-vulkan-x64.zip"
$motorSha = "b064a618c174d0c800e1a99a83885e710f826520004e3bb9af827a22ca63b689"
if (-not (Test-Path $motorZip)) {
    Write-Host "Descargando el motor de la IA incluida (b12626)..."
    Invoke-WebRequest -Uri "https://github.com/ggml-org/llama.cpp/releases/download/b12626/llama-b12626-bin-win-vulkan-x64.zip" -OutFile $motorZip
}
if ((Get-FileHash $motorZip -Algorithm SHA256).Hash.ToLower() -ne $motorSha) {
    Remove-Item $motorZip
    throw "El motor descargado no coincide con su SHA-256: se ha borrado, vuelve a ejecutar el script."
}
Expand-Archive -Path $motorZip -DestinationPath "empaquetado\dist\BuildAI\motor" -Force

$iscc = Get-ChildItem -Path "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe", "C:\Program Files (x86)\Inno Setup 6\ISCC.exe", "C:\Program Files\Inno Setup 6\ISCC.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $iscc) {
    throw "No se encontró ISCC.exe (Inno Setup). Instálalo con: winget install JRSoftware.InnoSetup"
}

Write-Host "Compilando el instalador con Inno Setup..."
& $iscc.FullName empaquetado\BuildAI.iss
if ($LASTEXITCODE -ne 0) { throw "ISCC falló" }

Write-Host ""
Write-Host "Listo: empaquetado\Output\BuildAI-Setup.exe"
