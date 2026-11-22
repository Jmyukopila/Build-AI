"""Adaptador para APIs compatibles con Chat Completions de OpenAI.

Cubre OpenRouter, OpenAI y el endpoint de compatibilidad de Gemini.
"""

import json
import time

import httpx

from .base import Proveedor, RespuestaLLM, LlamadaHerramienta, ErrorProveedor, ErrorContextoExcedido

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


# Fallos transitorios seguidos de un mismo modelo gratuito antes de pasar a
# otro: los gratuitos se saturan a menudo, y esperar minutos a que se libere
# uno cuando hay otros libres solo hace esperar al usuario.
_FALLOS_ANTES_DE_CAMBIAR = 2
# Un 429 cuyo cupo se renueva en más de esto no es "espera un poco": es el
# cupo diario de modelos gratuitos (50 o 1000 peticiones al día en OpenRouter).
_CUPO_LARGO_SEGUNDOS = 300


class ProveedorOpenAICompatible(Proveedor):
    def __init__(self, base_url: str, clave: str, modelo: str, nombre: str, timeout: float = 180.0):
        self.base_url = base_url.rstrip("/")
        self.clave = clave
        self.modelo = modelo
        self.nombre = nombre
        self.timeout = timeout
        # Callable(ve_imagenes: bool) -> [ids de modelos gratuitos alternativos],
        # o None si no hay que cambiar de modelo nunca (modelos de pago, Ollama).
        self.buscar_alternativas = None

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

    @staticmethod
    def _mensaje_imagenes(imagenes: list) -> dict:
        """Las imágenes de herramientas, como mensaje de usuario.

        En Chat Completions un mensaje "tool" solo admite texto, y entre las
        tool_calls de un asistente y sus respuestas no puede colarse nada: por
        eso van en un mensaje de usuario justo DESPUÉS de todos los resultados.
        """
        contenido = [{"type": "text", "text": "Imágenes devueltas por las herramientas anteriores:"}]
        for i in imagenes:
            contenido.append({"type": "image_url", "image_url": {"url": f"data:{i['media_type']};base64,{i['datos']}"}})
        return {"role": "user", "content": contenido}

    def _convertir_historial(self, sistema: str, historial: list) -> list:
        mensajes = [{"role": "system", "content": sistema}]
        pendientes = []  # imágenes de los resultados en curso
        for m in historial:
            if m["tipo"] != "resultado" and pendientes:
                mensajes.append(self._mensaje_imagenes(pendientes))
                pendientes = []
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
                pendientes.extend(m.get("imagenes_datos") or [])
        if pendientes:
            mensajes.append(self._mensaje_imagenes(pendientes))
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

    def _cupo_de_openrouter(self, respuesta):
        """(restantes, segundos_hasta_renovar) si el 429 es un límite PROPIO de
        OpenRouter (free-models o clave), o None si viene del proveedor del modelo.

        Según su documentación, solo sus propios límites llevan las cabeceras
        X-RateLimit-*; X-RateLimit-Reset es una marca de tiempo en milisegundos.
        """
        if self.nombre != "openrouter":
            return None
        cabeceras = respuesta.headers
        if "X-RateLimit-Remaining" not in cabeceras:
            return None
        try:
            restantes = int(float(cabeceras["X-RateLimit-Remaining"]))
            renovacion = float(cabeceras.get("X-RateLimit-Reset", "0")) / 1000.0
        except (TypeError, ValueError):
            return None
        return restantes, max(0.0, renovacion - time.time())

    def _mensaje_cupo_diario(self, segundos) -> str:
        cuando = ""
        if segundos is not None:
            cuando = f" (se renuevan hacia las {time.strftime('%H:%M', time.localtime(time.time() + segundos))})"
        return (
            f"Has gastado las peticiones gratuitas de hoy en OpenRouter{cuando}. "
            "No es que esté saturado: cada paso de una tarea cuenta como una petición, y sin crédito "
            "comprado el cupo es de 50 al día. Opciones: comprar 10 $ de crédito en openrouter.ai lo "
            "sube a 1 000 al día (sigues usando los modelos gratis), usar Ollama en tu ordenador "
            "(sin límites) u otro proveedor en Ajustes (⚙️)."
        )

    @staticmethod
    def _pide_imagenes(cuerpo: dict) -> bool:
        for m in cuerpo.get("messages", []):
            contenido = m.get("content")
            if isinstance(contenido, list) and any(b.get("type") == "image_url" for b in contenido):
                return True
        return False

    def _cambiar_de_modelo(self, cuerpo: dict, codigo: int) -> bool:
        """Pasa al siguiente modelo gratuito libre. False si no queda ninguno."""
        if self.buscar_alternativas is None:
            return False
        if not hasattr(self, "_pendientes"):
            try:
                self._pendientes = [m for m in self.buscar_alternativas(self._pide_imagenes(cuerpo)) if m != self.modelo]
            except Exception:
                self._pendientes = []
        if not self._pendientes:
            return False
        anterior, self.modelo = self.modelo, self._pendientes.pop(0)
        cuerpo["model"] = self.modelo
        self._avisar(
            f"El modelo gratuito «{anterior}» está saturado ahora mismo ({codigo}); "
            f"sigo con «{self.modelo}», también gratuito."
        )
        return True

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

    def _detalle_error(self, respuesta, error_datos=None) -> str:
        """El mensaje que da el proveedor, sin el JSON alrededor."""
        if isinstance(error_datos, dict) and error_datos.get("message"):
            return str(error_datos["message"])
        try:
            datos = respuesta.json()
        except ValueError:
            return respuesta.text[:300]
        error = datos.get("error") if isinstance(datos, dict) else None
        if isinstance(error, dict) and error.get("message"):
            mensaje = str(error["message"])
            # Ollama envuelve el error de su motor dos veces: el "message" es
            # otro JSON con el error de verdad dentro.
            if mensaje.startswith("{"):
                try:
                    interno = json.loads(mensaje).get("error") or {}
                    mensaje = str(interno.get("message") or mensaje)
                except (ValueError, AttributeError):
                    pass
            return mensaje
        if isinstance(error, str):
            return error
        if isinstance(datos, list) and datos and isinstance(datos[0], dict):  # Gemini devuelve [ {error} ]
            return str((datos[0].get("error") or {}).get("message") or datos[0])[:300]
        return respuesta.text[:300]

    def _error_definitivo(self, codigo: int, detalle: str) -> ErrorProveedor:
        """Errores que no se arreglan reintentando, explicados para el usuario."""
        donde = "Revísalo en Ajustes (⚙️)."
        if "exceeds the available context" in detalle or "context length" in detalle.lower() \
                or "maximum context" in detalle.lower():
            return ErrorContextoExcedido(
                f"La conversación ya no cabe en la memoria de trabajo del modelo «{self.modelo}». "
                "Empieza una conversación nueva (botón +) o usa un modelo con más contexto."
            )
        # Gemini responde a una clave inválida con 400 ("API key not valid" /
        # "Please pass a valid API key"), no con 401: es el mismo problema.
        clave_mala = codigo == 400 and "api key" in detalle.lower() and "valid" in detalle.lower()
        if codigo == 401 or clave_mala:
            return ErrorProveedor(f"La clave de API de {self.nombre} no es válida. Revísala en Ajustes (⚙️).")
        if codigo == 402:
            return ErrorProveedor(
                f"Tu cuenta de {self.nombre} no tiene saldo o crédito para este modelo. Recárgala "
                f"o elige un modelo gratuito en Ajustes (⚙️). ({detalle})"
            )
        if codigo == 403:
            return ErrorProveedor(
                f"{self.nombre} rechaza la petición con esta clave (sin permiso para el modelo "
                f"«{self.modelo}», clave restringida o región no admitida). {donde} ({detalle})"
            )
        if codigo == 404 or (codigo == 400 and "model" in detalle.lower()):
            return ErrorProveedor(
                f"El modelo «{self.modelo}» no existe en {self.nombre} o tu clave no tiene acceso a "
                f"él. Elige otro de la lista en Ajustes (⚙️). ({detalle})"
            )
        return ErrorProveedor(f"Error {codigo} de {self.nombre}: {detalle}")

    def _post(self, cuerpo: dict, timeout: float):
        try:
            return httpx.post(
                f"{self.base_url}/chat/completions",
                headers=self._cabeceras(),
                json=cuerpo,
                timeout=timeout,
            )
        except (httpx.LocalProtocolError, UnicodeEncodeError) as exc:
            # No es la red: la clave guardada tiene caracteres que no pueden ir
            # en una cabecera. Reintentar solo haría esperar minutos para nada.
            raise ErrorProveedor(
                f"La clave de {self.nombre} guardada tiene caracteres no válidos (espacios, "
                "saltos de línea o símbolos que se colaron al copiarla). Pégala de nuevo en Ajustes (⚙️)."
            ) from exc

    def probar(self) -> str:
        """Comprueba clave y modelo. En OpenRouter, sin gastar ninguna petición del cupo."""
        if self.nombre == "openrouter":
            return self._probar_openrouter()
        return self._probar_chat()

    def _probar_openrouter(self) -> str:
        try:
            r = httpx.get(f"{self.base_url}/key", headers=self._cabeceras(), timeout=20.0)
        except (httpx.LocalProtocolError, UnicodeEncodeError) as exc:
            raise ErrorProveedor(
                "La clave de openrouter guardada tiene caracteres no válidos. Pégala de nuevo en Ajustes (⚙️)."
            ) from exc
        except httpx.HTTPError as exc:
            raise ErrorProveedor(f"No se pudo contactar con OpenRouter: {exc}") from exc
        if r.status_code == 401:
            raise self._error_definitivo(401, "")
        if r.status_code >= 400:
            return self._probar_chat()  # /key no disponible: la prueba clásica
        try:
            datos = (r.json() or {}).get("data") or {}
        except ValueError:
            datos = {}

        from .. import modelos as catalogo  # diferido: el catálogo importa config

        lista = catalogo.listar("openrouter")
        en_vivo = "Sin conexión" not in (lista.get("nota") or "")
        if self.modelo.endswith(":free") and en_vivo and self.modelo not in {m["id"] for m in lista["modelos"]}:
            raise ErrorProveedor(
                f"«{self.modelo}» no está entre los modelos gratuitos de OpenRouter que saben usar "
                "herramientas (o ya no existe). Elige uno de la lista en Ajustes (⚙️)."
            )
        partes = [f"Clave de OpenRouter válida; modelo «{self.modelo}»."]
        cupo = datos.get("free_model_daily_requests")
        if self.modelo.endswith(":free") and isinstance(cupo, dict) and cupo.get("limit"):
            restantes, limite = cupo.get("remaining"), cupo.get("limit")
            if restantes is not None and restantes <= 0:
                raise ErrorProveedor(self._mensaje_cupo_diario(None))
            partes.append(f"Hoy te quedan {restantes} de {limite} peticiones gratuitas "
                          "(cada paso de una tarea gasta una).")
        return " ".join(partes)

    def _probar_chat(self) -> str:
        """Comprueba clave y modelo con una petición mínima (sin reintentos)."""
        cuerpo = {
            "model": self.modelo,
            "messages": [{"role": "user", "content": "Responde solo: ok"}],
            "max_tokens": 16,
        }
        try:
            respuesta = self._post(cuerpo, timeout=self.timeout if self.nombre == "ollama" else 45.0)
        except httpx.HTTPError as exc:
            if self.nombre == "ollama":
                raise ErrorProveedor("Ollama no responde. ¿Está en marcha? Ábrelo (o ejecuta «ollama serve»).") from exc
            raise ErrorProveedor(f"No se pudo contactar con {self.nombre}: {exc}") from exc
        error_datos = None
        codigo = respuesta.status_code
        if codigo < 400:
            try:
                datos = respuesta.json()
            except ValueError:
                datos = None
            if isinstance(datos, dict) and "error" in datos:
                error_datos = datos["error"]
                try:
                    codigo = int(error_datos.get("code"))
                except (TypeError, ValueError, AttributeError):
                    codigo = 400
        if codigo == 429:
            # La clave y el modelo son válidos: solo hay límite de uso ahora mismo.
            return f"Clave válida, pero {self.nombre} limita las peticiones ahora mismo (429): espera un poco."
        if codigo >= 500:
            raise ErrorProveedor(f"{self.nombre} tiene problemas ahora mismo (error {codigo}). Prueba en unos minutos.")
        if codigo >= 400:
            raise self._error_definitivo(codigo, self._detalle_error(respuesta, error_datos))
        return f"Conectado con {self.nombre}: el modelo «{self.modelo}» responde."

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
        fallos_seguidos = 0
        # Bucle explícito: cada modelo alternativo recibe su propio presupuesto de
        # reintentos. Es finito: termina con break, con un error, o cuando ya no
        # quedan alternativas (la lista solo se vacía).
        intento = -1
        while True:
            intento += 1
            ultimo = intento >= _MAX_REINTENTOS
            self._respetar_ritmo()
            try:
                respuesta = self._post(cuerpo, timeout=self.timeout)
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
                raise self._error_definitivo(401, "")

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
                    except (TypeError, ValueError, AttributeError):  # el error puede venir como texto
                        codigo = 400

            if codigo == 429:
                cupo = self._cupo_de_openrouter(respuesta)
                if cupo is not None and cupo[0] <= 0 and cupo[1] > _CUPO_LARGO_SEGUNDOS:
                    # Cupo diario agotado: ni reintentar ni cambiar de modelo sirve
                    # (el cupo es de la cuenta, para todos los modelos gratuitos).
                    raise ErrorProveedor(self._mensaje_cupo_diario(cupo[1]))
                if cupo is not None and cupo[0] <= 0 and not ultimo:
                    # Límite por minuto: se espera justo hasta que se renueva.
                    pausa = min(cupo[1] + 1.0, _ESPERA_MAXIMA)
                    self._avisar(f"Límite de peticiones por minuto de {self.nombre}; sigo en {int(pausa)} s…")
                    time.sleep(pausa)
                    continue
            if codigo == 429 or codigo == 408 or codigo >= 500:
                fallos_seguidos += 1
                if fallos_seguidos >= _FALLOS_ANTES_DE_CAMBIAR and self._cambiar_de_modelo(cuerpo, codigo):
                    fallos_seguidos = 0
                    espera = _ESPERA_INICIAL
                    intento = -1
                    continue
                if not ultimo:
                    pausa = self._espera_reintento(respuesta, espera)
                    quien = (f"El modelo «{self.modelo}»" if self.buscar_alternativas is not None
                             else self.nombre)
                    self._avisar(
                        f"{quien} está saturado ahora mismo ({codigo}); espero {int(pausa)} s "
                        f"y reintento ({intento + 1}/{_MAX_REINTENTOS})…"
                    )
                    time.sleep(pausa)
                    espera = min(espera * 2, _ESPERA_MAXIMA)
                    continue
                raise ErrorProveedor(self._mensaje_agotado(codigo))
            if error_datos is not None or codigo >= 400:
                raise self._error_definitivo(codigo, self._detalle_error(respuesta, error_datos))
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
