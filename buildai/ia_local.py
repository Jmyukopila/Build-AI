"""IA incluida: un modelo ligero que corre en el propio ordenador, gratis y sin clave.

Es el proveedor por defecto para que BuildAI funcione nada más instalarlo:
sin cuenta, sin clave, sin límites diarios y sin enviar nada a internet.

Piezas:
- Motor: llama-server de llama.cpp (licencia MIT), versión fijada abajo. El
  instalador de Windows lo trae dentro; si no está (instalación desde código),
  se descarga una vez la versión oficial verificando su SHA-256.
- Modelo: Qwen3.5-4B en GGUF Q4_K_M (Apache 2.0, ~2,7 GB). El instalador lo
  descarga durante la instalación; si no lo hizo, BuildAI lo descarga solo al
  arrancar, con progreso visible en la interfaz y reanudación si se corta.
- Proceso: BuildAI arranca el motor en 127.0.0.1 (nunca expuesto a la red) con
  un contexto fijo de 16k tokens, comprueba que responde y lo cierra al salir.

¿Por qué no Ollama? Su API compatible con OpenAI no deja ampliar el contexto
(con 4 GB de VRAM se queda en 4 096 tokens y rechaza la petición de BuildAI),
exige instalar otra aplicación y no se puede llevar dentro del instalador.
"""

import atexit
import hashlib
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import threading
import time
import zipfile
from pathlib import Path

import httpx

from . import rutas

PUERTO = 8610
CONTEXTO = 16384
NOMBRE = "IA incluida"

# Versión del motor fijada: actualizarla exige comprobar de nuevo los hashes
# (los publica GitHub en el campo "digest" de cada archivo de la release).
_VERSION_MOTOR = "b12626"
_MOTORES = {
    ("Windows", "x64"): ("llama-b12626-bin-win-vulkan-x64.zip",
                         "b064a618c174d0c800e1a99a83885e710f826520004e3bb9af827a22ca63b689"),
    ("Linux", "x64"): ("llama-b12626-bin-ubuntu-vulkan-x64.tar.gz",
                       "0b263ae3b910890535f20f8c05e61461c2080f8966050af356a029b90d37d843"),
}

MODELO = {
    "id": "qwen3.5-4b",
    "nombre": "Qwen3.5 4B",
    "archivo": "Qwen3.5-4B-Q4_K_M.gguf",
    "url": "https://huggingface.co/unsloth/Qwen3.5-4B-GGUF/resolve/main/Qwen3.5-4B-Q4_K_M.gguf",
    "sha256": "00fe7986ff5f6b463e62455821146049db6f9313603938a70800d1fb69ef11a4",
    "bytes": 2740937888,
}

_CABECERAS = {"User-Agent": "BuildAI (asistente de arquitectura)"}


class ErrorIALocal(RuntimeError):
    pass


# ------------------------------------------------------------------ carpetas

def carpeta():
    destino = rutas.CARPETA_DATOS / "ia_local"
    destino.mkdir(parents=True, exist_ok=True)
    return destino


def ruta_modelo() -> Path:
    return carpeta() / "modelos" / MODELO["archivo"]


def _plataforma():
    sistema = platform.system()
    maquina = platform.machine().lower()
    arquitectura = "x64" if maquina in ("x86_64", "amd64") else maquina
    return sistema, arquitectura


def _nombre_binario():
    return "llama-server.exe" if os.name == "nt" else "llama-server"


def buscar_motor():
    """Ruta a llama-server: el incluido en la instalación o el ya descargado."""
    candidatos = []
    if getattr(sys, "frozen", False):  # instalación empaquetada (PyInstaller)
        candidatos.append(Path(sys.executable).parent / "motor")
    if os.environ.get("BUILDAI_MOTOR"):
        candidatos.append(Path(os.environ["BUILDAI_MOTOR"]))
    candidatos.append(carpeta() / "motor")
    for base in candidatos:
        if base.is_file():
            return base
        if base.is_dir():
            encontrado = next(base.rglob(_nombre_binario()), None)
            if encontrado:
                return encontrado
    return None


# ----------------------------------------------------------------- descargas

def _sha256(ruta: Path) -> str:
    h = hashlib.sha256()
    with ruta.open("rb") as f:
        for trozo in iter(lambda: f.read(1 << 22), b""):
            h.update(trozo)
    return h.hexdigest()


