"""Proveedores de modelos de IA disponibles en BuildAI."""

from ..config import OLLAMA_URL, PROVEEDORES
from .base import LlamadaHerramienta, RespuestaLLM, ErrorProveedor
from .openai_compat import ProveedorOpenAICompatible
from .anthropic_provider import ProveedorAnthropic


def crear_proveedor(config: dict):
    """Devuelve el proveedor configurado, listo para conversar."""
    nombre = config["proveedor"]
    clave = config["claves"].get(nombre, "").strip()
    modelo = config["modelos"].get(nombre, "")
    if not clave and PROVEEDORES.get(nombre, {}).get("requiere_clave", True):
        raise ErrorProveedor(
            f"Falta la clave de API del proveedor '{nombre}'. "
            "Abre Ajustes (⚙️) y pégala ahí."
        )
    if nombre == "anthropic":
        return ProveedorAnthropic(clave, modelo)
    if nombre == "ollama":
        # Endpoint compatible con OpenAI del Ollama local; la clave no se usa.
        # Timeout amplio: un modelo local puede tardar minutos en equipos modestos.
        return ProveedorOpenAICompatible(
            f"{OLLAMA_URL}/v1", "ollama", modelo, "ollama", timeout=600.0
        )
    bases = {
        "openrouter": "https://openrouter.ai/api/v1",
        "openai": "https://api.openai.com/v1",
        "gemini": "https://generativelanguage.googleapis.com/v1beta/openai",
        "opencode": "https://opencode.ai/zen/v1",
    }
    return ProveedorOpenAICompatible(bases[nombre], clave, modelo, nombre)
