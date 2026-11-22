"""Proveedores de modelos de IA disponibles en BuildAI."""

from ..config import MODELOS_POR_DEFECTO, OLLAMA_URL, PROVEEDORES
from . import claves as _claves
from .base import LlamadaHerramienta, RespuestaLLM, ErrorProveedor, ErrorContextoExcedido
from .openai_compat import ProveedorOpenAICompatible
from .anthropic_provider import ProveedorAnthropic


def _ollama_ve_imagenes(modelo: str) -> bool:
    """¿El modelo local acepta imágenes? Ollama lo declara en `capabilities`.

    Muchos modelos locales (qwen3, llama3.1…) son solo de texto. Si no se puede
    saber (Ollama antiguo o apagado) se asume que sí, como hasta ahora.
    """
    import httpx

    try:
        r = httpx.post(f"{OLLAMA_URL}/api/show", json={"model": modelo}, timeout=3.0)
        capacidades = r.json().get("capabilities")
    except Exception:
        return True
    return "vision" in capacidades if isinstance(capacidades, list) else True


def crear_proveedor(config: dict):
    """Devuelve el proveedor configurado, listo para conversar."""
    nombre = config["proveedor"]
    # También se limpian aquí las claves guardadas antes de que Ajustes las
    # limpiara al guardar: así una clave antigua con basura invisible funciona.
    try:
        clave = _claves.limpiar(config["claves"].get(nombre, ""))
    except _claves.ClaveInvalida as exc:
        raise ErrorProveedor(f"{exc} (Ajustes ⚙️ → {nombre})") from exc
    modelo = config["modelos"].get(nombre, "") or MODELOS_POR_DEFECTO.get(nombre, "")
    if not clave and PROVEEDORES.get(nombre, {}).get("requiere_clave", True):
        raise ErrorProveedor(
            f"Falta la clave de API del proveedor '{nombre}'. "
            "Abre Ajustes (⚙️) y pégala ahí."
        )
    if nombre == "local":
        from .. import ia_local

        try:
            base = ia_local.asegurar()
        except ia_local.ErrorIALocal as exc:
            raise ErrorProveedor(str(exc)) from exc
        # Timeout amplio: un modelo local en un PC modesto tarda en contestar.
        proveedor = ProveedorOpenAICompatible(base, "local", modelo, ia_local.NOMBRE, timeout=900.0)
        proveedor.ve_imagenes = False   # el motor arranca sin visión (--no-mmproj)
        proveedor.ligero = True         # instrucciones y herramientas compactas
        return proveedor
    if nombre == "anthropic":
        return ProveedorAnthropic(clave, modelo)
    if nombre == "ollama":
        # Endpoint compatible con OpenAI del Ollama local; la clave no se usa.
        # Timeout amplio: un modelo local puede tardar minutos en equipos modestos.
        proveedor = ProveedorOpenAICompatible(
            f"{OLLAMA_URL}/v1", "ollama", modelo, "ollama", timeout=600.0
        )
        proveedor.ve_imagenes = _ollama_ve_imagenes(modelo)
        # Por su API compatible con OpenAI, Ollama no deja ampliar el contexto:
        # con poca VRAM se queda en 4 096 tokens y RECHAZA (400) la petición
        # completa de BuildAI (~11 000). En modo ligero cabe: instrucciones y
        # herramientas compactas (~1 700 tokens) y la conversación recortada.
        proveedor.ligero = True
        proveedor.presupuesto = 7000
        return proveedor
    bases = {
        "openrouter": "https://openrouter.ai/api/v1",
        "openai": "https://api.openai.com/v1",
        "gemini": "https://generativelanguage.googleapis.com/v1beta/openai",
        "opencode": "https://opencode.ai/zen/v1",
    }
    proveedor = ProveedorOpenAICompatible(bases[nombre], clave, modelo, nombre)
    if nombre in ("openrouter", "opencode"):
        # Si el modelo gratuito elegido se satura, se puede seguir con otro
        # gratuito. Se consulta solo al hacer falta (el catálogo va por red).
        from .. import modelos as catalogo

        if catalogo.es_gratuito(nombre, modelo):
            proveedor.buscar_alternativas = lambda con_imagenes: catalogo.alternativas_gratuitas(
                nombre, modelo, con_imagenes)
    return proveedor


def probar_conexion(config: dict) -> str:
    """Comprueba de verdad la clave y el modelo configurados.

    Devuelve un texto de éxito o lanza ErrorProveedor con lo que hay que
    arreglar. Se usa al guardar Ajustes para que un error de configuración
    aparezca ahí, y no a mitad del primer encargo.
    """
    if config["proveedor"] == "local":
        from .. import ia_local

        estado = ia_local.estado()
        if estado["fase"] == "descargando":
            return (f"La IA incluida se está preparando ({round(estado['progreso'] * 100)} %). "
                    "Se activará sola al terminar.")
        ia_local.preparar_en_segundo_plano()
        return "IA incluida activada: funciona en tu ordenador, sin clave ni límites."
    proveedor = crear_proveedor(config)
    if config["proveedor"] == "ollama":
        import httpx

        try:
            instalados = httpx.get(f"{OLLAMA_URL}/api/tags", timeout=3.0).json().get("models") or []
        except Exception as exc:
            raise ErrorProveedor("Ollama no responde. ¿Está en marcha? Ábrelo (o ejecuta «ollama serve»).") from exc
        nombres = {m.get("name") for m in instalados} | {m.get("model") for m in instalados}
        if proveedor.modelo not in nombres and f"{proveedor.modelo}:latest" not in nombres:
            raise ErrorProveedor(
                f"El modelo «{proveedor.modelo}» no está instalado en Ollama. Descárgalo con "
                f"«ollama pull {proveedor.modelo}» o elige uno de la lista."
            )
        return f"Ollama en marcha y con el modelo «{proveedor.modelo}» instalado."
    return proveedor.probar()
