"""Adaptador para APIs compatibles con Chat Completions de OpenAI.

Cubre OpenRouter, OpenAI y el endpoint de compatibilidad de Gemini.
"""

import json
import time

import httpx

from .base import Proveedor, RespuestaLLM, LlamadaHerramienta, ErrorProveedor

# Reintentos ante errores transitorios (429, 5xx, cortes de red): las tareas
# largas con modelos gratuitos los sufren constantemente y abortar el turno
# entero por uno de ellos tira todo el trabajo previo.
_MAX_REINTENTOS = 5
_ESPERA_INICIAL = 5.0
_ESPERA_MAXIMA = 60.0

# Los modelos :free de OpenRouter admiten ~20 peticiones/minuto; espaciarlas
# evita quemar el cupo provocando los propios 429.
_INTERVALO_FREE = 3.5
_ultima_peticion = 0.0


class ProveedorOpenAICompatible(Proveedor):
    def __init__(self, base_url: str, clave: str, modelo: str, nombre: str, timeout: float = 180.0):
        self.base_url = base_url.rstrip("/")
        self.clave = clave
        self.modelo = modelo
        self.nombre = nombre
        self.timeout = timeout

    def _cabeceras(self) -> dict:
        cabeceras = {
            "Authorization": f"Bearer {self.clave}",
            "Content-Type": "application/json",
        }
        if self.nombre == "openrouter":
            # OpenRouter usa estas cabeceras para atribuir el tráfico
            cabeceras["HTTP-Referer"] = "https://github.com/buildai"
            cabeceras["X-Title"] = "BuildAI"
        return cabeceras

    def _convertir_historial(self, sistema: str, historial: list) -> list:
        mensajes = [{"role": "system", "content": sistema}]
        for m in historial:
            if m["tipo"] == "usuario":
                if m.get("adjuntos"):
                    contenido = []
                    if m.get("texto"):
                        contenido.append({"type": "text", "text": m["texto"]})
                    for a in m["adjuntos"]:
                        contenido.append(
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{a['media_type']};base64,{a['datos']}"
                                },
                            }
                        )
                    mensajes.append({"role": "user", "content": contenido})
                else:
                    mensajes.append({"role": "user", "content": m["texto"]})
            elif m["tipo"] == "asistente":
                msg = {"role": "assistant", "content": m.get("texto") or None}
                if m.get("llamadas"):
                    msg["tool_calls"] = [
                        {
                            "id": ll.id,
                            "type": "function",
                            "function": {
                                "name": ll.nombre,
                                "arguments": json.dumps(ll.argumentos, ensure_ascii=False),
                            },
                        }
                        for ll in m["llamadas"]
                    ]
                mensajes.append(msg)
            elif m["tipo"] == "resultado":
                mensajes.append(
                    {"role": "tool", "tool_call_id": m["id"], "content": m["contenido"]}
                )
        return mensajes

    def _avisar(self, texto: str) -> None:
        if self.notificar:
            try:
                self.notificar(texto)
            except Exception:
                pass

    def _respetar_ritmo(self) -> None:
        global _ultima_peticion
        if self.nombre == "openrouter" and self.modelo.endswith(":free"):
            pausa = _INTERVALO_FREE - (time.monotonic() - _ultima_peticion)
            if pausa > 0:
                time.sleep(pausa)
        _ultima_peticion = time.monotonic()

    @staticmethod
    def _espera_reintento(respuesta, espera: float) -> float:
        try:
            return min(float(respuesta.headers.get("Retry-After", "")), _ESPERA_MAXIMA)
        except (TypeError, ValueError):
            return espera

    def _mensaje_agotado(self, codigo: int) -> str:
        if codigo != 429:
            return (
                f"{self.nombre} sigue devolviendo el error {codigo} tras "
                f"{_MAX_REINTENTOS} reintentos. Espera unos minutos y vuelve a intentarlo."
            )
        mensaje = (
            f"{self.nombre} sigue limitando las peticiones (429) tras "
            f"{_MAX_REINTENTOS} reintentos con espera."
        )
        if self.nombre == "openrouter" and self.modelo.endswith(":free"):
            mensaje += (
                " Los modelos gratuitos tienen además un cupo diario de peticiones: "
                "prueba con otro modelo ':free' en Ajustes (⚙️) o usa Ollama local, "
                "que no tiene límites."
            )
        else:
            mensaje += " Espera unos minutos y vuelve a intentarlo."
        return mensaje

    def conversar(self, sistema: str, historial: list, herramientas: list) -> RespuestaLLM:
        cuerpo = {
            "model": self.modelo,
            "messages": self._convertir_historial(sistema, historial),
        }
        if herramientas:
            cuerpo["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": h["nombre"],
                        "description": h["descripcion"],
                        "parameters": h["parametros"],
                    },
                }
                for h in herramientas
            ]

        espera = _ESPERA_INICIAL
        datos = None
        for intento in range(_MAX_REINTENTOS + 1):
            ultimo = intento == _MAX_REINTENTOS
            self._respetar_ritmo()
            try:
                respuesta = httpx.post(
                    f"{self.base_url}/chat/completions",
                    headers=self._cabeceras(),
                    json=cuerpo,
                    timeout=self.timeout,
                )
            except httpx.HTTPError as exc:
                if self.nombre == "ollama":
                    raise ErrorProveedor(
                        "No se pudo hablar con Ollama. ¿Está en marcha? Ábrelo (o ejecuta "
                        "«ollama serve») y reintenta."
                    ) from exc
                if not ultimo:
                    self._avisar(
                        f"Sin respuesta de {self.nombre}; reintento en {int(espera)} s "
                        f"({intento + 1}/{_MAX_REINTENTOS})…"
                    )
                    time.sleep(espera)
                    espera = min(espera * 2, _ESPERA_MAXIMA)
                    continue
                raise ErrorProveedor(
                    f"No se pudo contactar con {self.nombre} tras varios intentos: {exc}"
                ) from exc

            if respuesta.status_code == 401:
                raise ErrorProveedor(
                    f"La clave de API de {self.nombre} no es válida. Revísala en Ajustes (⚙️)."
                )

            codigo = respuesta.status_code
            error_datos = None
            if codigo < 400:
                try:
                    datos = respuesta.json()
                except ValueError:
                    datos = None
                    codigo = 502  # respuesta ilegible: tratarla como fallo transitorio
                if datos and "error" in datos:  # OpenRouter puede devolver 200 con error dentro
                    error_datos = datos["error"]
                    try:
                        codigo = int(error_datos.get("code"))
                    except (TypeError, ValueError):
                        codigo = 400

            if codigo == 429 or codigo == 408 or codigo >= 500:
                if not ultimo:
                    pausa = self._espera_reintento(respuesta, espera)
                    self._avisar(
                        f"{self.nombre} está saturado ({codigo}); espero {int(pausa)} s "
                        f"y reintento ({intento + 1}/{_MAX_REINTENTOS})…"
                    )
                    time.sleep(pausa)
                    espera = min(espera * 2, _ESPERA_MAXIMA)
                    continue
                raise ErrorProveedor(self._mensaje_agotado(codigo))
            if error_datos is not None:
                raise ErrorProveedor(
                    f"Error de {self.nombre}: {error_datos.get('message', error_datos)}"
                )
            if codigo >= 400:
                raise ErrorProveedor(
                    f"Error {codigo} de {self.nombre}: {respuesta.text[:400]}"
                )
            break

        mensaje = datos["choices"][0]["message"]
        llamadas = []
        for tc in mensaje.get("tool_calls") or []:
            try:
                argumentos = json.loads(tc["function"].get("arguments") or "{}")
            except json.JSONDecodeError:
                argumentos = {}
            llamadas.append(
                LlamadaHerramienta(
                    id=tc.get("id") or f"llamada_{len(llamadas)}",
                    nombre=tc["function"]["name"],
                    argumentos=argumentos,
                )
            )
        return RespuestaLLM(texto=mensaje.get("content") or "", llamadas=llamadas)
