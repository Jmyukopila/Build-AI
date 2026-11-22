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
| `openrouter` | `google/gemma-4-31b-it:free` |
| `ollama` | `qwen3` |
| `anthropic` | `claude-opus-5` |
| `openai` | `gpt-5.6-terra` |
| `gemini` | `gemini-3.7-flash` |
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

## Conectar la clave sin sorpresas

Al configurar un proveedor fallaban cosas que no eran culpa del usuario. Desde 2026-11-21 se gestionan así:

- **Limpieza de la clave** ([`providers/claves.py`](../buildai/providers/claves.py)).
  - **Qué se quita:** espacios, saltos de línea, caracteres invisibles de copiar y pegar (anchura cero, BOM, espacio duro), comillas, el prefijo `Bearer ` y una línea `NOMBRE_API_KEY=` entera.
  - **Cuándo:** al guardar en Ajustes y también al crear el proveedor, para que una clave guardada antes del arreglo siga funcionando.
  - **Clave imposible:** si aun así contiene tildes o espacios en medio, no se guarda y se explica.
  - **Proveedor equivocado:** se avisa si la clave parece de otro proveedor por su prefijo (`sk-ant-`, `sk-or-`, `AIza`, `sk-`).
- **Prueba de conexión al guardar** (`POST /api/config/probar` → `probar_conexion`).
  - Anthropic consulta la API de Modelos, que no gasta tokens.
  - Los compatibles con OpenAI hacen una petición de 16 tokens, sin reintentos.
  - Ollama comprueba que el modelo está instalado.
  - Si falla, Ajustes sigue abierto con el motivo en rojo.
- **Errores legibles.**
  - Compatibles con OpenAI: 402 (sin saldo), 403 (sin permiso o región no admitida), 404 o 400 de modelo (no existe) y el 400 «API key not valid» de Gemini se explican sin JSON. Una clave con caracteres imposibles ya no se reintenta 5 veces como si fuera un corte de red.
  - Anthropic: los errores se traducen por tipo, del más concreto al más general.
- ***Thinking* en Claude.** Solo se envía `thinking={"type": "adaptive"}` a los modelos que lo admiten (Claude 4.6 en adelante; `admite_pensamiento_adaptativo`). Haiku 4.5 y los anteriores devolvían un 400 en cada mensaje.
- **OAuth de OpenCode Zen.** Desactivado: su página de autorización no existe (404).

## «Está saturado»: cupos y modelos gratuitos

Casi siempre se trata de los modelos `:free` de OpenRouter. Según su documentación de límites, admiten 20 peticiones por minuto y **50 al día** sin crédito comprado (1 000 al día a partir de 10 $). Cada paso del agente es una petición, así que una tarea grande puede agotar el cupo diario. Así lo gestiona [`openai_compat.py`](../buildai/providers/openai_compat.py):

- **Cupo diario agotado:** un 429 con `X-RateLimit-Remaining: 0` y una renovación a más de 5 minutos. Solo los límites propios de OpenRouter llevan esas cabeceras. No se reintenta y se explica a qué hora se renueva y qué opciones hay (crédito, Ollama u otro proveedor).
- **Límite por minuto:** se espera hasta `X-RateLimit-Reset` y se reintenta una vez.
- **Modelo gratuito saturado** (429 del proveedor del modelo, 408 o 5xx): tras 2 fallos seguidos se pasa a otro modelo **gratuito** con herramientas (`modelos.alternativas_gratuitas`; con imágenes en la conversación, primero los que las ven). Se avisa al usuario y se sigue con ese modelo el resto del turno; cada alternativa recibe su propio presupuesto de reintentos. Un modelo de pago nunca cambia solo.
- **«Guardar» en Ajustes:** con OpenRouter consulta `GET /api/v1/key`, que no gasta cupo, y muestra «Hoy te quedan N de M peticiones gratuitas».

**No verificado contra el servicio real** (haría falta una clave con el cupo agotado): la forma exacta de las cabeceras del 429 sigue lo que dice la documentación de OpenRouter.
