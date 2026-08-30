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

# Respaldo si no hay internet: modelos gratuitos con tools, verificados contra
# la API de OpenRouter el 2026-08-24. Un modelo retirado aquí deja la configuración
# del usuario rota, así que al tocar esta lista hay que comprobarla en vivo.
_RESPALDO_OPENROUTER = [
    "google/gemma-4-31b-it:free",
    "dots-studio/dots-3-note-preview:free",
    "nvidia/nemotron-3-ultra-550b-a55b:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
    "z-ai/glm-5.2:free",
]

_ESTATICOS = {
    "gemini": ["gemini-3.7-flash", "gemini-3.6-flash", "gemini-3.5-flash",
               "gemini-3.5-flash-lite", "gemini-3.1-pro"],
    "anthropic": ["claude-opus-5", "claude-sonnet-5", "claude-fable-5",
                  "claude-haiku-4-5-20251001"],
    "openai": ["gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna", "gpt-5.5", "gpt-5.2"],
}

# Respaldo de OpenCode Zen, verificado contra su API el 2026-08-24.
_RESPALDO_OPENCODE = [
    # Gratuitos
    "big-pickle",
    "deepseek-v4-flash-free",
    "nemotron-3-ultra-free",
    "nemotron-3.5-lightning-free",
    "laguna-s-2.1-free",
    "mimo-v2.5-free",
    "hy3-free",
    "x-preview-f-free",
    "muse-spark-1.2-contributor-free",
    # Top-tier (pago)
    "claude-opus-5",
    "claude-fable-5",
    "gpt-5.6-sol",
    "gpt-5.5-pro",
    "deepseek-v4-pro",
    # Mid-tier (pago)
    "claude-sonnet-5",
    "gpt-5.6-terra",
    "gemini-3.7-flash",
    "gemini-3.1-pro",
    "qwen3.6-plus",
    # Rápidos / código (pago)
    "claude-haiku-4-5",
    "gpt-5.6-luna",
    "gpt-5.3-codex",
    "deepseek-v4-flash",
]

# En OpenCode Zen los modelos sin coste llevan el sufijo "-free"; big-pickle es
# la excepción histórica. Su API no publica precios, así que no hay otra forma
# de distinguirlos.
_ZEN_GRATIS_SIN_SUFIJO = {"big-pickle"}


def _es_gratis_zen(id_modelo: str) -> bool:
    return id_modelo.endswith("-free") or id_modelo in _ZEN_GRATIS_SIN_SUFIJO


def _contexto_legible(tokens: int) -> str:
    """1000000 → «1M», 262144 → «262k». Vacío si no se conoce."""
    if not tokens:
        return ""
    if tokens >= 1_000_000:
        valor = tokens / 1_000_000
        return f"{valor:.1f}M".replace(".0M", "M")
    return f"{round(tokens / 1000)}k"

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
    modelos, con_vista = [], 0
    for m in libres:
        entradas = (m.get("architecture") or {}).get("input_modalities") or []
        ve_imagenes = "image" in entradas
        con_vista += ve_imagenes
        detalles = [d for d in (_contexto_legible(m.get("context_length") or 0),
                                "👁 ve imágenes" if ve_imagenes else "") if d]
        nombre = m.get("name") or m["id"]
        modelos.append({
            "id": m["id"],
            "nombre": f"{nombre} · {' · '.join(detalles)}" if detalles else nombre,
        })
    return {
        "disponible": True,
        "modelos": modelos,
        "nota": (
            f"{len(modelos)} modelos gratuitos que saben usar herramientas, de mayor a menor "
            f"contexto. {con_vista} pueden ver las fotos y planos que adjuntes (👁). "
            "Los gratuitos tienen un límite de mensajes al día por cuenta."
        ),
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
            "modelos": [
                {"id": m, "nombre": f"{m} · gratis" if _es_gratis_zen(m) else m}
                for m in _RESPALDO_OPENCODE
            ],
            "nota": "Sin conexión con OpenCode Zen: se muestra una lista guardada.",
        }
    ids = [m["id"] for m in datos if m.get("id")]
    # Los gratuitos primero: son los que la mayoría de usuarios va a querer.
    gratis = [i for i in ids if _es_gratis_zen(i)]
    pago = [i for i in ids if not _es_gratis_zen(i)]
    modelos = ([{"id": i, "nombre": f"{i} · gratis"} for i in gratis]
               + [{"id": i, "nombre": i} for i in pago])
    return {
        "disponible": True,
        "modelos": modelos,
        "nota": (
            f"{len(gratis)} modelos gratuitos (marcados «gratis», los primeros de la lista) "
            f"y {len(pago)} de pago según tu clave."
        ),
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