def _descargar(url, destino: Path, sha256: str, total: int, progreso=None):
    """Descarga verificada y REANUDABLE (un corte a mitad de 2,7 GB no empieza de cero)."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    parcial = destino.with_name(destino.name + ".parcial")
    hecho = parcial.stat().st_size if parcial.exists() else 0
    cabeceras = dict(_CABECERAS)
    if hecho:
        cabeceras["Range"] = f"bytes={hecho}-"
    try:
        with httpx.stream("GET", url, headers=cabeceras, follow_redirects=True, timeout=60.0) as r:
            if r.status_code == 200 and hecho:
                hecho = 0  # el servidor no admite reanudar: se empieza de nuevo
            elif r.status_code not in (200, 206):
                raise ErrorIALocal(f"El servidor de descarga respondió {r.status_code}.")
            with parcial.open("ab" if hecho else "wb") as f:
                for trozo in r.iter_bytes(1 << 20):
                    f.write(trozo)
                    hecho += len(trozo)
                    if progreso:
                        progreso(hecho / total if total else 0.0)
    except httpx.HTTPError as exc:
        raise ErrorIALocal(f"Se cortó la descarga ({exc}). Se reanudará donde quedó.") from exc
    if _sha256(parcial) != sha256:
        parcial.unlink(missing_ok=True)
        raise ErrorIALocal("El archivo descargado llegó dañado (no coincide su huella SHA-256); se volverá a bajar.")
    parcial.replace(destino)


def _instalar_motor(progreso=None):
    clave = _plataforma()
    if clave not in _MOTORES:
        raise ErrorIALocal(f"La IA incluida aún no tiene motor para {clave[0]} {clave[1]}.")
    nombre, sha = _MOTORES[clave]
    url = f"https://github.com/ggml-org/llama.cpp/releases/download/{_VERSION_MOTOR}/{nombre}"
    archivo = carpeta() / "descargas" / nombre
    _descargar(url, archivo, sha, 0, progreso)
    destino = carpeta() / "motor"
    shutil.rmtree(destino, ignore_errors=True)
    destino.mkdir(parents=True)
    if nombre.endswith(".zip"):
        with zipfile.ZipFile(archivo) as z:
            z.extractall(destino)
    else:
        with tarfile.open(archivo) as t:
            t.extractall(destino, filter="data")
    archivo.unlink(missing_ok=True)
    binario = buscar_motor()
    if binario is None:
        raise ErrorIALocal("El motor descargado no contiene llama-server.")
    binario.chmod(binario.stat().st_mode | 0o755)
    return binario


# --------------------------------------------------------------------- estado

class _Estado:
    """Estado compartido entre el hilo de preparación, el agente y la interfaz."""

    def __init__(self):
        self.lock = threading.Lock()
        self.fase = "pendiente"   # pendiente|descargando|arrancando|lista|error
        self.progreso = 0.0
        self.mensaje = ""
        self.hilo = None
        self.proceso = None

    def fijar(self, fase, mensaje="", progreso=None):
        with self.lock:
            self.fase, self.mensaje = fase, mensaje
            if progreso is not None:
                self.progreso = progreso


_estado = _Estado()


def estado() -> dict:
    with _estado.lock:
        return {"fase": _estado.fase, "progreso": round(_estado.progreso, 3), "mensaje": _estado.mensaje,
                "modelo": MODELO["nombre"]}


def _url():
    return f"http://127.0.0.1:{PUERTO}"


def _responde() -> bool:
    try:
        return httpx.get(f"{_url()}/health", timeout=2.0).status_code == 200
    except httpx.HTTPError:
        return False


def _arrancar_motor(binario: Path):
    """Arranca llama-server y espera a que el modelo esté cargado."""
    if _responde():
        return  # ya en marcha (otra ventana de BuildAI o un arranque anterior)
    registro = (carpeta() / "motor.log").open("ab")
    argumentos = [
        str(binario), "-m", str(ruta_modelo()),
        "--host", "127.0.0.1", "--port", str(PUERTO),
        "-c", str(CONTEXTO),
        "-np", "1",                 # un solo usuario: todo el contexto para él
        "-ngl", "99",               # todas las capas a la GPU si caben (llama.cpp ajusta)
        "--no-mmproj",              # sin visión: ahorra ~0,7 GB; los planos van por herramientas
        # Sin "pensar" en voz alta: en un modelo de 4B dispara la latencia y
        # BuildAI no muestra ese razonamiento.
        "--reasoning-budget", "0",
    ]
    opciones = {}
    if os.name == "nt":
        opciones["creationflags"] = 0x08000000  # CREATE_NO_WINDOW: sin consola negra
    entorno = dict(os.environ)
    if os.name != "nt":
        # Las bibliotecas del motor viajan junto al binario.
        entorno["LD_LIBRARY_PATH"] = f"{binario.parent}:{entorno.get('LD_LIBRARY_PATH', '')}"
    _estado.proceso = subprocess.Popen(argumentos, stdout=registro, stderr=registro, env=entorno, **opciones)
    limite = time.time() + 300
    while time.time() < limite:
        if _estado.proceso.poll() is not None:
            raise ErrorIALocal(
                "El motor de la IA incluida se cerró al arrancar. Detalles en "
                f"{carpeta() / 'motor.log'} (suele ser falta de memoria)."
            )
        if _responde():
            return
        time.sleep(1.0)
    raise ErrorIALocal("El motor de la IA incluida tarda demasiado en cargar el modelo.")


def _parar():
    proceso = _estado.proceso
    if proceso is not None and proceso.poll() is None:
        proceso.terminate()
        try:
            proceso.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proceso.kill()


atexit.register(_parar)


def _preparar():
    try:
        binario = buscar_motor()
        if binario is None:
            _estado.fijar("descargando", "Descargando el motor de la IA incluida…", 0.0)
            binario = _instalar_motor()
        modelo = ruta_modelo()
        if not modelo.is_file():
            def avance(fraccion):
                _estado.fijar("descargando", f"Descargando la IA incluida ({MODELO['nombre']}, "
                                             f"2,7 GB, solo la primera vez)…", fraccion)
            avance(0.0)
            _descargar(MODELO["url"], modelo, MODELO["sha256"], MODELO["bytes"], avance)
        _estado.fijar("arrancando", "Cargando la IA incluida en memoria…", 1.0)
        _arrancar_motor(binario)
        _estado.fijar("lista", f"{NOMBRE} lista ({MODELO['nombre']}).", 1.0)
    except ErrorIALocal as exc:
        _estado.fijar("error", str(exc))
    except Exception as exc:  # nunca dejar el estado colgado en "descargando"
        _estado.fijar("error", f"No se pudo preparar la IA incluida: {exc}")


def preparar_en_segundo_plano():
    """Prepara (descarga y arranca) la IA incluida sin bloquear. Idempotente."""
    with _estado.lock:
        if _estado.hilo is not None and _estado.hilo.is_alive():
            return
        if _estado.fase == "lista" and _estado.proceso is not None and _estado.proceso.poll() is None:
            return
        _estado.hilo = threading.Thread(target=_preparar, daemon=True, name="ia-local")
        _estado.hilo.start()


def asegurar(espera_maxima=600.0) -> str:
    """URL base de la API de la IA incluida, ya en marcha.

    Si se está descargando, no se espera (serían minutos): se lanza un error
    con el progreso para que el usuario sepa cuánto falta. Si solo falta
    arrancar el motor, se espera a que cargue.
    """
    if _responde():
        _estado.fijar("lista", f"{NOMBRE} lista ({MODELO['nombre']}).", 1.0)
        return f"{_url()}/v1"
    preparar_en_segundo_plano()
    limite = time.time() + espera_maxima
    while time.time() < limite:
        actual = estado()
        if actual["fase"] == "lista":
            return f"{_url()}/v1"
        if actual["fase"] == "error":
            raise ErrorIALocal(actual["mensaje"])
        if actual["fase"] == "descargando":
            raise ErrorIALocal(
                f"La IA incluida se está preparando ({round(actual['progreso'] * 100)} %, solo la "
                "primera vez). Puedes seguir usando BuildAI cuando termine; el progreso está en el panel."
            )
        time.sleep(1.0)
    raise ErrorIALocal("La IA incluida no terminó de arrancar a tiempo.")
