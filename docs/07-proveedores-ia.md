# 07 · Proveedores de IA

## Frontera neutra

[`providers/base.py`](../buildai/providers/base.py) define `ErrorProveedor`,
`LlamadaHerramienta`, `RespuestaLLM` y la interfaz `Proveedor.conversar`.
El agente conserva un historial independiente de cualquier SDK:

```text
usuario    -> {tipo, texto, adjuntos}
asistente  -> {tipo, texto, llamadas, _raw opcional}
resultado  -> {tipo, id, nombre, contenido}
```

`LlamadaHerramienta` contiene `id`, `nombre` y `argumentos`; `RespuestaLLM`
contiene `texto`, `llamadas` y `raw`. Esta frontera permite guardar sesiones y
cambiar de proveedor sin migrar el modelo de datos.

## Adaptadores

| Adaptador | Proveedores | Traducción |
|---|---|---|
| [`ProveedorAnthropic`](../buildai/providers/anthropic_provider.py) | Anthropic | Convierte usuario, asistente y resultados a `messages`; coloca imágenes antes del texto, pasa `tools`, conserva `_raw` para `thinking` y `tool_use`. |
| [`ProveedorOpenAICompatible`](../buildai/providers/openai_compat.py) | OpenRouter, OpenAI, Gemini, OpenCode y Ollama | Usa Chat Completions, herramientas `type=function`, mensajes `tool` y llamadas con `tool_calls`. Gemini usa su endpoint OpenAI compatible. |

Anthropic usa `max_tokens=16000` y thinking adaptativo. Las imágenes se
reconstruyen desde base64. En el adaptador compatible, Ollama usa timeout de
600 segundos y su endpoint local; OpenRouter aplica una pausa de 3,5 s para
modelos `:free`.

## Fábrica y configuración

[`crear_proveedor`](../buildai/providers/__init__.py) selecciona la clase por
id. [`config.py`](../buildai/config.py) define:

| Id | Modelo predeterminado |
|---|---|
| `openrouter` | `qwen/qwen3-coder:free` |
| `ollama` | `qwen3` |
| `anthropic` | `claude-opus-4-8` |
| `openai` | `gpt-4o` |
| `gemini` | `gemini-2.0-flash` |
| `opencode` | `big-pickle` |

Las claves viven en `~/.buildai/config.json`; la API solo devuelve
`claves_configuradas`. Ollama puede funcionar sin clave y los modelos estáticos
pueden aparecer aunque no haya red.

## Tool calling

El agente envía a `conversar` el prompt, el historial adaptado y las
herramientas de los conectores disponibles. Si la respuesta contiene llamadas,
ejecuta cada una, añade el resultado neutro y vuelve a conversar. Por tanto,
el modelo seleccionado debe soportar herramientas; un modelo de texto sin
tool calling solo puede responder sin operar un CAD/BIM. OpenRouter filtra
modelos gratuitos para conservar los que anuncian soporte de tools.

## Errores y reintentos

Los adaptadores convierten errores de autenticación, conexión, estado HTTP,
rechazo del proveedor y límites de tasa en `ErrorProveedor` con mensaje apto
para el usuario. El adaptador compatible reintenta hasta cinco veces:

* `429`, `408` y respuestas 5xx son transitorias;
* respeta `Retry-After` si existe;
* usa espera progresiva desde 5 s, limitada a 60 s;
* llama a `notificar` para que la UI muestre el estado.

Un fallo definitivo no se oculta: llega al agente y se emite como evento
`error`. Una cancelación entre llamadas no interrumpe una petición HTTP ya
en curso.

## Catálogo de modelos

[`modelos.py`](../buildai/modelos.py) combina red y respaldos:

* OpenRouter consulta modelos gratuitos que soportan tools.
* Ollama consulta `http://127.0.0.1:11434/api/tags`.
* OpenCode consulta `https://opencode.ai/zen/v1/models`.
* Anthropic, OpenAI y Gemini tienen listas estáticas.

El resultado se cachea por proveedor. El TTL general es 3600 segundos y el de
Ollama 5 segundos. Si la consulta falla se devuelve el último respaldo
conocido o la lista estática. Esto permite abrir la configuración sin red,
pero no demuestra que un modelo remoto siga disponible.

## Añadir un proveedor

1. Añadir su entrada de configuración, modelo predeterminado y clave.
2. Elegir si su protocolo encaja en OpenAI compatible o crear un módulo nuevo.
3. Implementar `conversar` convirtiendo el historial neutro y reconstruyendo
   `LlamadaHerramienta` y `RespuestaLLM`.
4. Traducir errores a `ErrorProveedor`; tratar solo estados realmente
   reintentables como transitorios.
5. Añadir catálogo, respaldo, cache y límites en `modelos.py`.
6. Incorporar el proveedor a `crear_proveedor` y a la UI de configuración.
7. Documentar si requiere tool calling, visión, OAuth o clave.
8. Probar historial de herramientas, imágenes, errores 429 y ausencia de red.

No se debe introducir el formato propio del nuevo proveedor en sesiones:
la conversión pertenece al adaptador.
