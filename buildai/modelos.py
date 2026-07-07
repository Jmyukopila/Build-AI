"""Catálogo de modelos por proveedor.

- OpenRouter: consulta su API pública y devuelve solo los modelos GRATUITOS
  que soportan herramientas (imprescindible para controlar los programas).
- Ollama: escanea los modelos instalados en el Ollama local del usuario.
- Resto: sugerencias estáticas.

Los resultados de red se cachean para no repetir peticiones en cada apertura
de Ajustes.
"""

import time

import httpx

from . import config as cfg

# Respaldo si no hay internet: modelos gratuitos con tools verificados 2026-07
_RESPALDO_OPENROUTER = [
    "qwen/qwen3-coder:free",
    "openai/gpt-oss-120b:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
    "google/gemma-4-31b-it:free",
    "qwen/qwen3-next-80b-a3b-instruct:free",
]

_ESTATICOS = {
    "gemini": ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-2.5-pro"],
    "anthropic": ["claude-opus-4-8", "claude-sonnet-5", "claude-haiku-4-5-20251001"],
    "openai": ["gpt-4o", "gpt-4o-mini"],
    "opencode": ["big-pickle", "deepseek-v4-flash-free", "nemotron-3-ultra-free",
                  "north-mini-code-free", "mimo-v2.5-free", "hy3-free",
                  "claude-fable-5", "claude-sonnet-5", "claude-haiku-4-5",
                  "gpt-5.4", "gpt-5.4-mini", "deepseek-v4-flash"],
}

_RESPALDO_OPENCODE = [
    # Gratuitos
    "big-pickle",
    "deepseek-v4-flash-free",
    "nemotron-3-ultra-free",
    "north-mini-code-free",
    "mimo-v2.5-free",
    "hy3-free",
    # Top-tier (pago)
    "claude-fable-5",
    "claude-opus-4-8",
    "gpt-5.5",
    "gpt-5.5-pro",
    "deepseek-v4-pro",
    # Mid-tier (pago)
    "claude-sonnet-5",
    "gpt-5.4",
    "gpt-5.4-pro",
    "gemini-3.1-pro",
    "qwen3.6-plus",
    # Rápidos / código (pago)
    "claude-haiku-4-5",
    "gpt-5.4-mini",
    "gpt-5.3-codex",
    "deepseek-v4-flash",
]

_cache: dict = {}  # proveedor -> (marca_de_tiempo, resultado)
_CACHE_SEGUNDOS = 3600


def _openrouter_gratuitos() -> dict:
    try:
        r = httpx.get("https://openrouter.ai/api/v1/models", timeout=10.0)
        r.raise_for_status()
        datos = r.json()["data"]
    except Exception:
        return {
            "disponible": True,
            "modelos": [{"id": m, "nombre": m} for m in _RESPALDO_OPENROUTER],
            "nota": "Sin conexión con OpenRouter: se muestra una lista guardada de modelos gratuitos.",
        }
    libres = [
        m for m in datos
        if m.get("id", "").endswith(":free")
        and "tools" in (m.get("supported_parameters") or [])
    ]
    libres.sort(key=lambda m: -(m.get("context_length") or 0))
    return {
        "disponible": True,
        "modelos": [{"id": m["id"], "nombre": m.get("name") or m["id"]} for m in libres],
        "nota": f"{len(libres)} modelos gratuitos que saben usar herramientas, de mayor a menor contexto.",
    }


def _ollama_locales() -> dict:
    try:
        r = httpx.get(f"{cfg.OLLAMA_URL}/api/tags", timeout=2.0)
        r.raise_for_status()
        instalados = r.json().get("models") or []
    except Exception:
        return {
            "disponible": False,
            "modelos": [],
            "nota": (
                "Ollama no responde. Instálalo desde ollama.com/download, arráncalo y "
                "descarga un modelo (p. ej. «ollama pull qwen3»). Después reabre Ajustes."
            ),
        }
    modelos = []
    for m in instalados:
        nombre = m.get("name") or m.get("model") or ""
        detalle = (m.get("details") or {}).get("parameter_size") or ""
        modelos.append({"id": nombre, "nombre": f"{nombre} ({detalle})" if detalle else nombre})
    if not modelos:
        return {
            "disponible": True,
            "modelos": [],
            "nota": "Ollama está en marcha pero sin modelos. Descarga uno con «ollama pull qwen3».",
        }
    return {
        "disponible": True,
        "modelos": modelos,
        "nota": (
            f"{len(modelos)} modelo(s) locales detectados. Para manejar los programas, "
            "el modelo debe soportar herramientas (qwen3, llama3.1+, mistral…)."
        ),
    }


def _opencode_zen_models() -> dict:
    try:
        r = httpx.get("https://opencode.ai/zen/v1/models", timeout=10.0)
        r.raise_for_status()
        datos = r.json()["data"]
    except Exception:
        return {
            "disponible": True,
            "modelos": [{"id": m, "nombre": m} for m in _RESPALDO_OPENCODE],
            "nota": "Sin conexión con OpenCode Zen: se muestra una lista guardada.",
        }
    modelos = [{"id": m["id"], "nombre": m.get("id") or m["id"]} for m in datos]
    return {
        "disponible": True,
        "modelos": modelos,
        "nota": f"{len(modelos)} modelos disponibles en OpenCode Zen (precios según API Key).",
    }


def listar(proveedor: str) -> dict:
    """Devuelve {"disponible", "modelos": [{id, nombre}], "nota"} para el proveedor."""
    ahora = time.time()
    en_cache = _cache.get(proveedor)
    if en_cache and ahora - en_cache[0] < _CACHE_SEGUNDOS:
        return en_cache[1]

    if proveedor == "openrouter":
        resultado = _openrouter_gratuitos()
    elif proveedor == "ollama":
        resultado = _ollama_locales()
    elif proveedor == "opencode":
        resultado = _opencode_zen_models()
    elif proveedor in _ESTATICOS:
        resultado = {
            "disponible": True,
            "modelos": [{"id": m, "nombre": m} for m in _ESTATICOS[proveedor]],
            "nota": "Sugerencias; puedes escribir cualquier modelo del proveedor.",
        }
    else:
        return {"disponible": False, "modelos": [], "nota": f"Proveedor desconocido: {proveedor}"}

    # El estado de Ollama cambia al arrancarlo/descargar modelos: cache corta
    ttl = 5 if proveedor == "ollama" else _CACHE_SEGUNDOS
    _cache[proveedor] = (ahora - (_CACHE_SEGUNDOS - ttl), resultado)
    return resultado
