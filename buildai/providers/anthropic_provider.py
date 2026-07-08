"""Adaptador para la API de Anthropic (Claude) usando el SDK oficial."""

from .base import Proveedor, RespuestaLLM, LlamadaHerramienta, ErrorProveedor


class ProveedorAnthropic(Proveedor):
    def __init__(self, clave: str, modelo: str):
        self.clave = clave
        self.modelo = modelo or "claude-opus-4-8"

    def _convertir_historial(self, historial: list) -> list:
        mensajes = []
        for m in historial:
            if m["tipo"] == "usuario":
                if m.get("adjuntos"):
                    # Imágenes primero, luego el texto: Anthropic recomienda ese
                    # orden para que el modelo interprete mejor la petición.
                    contenido = [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": a["media_type"],
                                "data": a["datos"],
                            },
                        }
                        for a in m["adjuntos"]
                    ]
                    if m.get("texto"):
                        contenido.append({"type": "text", "text": m["texto"]})
                    mensajes.append({"role": "user", "content": contenido})
                else:
                    mensajes.append({"role": "user", "content": m["texto"]})
            elif m["tipo"] == "asistente":
                # Reenviamos los bloques originales (incluye thinking/tool_use)
                # tal cual los devolvió la API, como exige Anthropic.
                if m.get("_raw") is not None:
                    mensajes.append({"role": "assistant", "content": m["_raw"]})
                elif m.get("texto"):
                    mensajes.append({"role": "assistant", "content": m["texto"]})
            elif m["tipo"] == "resultado":
                mensajes.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": m["id"],
                                "content": m["contenido"],
                            }
                        ],
                    }
                )
        return mensajes

    def conversar(self, sistema: str, historial: list, herramientas: list) -> RespuestaLLM:
        import anthropic

        cliente = anthropic.Anthropic(api_key=self.clave)
        try:
            respuesta = cliente.messages.create(
                model=self.modelo,
                max_tokens=16000,
                thinking={"type": "adaptive"},
                system=sistema,
                tools=[
                    {
                        "name": h["nombre"],
                        "description": h["descripcion"],
                        "input_schema": h["parametros"],
                    }
                    for h in herramientas
                ],
                messages=self._convertir_historial(historial),
            )
        except anthropic.AuthenticationError as exc:
            raise ErrorProveedor(
                "La clave de API de Anthropic no es válida. Revísala en Ajustes (⚙️)."
            ) from exc
        except anthropic.RateLimitError as exc:
            raise ErrorProveedor(
                "Anthropic está limitando las peticiones. Espera un momento y reintenta."
            ) from exc
        except anthropic.APIStatusError as exc:
            raise ErrorProveedor(f"Error {exc.status_code} de Anthropic: {exc.message}") from exc
        except anthropic.APIConnectionError as exc:
            raise ErrorProveedor(f"No se pudo contactar con Anthropic: {exc}") from exc

        if respuesta.stop_reason == "refusal":
            raise ErrorProveedor(
                "Claude rechazó esta petición por motivos de seguridad. "
                "Prueba a reformularla."
            )

        texto = ""
        llamadas = []
        for bloque in respuesta.content:
            if bloque.type == "text":
                texto += bloque.text
            elif bloque.type == "tool_use":
                llamadas.append(
                    LlamadaHerramienta(id=bloque.id, nombre=bloque.name, argumentos=dict(bloque.input))
                )
        # Guardamos los bloques originales para reenviarlos en el siguiente turno
        raw = [b.model_dump(exclude_none=True) for b in respuesta.content]
        return RespuestaLLM(texto=texto, llamadas=llamadas, raw=raw)
