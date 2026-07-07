"""Tipos comunes a todos los proveedores.

El historial de conversación usa un formato neutro (independiente del
proveedor) y cada adaptador lo traduce a su API:

    {"tipo": "usuario",   "texto": "..."}
    {"tipo": "asistente", "texto": "...", "llamadas": [LlamadaHerramienta...],
     "_raw": <bloques originales del proveedor, si los necesita>}
    {"tipo": "resultado", "id": "...", "nombre": "...", "contenido": "..."}
"""

from dataclasses import dataclass, field


class ErrorProveedor(Exception):
    """Error al hablar con el proveedor de IA, con mensaje apto para el usuario."""


@dataclass
class LlamadaHerramienta:
    id: str
    nombre: str
    argumentos: dict


@dataclass
class RespuestaLLM:
    texto: str = ""
    llamadas: list = field(default_factory=list)  # list[LlamadaHerramienta]
    raw: object = None  # bloques originales para reenviar al proveedor


class Proveedor:
    # Callable(texto) opcional que el agente asigna para mostrar al usuario
    # esperas y reintentos (p. ej. mientras se respeta un límite de peticiones).
    notificar = None

    def conversar(self, sistema: str, historial: list, herramientas: list) -> RespuestaLLM:
        """`herramientas` es una lista de dicts {nombre, descripcion, parametros(JSON Schema)}."""
        raise NotImplementedError
