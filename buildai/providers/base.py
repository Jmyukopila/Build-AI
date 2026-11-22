"""Tipos comunes a todos los proveedores.

El historial de conversación usa un formato neutro (independiente del
proveedor) y cada adaptador lo traduce a su API:

    {"tipo": "usuario",   "texto": "...", "adjuntos": [{media_type, datos}]}
    {"tipo": "asistente", "texto": "...", "llamadas": [LlamadaHerramienta...],
     "_raw": <bloques originales del proveedor, si los necesita>}
    {"tipo": "resultado", "id": "...", "nombre": "...", "contenido": "...",
     "imagenes_datos": [{media_type, datos}]}

`adjuntos` es opcional: lista de imágenes que el usuario adjuntó, cada una
{"media_type": "image/jpeg", "datos": "<base64 sin el prefijo data:>"}. Los
vídeos llegan ya convertidos a fotogramas (imágenes) desde la interfaz. Cada
adaptador las traduce al formato de visión de su API.

`imagenes_datos` (opcional, solo en la vista que prepara el agente) son las
imágenes que devolvió la herramienta: un render, una foto de referencia, el
control de un plano. Cada adaptador las hace llegar al modelo como pueda.
"""

from dataclasses import dataclass, field


class ErrorProveedor(Exception):
    """Error al hablar con el proveedor de IA, con mensaje apto para el usuario."""


class ErrorContextoExcedido(ErrorProveedor):
    """La petición no cabe en el contexto del modelo (típico de modelos locales).

    Es recuperable: el agente puede reintentar con menos conversación."""


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
    # False en modelos sin visión: el agente no les manda imágenes de
    # herramientas (algunos servidores rechazan la petición entera si llegan).
    ve_imagenes = True

    def conversar(self, sistema: str, historial: list, herramientas: list) -> RespuestaLLM:
        """`herramientas` es una lista de dicts {nombre, descripcion, parametros(JSON Schema)}."""
        raise NotImplementedError
