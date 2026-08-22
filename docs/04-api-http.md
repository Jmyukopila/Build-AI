# 04 · API HTTP

La API de [`main.py`](../buildai/main.py) escucha en `http://127.0.0.1:8600`.
No hay autenticación ni versionado. Los errores funcionales suelen ser JSON
con estado 200 porque las funciones retornan diccionarios de error; el render
usa 404 explícito.

## Endpoints

| Método y ruta | Entrada | Respuesta implementada |
|---|---|---|
| `GET /` | Ninguna | `FileResponse` de `ui/index.html`. |
| `GET /manual` | Ninguna | `FileResponse` de `ui/manual.html`. |
| `GET /ui/{ruta}` | Ruta estática | Archivo bajo `buildai/ui` mediante `StaticFiles`. |
| `GET /api/renders/{nombre}` | `nombre` | PNG de `~/.buildai/renders`; 404 si contiene separadores, empieza por `.`, no es `.png`, no existe o no es archivo. |
| `GET /api/estado` | Ninguna | `{programas:[{id,nombre,icono,conectado,ayuda}], proveedor, modelo, clave_configurada}`. |
| `GET /api/config` | Ninguna | `{proveedor, modelos, claves_configuradas, proveedores, modelos_por_defecto}`. Las claves son booleanos. |
| `POST /api/config` | `{proveedor?, claves?:{}, modelos?:{}}` | `{ok:true}`. Solo actualiza nombres conocidos y valores no vacíos. |
| `GET /api/oauth/login?proveedor=...` | Query `proveedor` | Redirección OAuth si `oauth_disponible`; si no, `{error}`. Solo OpenCode lo declara activo. |
| `GET /api/oauth/callback` | Hash del navegador | HTML que lee `access_token`, llama a `/api/oauth/save` y cierra en 2 s. |
| `POST /api/oauth/save` | `{token}` | `{ok:false,error:"Token vacío"}` si falta; si existe, guarda el token en el primer proveedor OAuth disponible y devuelve `{ok:true}`. |
| `POST /api/conectar/{programa_id}` | `programa_id` | Resultado de `instalador.instalar` más `conectado`, comprobado inmediatamente con el conector. |
| `GET /api/modelos/{proveedor}` | `proveedor` | Resultado de `modelos.listar`: `disponible`, `modelos:[{id,nombre}]`, `nota`. |
| `GET /api/skills` | Ninguna | Lista de JSON válidos cargados desde `buildai/skills_data`. |
| `POST /api/reiniciar` | Ninguna | `{ok:true}` y nueva conversación; si hay lock, `{ok:false,error}`. |
| `GET /api/sesiones` | Ninguna | `{actual:<id>, sesiones:[...]}`. |
| `POST /api/sesiones/{sesion_id}/abrir` | `sesion_id` | `{ok:true,mensajes:[eventos UI]}`; error si trabaja o no existe. |
| `DELETE /api/sesiones/{sesion_id}` | `sesion_id` | `{ok:true}`; no borra la sesión activa mientras trabaja. |
| `POST /api/cancelar` | Ninguna | Marca cancelación si hay lock y siempre devuelve `{ok:true}`. |
| `POST /api/chat` | `{mensaje, adjuntos?}` | `StreamingResponse` `text/event-stream`; errores de entrada o concurrencia también son eventos SSE. |

`/api/estado` comprueba los cuatro conectores en paralelo con
`ThreadPoolExecutor`. `POST /api/config` ignora campos desconocidos y un valor
vacío significa no cambiar la clave o modelo existente.

## Stream SSE de `/api/chat`

Cada mensaje tiene la forma `data: <JSON>\n\n`, generada por `_sse` con
`ensure_ascii=False`. La secuencia termina con `fin`.

| `tipo` | Campos | Emisión |
|---|---|---|
| `estado` | `texto` | El agente piensa o el proveedor espera y reintenta. |
| `herramienta` | `programa`, `nombre`, `detalle` | Antes de ejecutar una llamada; `detalle` es código u orden truncado a 400 caracteres. |
| `respuesta` | `texto` | Texto intermedio, final o cancelación. |
| `render` | `archivo` | Render validado por `renders_en_resultado`. |
| `error` | `texto` | Petición vacía, lock ocupado, proveedor o herramienta fallida. |
| `fin` | Ninguno | El hilo guardó la sesión y terminó. |

El cliente consume el stream con `response.body.getReader()` en
[`app.js`](../buildai/ui/app.js), separa líneas `data:` y actúa según `tipo`.

## Adjuntos y límites

La UI solo acepta fotos y vídeos; reduce imágenes en canvas y convierte un
vídeo en cuatro fotogramas. El servidor vuelve a validar en
[`_sanear_adjuntos`](../buildai/main.py): máximo 12 adjuntos válidos, solo
`image/*`, datos string no vacíos, base64 estricto y máximo de
`8 * 1024 * 1024` caracteres por adjunto. Las entradas inválidas no consumen
el cupo. El adaptador Anthropic usa bloques base64 y el compatible con OpenAI
usa URLs `data:`.

## OAuth de OpenCode

`/api/oauth/login` crea una redirección con `response_type=token`,
`client_id=buildai`, callback local y `scope=openid`. El callback no recibe
query de servidor: un script lee el token del fragmento URL del navegador y lo
envía a `/api/oauth/save`. El servidor guarda el token en la primera entrada
de `PROVEEDORES` con `oauth_disponible`. No hay estado, PKCE, comprobación de
audiencia ni selección explícita del proveedor al guardar; es una limitación
del flujo actual. Los demás proveedores requieren clave de API.

## Seguridad

El servidor enlaza solo con loopback y no autentica peticiones. Esto evita
exposición de red, pero no impide que otro proceso local llame a la API. Las
claves completas nunca se devuelven por `/api/config`; sí se guardan en
`~/.buildai/config.json`. Los puentes también escuchan solo en loopback.
