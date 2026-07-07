"""Configuración persistente de BuildAI (proveedor de IA, claves, modelos)."""

import json
import threading

from . import rutas

# Ollama local (gratis, sin clave). Escanea los modelos con /api/tags.
OLLAMA_URL = "http://127.0.0.1:11434"

# Modelos por defecto de cada proveedor. El usuario puede cambiarlos en Ajustes.
MODELOS_POR_DEFECTO = {
    "openrouter": "qwen/qwen3-coder:free",
    "ollama": "qwen3",
    "anthropic": "claude-opus-4-8",
    "openai": "gpt-4o",
    "gemini": "gemini-2.0-flash",
    "opencode": "big-pickle",
}

# Modelos retirados por el proveedor → sustituto, para no dejar configs rotas
_MODELOS_MIGRADOS = {
    "deepseek/deepseek-chat-v3.1:free": "qwen/qwen3-coder:free",
}

PROVEEDORES = {
    "openrouter": {
        "nombre": "OpenRouter (modelos gratuitos)",
        "url_clave": "https://openrouter.ai/keys",
        "url_texto": "Obtener clave ↗",
        "requiere_clave": True,
        "oauth_disponible": False,
        "nota": "Crea una cuenta gratuita en openrouter.ai y genera una clave. "
                "Los modelos con ':free' no tienen coste.",
    },
    "ollama": {
        "nombre": "Ollama (IA local, gratis)",
        "url_clave": "https://ollama.com/download",
        "url_texto": "Descargar Ollama ↗",
        "requiere_clave": False,
        "oauth_disponible": False,
        "nota": "Ejecuta modelos en tu propio ordenador: gratis, sin clave y sin "
                "enviar nada a internet. BuildAI detecta tus modelos instalados.",
    },
    "anthropic": {
        "nombre": "Anthropic (Claude)",
        "url_clave": "https://platform.claude.com/",
        "url_texto": "Obtener clave ↗",
        "requiere_clave": True,
        "oauth_disponible": False,
        "nota": "Requiere una clave de API de pago de platform.claude.com.",
    },
    "openai": {
        "nombre": "OpenAI (GPT)",
        "url_clave": "https://platform.openai.com/api-keys",
        "url_texto": "Obtener clave ↗",
        "requiere_clave": True,
        "oauth_disponible": False,
        "nota": "Requiere una clave de API de pago de platform.openai.com.",
    },
    "gemini": {
        "nombre": "Google (Gemini)",
        "url_clave": "https://aistudio.google.com/apikey",
        "url_texto": "Obtener clave ↗",
        "requiere_clave": True,
        "oauth_disponible": False,
        "nota": "Google AI Studio ofrece una clave con nivel gratuito.",
    },
    "opencode": {
        "nombre": "OpenCode Zen (modelos gratuitos)",
        "url_clave": "https://opencode.ai/zen",
        "url_texto": "Obtener clave ↗",
        "requiere_clave": True,
        "oauth_disponible": True,
        "oauth_url": "https://opencode.ai/zen/oauth/authorize",
        "nota": "Modelos curados para agentes, con gratuitos como Big Pickle, "
                "DeepSeek V4 Flash Free. Crea cuenta en opencode.ai/zen → API Keys.",
    },
}

_CONFIG_DEFECTO = {
    "proveedor": "openrouter",
    "claves": {p: "" for p in PROVEEDORES},
    "modelos": dict(MODELOS_POR_DEFECTO),
}

_lock = threading.Lock()


def cargar() -> dict:
    with _lock:
        ruta = rutas.ruta_config()
        if ruta.exists():
            try:
                datos = json.loads(ruta.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                datos = {}
        else:
            datos = {}
    # Rellenar campos que falten sin perder los existentes
    config = json.loads(json.dumps(_CONFIG_DEFECTO))
    config.update({k: v for k, v in datos.items() if k in config and not isinstance(v, dict)})
    for seccion in ("claves", "modelos"):
        config[seccion].update(datos.get(seccion, {}))
    if datos.get("proveedor") in PROVEEDORES:
        config["proveedor"] = datos["proveedor"]
    for proveedor, modelo in config["modelos"].items():
        if modelo in _MODELOS_MIGRADOS:
            config["modelos"][proveedor] = _MODELOS_MIGRADOS[modelo]
    return config


def guardar(config: dict) -> None:
    with _lock:
        ruta = rutas.ruta_config()
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(
            json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8"
        )


def clave_activa(config: dict | None = None) -> str:
    config = config or cargar()
    return config["claves"].get(config["proveedor"], "")


def proveedor_listo(config: dict | None = None) -> bool:
    """True si el proveedor activo puede usarse (tiene clave o no la necesita)."""
    config = config or cargar()
    if not PROVEEDORES[config["proveedor"]].get("requiere_clave", True):
        return True
    return bool(clave_activa(config))


def modelo_activo(config: dict | None = None) -> str:
    config = config or cargar()
    return config["modelos"].get(config["proveedor"]) or MODELOS_POR_DEFECTO[config["proveedor"]]
