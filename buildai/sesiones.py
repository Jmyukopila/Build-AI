"""Historial de sesiones: cada conversación se guarda en disco y puede retomarse.

Las sesiones viven en `~/.buildai/sesiones/` (ver `rutas.py`), un JSON por
conversación, con el historial en el formato neutro de providers.base.
"""

import json
import threading
import time
import uuid
from pathlib import Path

from . import rutas
from .agent import renders_en_resultado
from .connectors import buscar_herramienta
from .providers.base import LlamadaHerramienta

TITULO_MAX = 60

_lock = threading.Lock()


def nuevo_id() -> str:
    return uuid.uuid4().hex[:12]


def _ruta(sesion_id: str) -> Path:
    # El id viene de nuevo_id() o de un listado propio; se valida igualmente
    # para que un id manipulado no pueda salir de la carpeta de sesiones.
    if not sesion_id.isalnum():
        raise ValueError(f"Id de sesión no válido: {sesion_id!r}")
    return rutas.carpeta_sesiones() / f"{sesion_id}.json"


def _serializar(historial: list) -> list:
    entradas = []
    for m in historial:
        m2 = dict(m)
        if m2.get("llamadas"):
            m2["llamadas"] = [
                {"id": ll.id, "nombre": ll.nombre, "argumentos": ll.argumentos}
                for ll in m2["llamadas"]
            ]
        entradas.append(m2)
    return entradas


def _deserializar(entradas: list) -> list:
    historial = []
    for m in entradas:
        m2 = dict(m)
        if m2.get("llamadas"):
            m2["llamadas"] = [LlamadaHerramienta(**ll) for ll in m2["llamadas"]]
        historial.append(m2)
    return historial


def _titulo(historial: list) -> str:
    primero = next((m["texto"] for m in historial if m["tipo"] == "usuario"), "")
    primero = " ".join(primero.split())
    if len(primero) > TITULO_MAX:
        primero = primero[:TITULO_MAX].rstrip() + "…"
    return primero or "Conversación sin título"


def guardar(sesion_id: str, historial: list) -> None:
    """Guarda (o actualiza) la sesión. Las conversaciones vacías no se guardan."""
    if not historial:
        return
    ruta = _ruta(sesion_id)
    with _lock:
        creada = time.time()
        if ruta.exists():
            try:
                creada = json.loads(ruta.read_text(encoding="utf-8")).get("creada", creada)
            except (json.JSONDecodeError, OSError):
                pass
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(
            json.dumps(
                {
                    "id": sesion_id,
                    "titulo": _titulo(historial),
                    "creada": creada,
                    "actualizada": time.time(),
                    "historial": _serializar(historial),
                },
                ensure_ascii=False,
                default=str,
            ),
            encoding="utf-8",
        )


def cargar(sesion_id: str):
    """Devuelve el historial de la sesión (formato neutro), o None si no existe."""
    try:
        ruta = _ruta(sesion_id)
    except ValueError:
        return None
    with _lock:
        if not ruta.exists():
            return None
        try:
            datos = json.loads(ruta.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
    return _deserializar(datos.get("historial") or [])


def listar() -> list:
    """Sesiones guardadas, de la más reciente a la más antigua."""
    resultado = []
    carpeta = rutas.carpeta_sesiones()
    with _lock:
        for ruta in carpeta.glob("*.json") if carpeta.exists() else []:
            try:
                datos = json.loads(ruta.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            resultado.append(
                {
                    "id": datos.get("id") or ruta.stem,
                    "titulo": datos.get("titulo") or "Conversación sin título",
                    "actualizada": datos.get("actualizada") or 0,
                    "mensajes": sum(
                        1 for m in datos.get("historial") or [] if m.get("tipo") == "usuario"
                    ),
                }
            )
    resultado.sort(key=lambda s: -s["actualizada"])
    return resultado


def borrar(sesion_id: str) -> None:
    try:
        ruta = _ruta(sesion_id)
    except ValueError:
        return
    with _lock:
        ruta.unlink(missing_ok=True)


def para_ui(historial: list) -> list:
    """Convierte el historial neutro en la lista de eventos que pinta la interfaz."""
    eventos = []
    for m in historial:
        if m["tipo"] == "usuario":
            eventos.append({"tipo": "usuario", "texto": m["texto"]})
        elif m["tipo"] == "resultado":
            for archivo in renders_en_resultado(m.get("contenido", "")):
                eventos.append({"tipo": "render", "archivo": archivo})
        elif m["tipo"] == "asistente":
            if m.get("texto"):
                eventos.append({"tipo": "respuesta", "texto": m["texto"]})
            for ll in m.get("llamadas") or []:
                encontrada = buscar_herramienta(ll.nombre)
                eventos.append(
                    {
                        "tipo": "herramienta",
                        "programa": encontrada[0].nombre if encontrada else "?",
                        "nombre": ll.nombre,
                        "detalle": str(
                            ll.argumentos.get("codigo") or ll.argumentos.get("orden") or ""
                        )[:400],
                    }
                )
    return eventos
