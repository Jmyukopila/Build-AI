"""Adaptador para la API de Anthropic (Claude) usando el SDK oficial."""

import re

from .base import Proveedor, RespuestaLLM, LlamadaHerramienta, ErrorProveedor

MODELO_POR_DEFECTO = "claude-opus-5-5"

# claude-<familia>-<mayor>[-<menor>]: opus-4-8, sonnet-5-5, haiku-4-5, opus-5…
_VERSION = re.compile(r"^claude-(opus|sonnet|haiku)-(\d+)(?:-(\d+))?(?:-\d{8})?$")


def admite_pensamiento_adaptativo(modelo: str) -> bool:
    """¿Acepta el modelo thinking={"type": "adaptive"}?

    Lo admiten Claude 4.6 en adelante (y Fable/Mythos); los anteriores
    (Haiku 4.5, Sonnet/Opus 4.5, Claude 3…) devuelven un 400 si se les manda.
    Un modelo con nombre desconocido se trata como nuevo: los futuros también
    lo admitirán, y es el formato vigente.
    """
    modelo = (modelo or "").lower()
    if modelo.startswith("claude-3"):
        return False
    coincide = _VERSION.match(modelo)
    if not coincide:
        return True
    mayor = int(coincide.group(2))
    menor = int(coincide.group(3)) if coincide.group(3) and len(coincide.group(3)) <= 2 else 0
    return (mayor, menor) >= (4, 6)


class ProveedorAnthropic(Proveedor):
    def __init__(self, clave: str, modelo: str):
        self.clave = clave
        self.modelo = modelo or MODELO_POR_DEFECTO

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
                contenido = m["contenido"]
                if m.get("imagenes_datos"):
                    # tool_result admite imágenes: Claude ve su render o la foto
                    # de referencia junto al texto que la acompaña.
                    contenido = [{"type": "text", "text": m["contenido"]}] + [
                        {"type": "image", "source": {"type": "base64", "media_type": i["media_type"], "data": i["datos"]}}
                        for i in m["imagenes_datos"]
                    ]
                bloque = {"type": "tool_result", "tool_use_id": m["id"], "content": contenido}
                # Varios resultados seguidos (llamadas en paralelo) van en un
                # solo mensaje de usuario, como exige la API.
                previo = mensajes[-1] if mensajes else None
                if (previo and previo["role"] == "user" and isinstance(previo["content"], list)
                        and all(b.get("type") == "tool_result" for b in previo["content"])):
                    previo["content"].append(bloque)
                else:
                    mensajes.append({"role": "user", "content": [bloque]})
        return mensajes

    def _traducir_error(self, exc):
        """Errores del SDK → mensaje para el usuario, del más concreto al más general."""
        import anthropic

        if isinstance(exc, anthropic.AuthenticationError):
            return ErrorProveedor("La clave de API de Anthropic no es válida. Revísala en Ajustes (⚙️).")
        if isinstance(exc, anthropic.PermissionDeniedError):
            return ErrorProveedor(
                f"Tu clave de Anthropic no tiene permiso para usar «{self.modelo}». Elige otro "
                "modelo en Ajustes (⚙️) o revisa los permisos de la clave en platform.claude.com."
            )
        if isinstance(exc, anthropic.NotFoundError):
            return ErrorProveedor(
                f"El modelo «{self.modelo}» no existe en Anthropic. Elige uno de la lista en Ajustes (⚙️)."
            )
        if isinstance(exc, anthropic.RateLimitError):
            return ErrorProveedor("Anthropic está limitando las peticiones. Espera un momento y reintenta.")
        if isinstance(exc, anthropic.BadRequestError):
            mensaje = str(getattr(exc, "message", exc))
            if "credit balance" in mensaje.lower():
                return ErrorProveedor(
                    "Tu cuenta de Anthropic no tiene saldo. Añade crédito en platform.claude.com "
                    "(Billing) o usa un proveedor gratuito como OpenRouter u Ollama."
                )
            return ErrorProveedor(f"Anthropic rechazó la petición: {mensaje}")
        if isinstance(exc, anthropic.APIStatusError):
            if exc.status_code >= 500:
                return ErrorProveedor(
                    f"Anthropic tiene problemas ahora mismo (error {exc.status_code}). Prueba en unos minutos."
                )
            return ErrorProveedor(f"Error {exc.status_code} de Anthropic: {exc.message}")
        if isinstance(exc, anthropic.APIConnectionError):
            return ErrorProveedor(f"No se pudo contactar con Anthropic. ¿Hay conexión a internet? ({exc})")
        if isinstance(exc, (UnicodeEncodeError, ValueError)):
            return ErrorProveedor(
                "La clave de Anthropic guardada tiene caracteres no válidos (se colaron al copiarla). "
                "Pégala de nuevo en Ajustes (⚙️)."
            )
        return ErrorProveedor(f"Error inesperado con Anthropic: {exc}")

    def probar(self) -> str:
        """Comprueba la clave y que el modelo existe, sin gastar tokens (API de Modelos)."""
        import anthropic

        cliente = anthropic.Anthropic(api_key=self.clave, max_retries=1, timeout=30.0)
        try:
            cliente.models.retrieve(self.modelo)
        except Exception as exc:
            raise self._traducir_error(exc) from exc
        return f"Conectado con Anthropic: el modelo «{self.modelo}» está disponible para tu clave."

    def conversar(self, sistema: str, historial: list, herramientas: list) -> RespuestaLLM:
        import anthropic

        cliente = anthropic.Anthropic(api_key=self.clave)
        opciones = {}
        if admite_pensamiento_adaptativo(self.modelo):
            opciones["thinking"] = {"type": "adaptive"}
        try:
            respuesta = cliente.messages.create(
                model=self.modelo,
                max_tokens=16000,
                **opciones,
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
        except Exception as exc:
            raise self._traducir_error(exc) from exc

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
