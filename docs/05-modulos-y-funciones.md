# 05 · Módulos y funciones

Esta referencia resume las funciones y clases existentes en `buildai/`,
`build_pkg/` y `tests/`. Las firmas se mantienen en la forma del código; los
detalles de implementación deben consultarse en los enlaces.

## Núcleo de aplicación

| Módulo | Función o clase | Firma y resultado | Notas |
|---|---|---|---|
| [`agent.py`](../buildai/agent.py) | `renders_en_resultado` | `(resultado: str) -> list` | Extrae marcas `RENDER_GUARDADO:` válidas. |
|  | `_sistema` | `(conectados: list) -> str` | Prompt arquitectónico con memoria y capacidades. |
|  | `_herramientas` | `(conectados: list) -> list` | Une herramientas de conectores. |
|  | `_recortar_historial` | `(historial: list) -> None` | Límite 120; corta en mensajes de usuario. |
|  | `_comprimir_resultados` | `(historial: list) -> None` | Resultados viejos a 600 caracteres; conserva renders. |
|  | `_historial_para_modelo` | `(historial: list) -> list` | Vista sin adjuntos de turnos cerrados. |
|  | `ejecutar_turno` | `(historial, mensaje_usuario, emitir, cancelado=None, adjuntos=None) -> None` | Orquesta proveedor, llamadas, límites y eventos; modifica el historial. |
| [`config.py`](../buildai/config.py) | `cargar`, `guardar` | `(config?)` | Lee/escribe JSON bajo `~/.buildai`; usa lock. |
|  | `clave_activa`, `proveedor_listo`, `modelo_activo` | `(config=None)` | Resuelven configuración efectiva. |
|  | `PROVEEDORES`, `MODELOS_POR_DEFECTO` | Constantes | Catálogo de seis proveedores y modelos iniciales. |
| [`rutas.py`](../buildai/rutas.py) | `ruta_datos`, `ruta_config`, `ruta_sesiones` | `() -> Path` | Crea o devuelve rutas de usuario y migra ubicación antigua. |
| [`sesiones.py`](../buildai/sesiones.py) | `nuevo_id` | `() -> str` | ID hexadecimal de 12 caracteres. |
|  | `listar`, `cargar`, `guardar`, `borrar` | `(sesion_id...)` | JSON por conversación; `_ruta` exige `isalnum`. |
|  | `para_ui` | `(historial) -> list` | Reconstruye respuestas, llamadas y renders para la UI. |
|  | `titulo`, `serializar`, `deserializar`, `_ruta`, `_entrada_ui` | Internas | Serialización neutra y validaciones; errores de disco se propagan al llamador. |
| [`memoria.py`](../buildai/memoria.py) | `construir`, `extraer`, `firma` | `(directorio/historial...)` | Destila materiales, kits, categorías y temas; cachea por cantidad y mtime y responde vacío ante fallo. |
| [`modelos.py`](../buildai/modelos.py) | `listar` | `(proveedor) -> dict` | Catálogo remoto o estático, con respaldo y cache TTL. |
|  | `_listar_openrouter`, `_listar_ollama`, `_listar_opencode` | `(...)` | OpenRouter filtra modelos gratuitos con tools; Ollama usa `/api/tags`; OpenCode usa `/v1/models`. |
|  | `_cache_valido` | `(proveedor) -> bool` | TTL general 3600 s y Ollama 5 s. |
| [`skills.py`](../buildai/skills.py) | `cargar` | `() -> list` | Lee únicamente `buildai/skills_data`, valida `id`, `nombre`, `prompt`, aplica defaults y omite JSON inválido. |
| [`instalador.py`](../buildai/instalador.py) | `instalar`, `instalar_todos` | `(programa_id...)` | Detecta rutas y copia el puente; best-effort según programa. |
|  | `rutas_*`, `detectar_*` | `(…) -> list/Path/None` | Descubrimiento de instalaciones de Blender, SketchUp y Revit. |
|  | `crear_acceso_directo`, `aviso_instalacion_arriesgada` | `(…)` | Acceso `.lnk` en Windows y aviso de ejecución de código. |
|  | `_copiar`, `_buscar`, `_normalizar`, `_ejecutar`, demás helpers | Internas | Preparan carpetas y procesos; no forman API estable. |

## API y frontend

| Módulo | Funciones o clases | Comportamiento |
|---|---|---|
| [`main.py`](../buildai/main.py) | `portada`, `manual`, `archivos_ui`, `ver_render` | Sirven UI, manual y PNG validado contra path traversal. |
|  | `estado`, `config_get`, `config_post` | Exponen estado de conectores y configuración sin devolver claves. |
|  | `oauth_login`, `oauth_callback`, `oauth_save` | Implementan el flujo OAuth de OpenCode. |
|  | `conectar`, `modelos`, `skills`, `reiniciar` | Instalación, catálogos y cambio de conversación. |
|  | `listar_sesiones`, `abrir_sesion`, `eliminar_sesion`, `cancelar`, `chat` | Ciclo de sesiones, cancelación y SSE. `chat` serializa el trabajo con `_ocupado`. |
|  | `_sanear_adjuntos`, `_sse`, `_esperar_servidor`, `_hilo_estado`, `arrancar` | Validación, formato SSE, arranque y fallback de navegador. |
| [`ui/app.js`](../buildai/ui/app.js) | funciones de chat, SSE, sesiones, ajustes y adjuntos | Código vanilla. Reduce imágenes en canvas, extrae cuatro fotogramas de vídeo y descarga exportaciones. |
| [`ui/icons.js`](../buildai/ui/icons.js) | iconos | Catálogo SVG usado por la UI. |
| [`ui/index.html`](../buildai/ui/index.html) | estructura | No contiene framework ni bundle. |

## Conectores y proveedores

| Módulo | Elementos | Notas |
|---|---|---|
| [`connectors/base.py`](../buildai/connectors/base.py) | `Conector`, `recortar` | Contrato `disponible`, `herramientas`, `ejecutar`; salida máxima 12000. |
| [`connectors/__init__.py`](../buildai/connectors/__init__.py) | `CONECTORES`, `buscar_herramienta` | Registro y búsqueda por nombre. |
| [`connectors/blender.py`](../buildai/connectors/blender.py) | `_enviar`, `ConectorBlender` | JSON por socket 8601; ejecuta Python y antepone `blender_kit.py`. |
| [`connectors/autocad.py`](../buildai/connectors/autocad.py) | `_obtener_acad`, `ConectorAutoCAD` | COM, `pythoncom.CoInitialize`, ProgID 25 a 18. |
| [`connectors/sketchup.py`](../buildai/connectors/sketchup.py) | `ConectorSketchUp` | HTTP 8602 y Ruby. |
| [`connectors/revit.py`](../buildai/connectors/revit.py) | `ConectorRevit` | Routes 48884, IronPython y transacción ya abierta. |
| [`providers/base.py`](../buildai/providers/base.py) | `ErrorProveedor`, `LlamadaHerramienta`, `RespuestaLLM`, `Proveedor` | Contrato neutral y error apto para usuario. |
| [`providers/__init__.py`](../buildai/providers/__init__.py) | `crear_proveedor` | Fábrica por id de configuración. |
| [`anthropic_provider.py`](../buildai/providers/anthropic_provider.py) | `ProveedorAnthropic` | Traduce mensajes, imágenes, thinking y tool use a SDK Anthropic. |
| [`openai_compat.py`](../buildai/providers/openai_compat.py) | `ProveedorOpenAICompatible` | Cubre OpenRouter, Ollama, OpenAI, Gemini y OpenCode; reintenta 429, 408 y 5xx. |

## Kit de Blender

[`blender_kit.py`](../buildai/connectors/blender_kit.py) es código textual
inyectado en Blender. Sus unidades son metros y crea geometría, materiales,
luces y cámaras mediante la API de bpy.

| Familia | Funciones |
|---|---|
| Utilidades geométricas | `_entrada`, `_agregar_caja`, `_agregar_cilindro`, `_agregar_esfera`, `_malla_piezas`, `_malla_cajas`, `_nuevo_objeto`, `_colocar`, `_sin_sombra`, `_mat`, `coleccion`, `caja`, `limpiar_todo`, `_local_a_mundo`, `_contorno_ccw`, `_quitar_objetos`, `_pieza`, `_situar`, `_sobre_pared`, `_fijar`, `_suavizar` |
| Terreno y estructura | `muro`, `ventanal`, `forjado`, `rejilla_pilares`, `terreno`, `escalera`, `barandilla`, `piscina`, `valla`, `camino`, `pergola`, `celosia` |
| Cubiertas | `cubierta_plana`, `cubierta_dos_aguas` |
| Mobiliario interior | `cama`, `mesita_noche`, `mesa`, `silla`, `sofa`, `sillon`, `comedor`, `armario`, `estanteria`, `cocina`, `lavabo`, `inodoro`, `ducha`, `banera`, `alfombra`, `cuadro`, `espejo_pared`, `television`, `planta_decorativa` |
| Estancias y exterior | `dormitorio`, `salon`, `bano`, `arbol`, `arbusto`, `seto`, `tumbona`, `barbacoa`, `palmera`, `farola`, `coche` |
| Materiales | `material`, `_conectar_relieve`, `_nodos_textura`, `_mat_vegetacion`, `_mat_corteza` |
| Iluminación | `_crear_sol`, `sol`, `_luz_puntual`, `luz_interior`, `lampara_colgante`, `lampara_pie`, `_luz_foco`, `foco_empotrado`, `foco_jardin`, `cielo` |
| Cámara y render | `camara`, `revisar_escena`, `_activar_gpu`, `_activar_resplandor`, `_vidrios_opacos_cycles`, `_auto_camara`, `render` |

Las funciones públicas devuelven objetos Blender o `None` según el caso y
crean elementos en la escena; las auxiliares no son una API estable. `render`
guarda un PNG y el conector devuelve la marca que el agente convierte en
evento.

## Kit de Revit

[`revit_kit.py`](../buildai/connectors/revit_kit.py) traduce metros a pies,
trabaja con la API DB disponible en el puente y asume una transacción abierta.

| Familia | Funciones |
|---|---|
| Conversiones y utilidades | `_a_pies`, `_a_metros`, `xyz`, `imprimir`, `_elementos`, `borrar` |
| Niveles | `niveles`, `nivel` |
| Muros y suelos | `tipo_muro`, `muro`, `_tipo_suelo`, `suelo` |
| Familias y símbolos | `_simbolos`, `familias`, `_buscar_simbolo`, `_activar` |
| Puertas y ventanas | `puerta`, `ventana` |
| Colocación y estructura | `colocar`, `pilar` |

## Puentes, empaquetado y pruebas

| Módulo | Funciones o clases | Notas |
|---|---|---|
| [`addons/blender/buildai_blender.py`](../buildai/addons/blender/buildai_blender.py) | `register`, `unregister`, `_servidor`, `_aceptar`, `_bombear_trabajos`, `_procesar`, `_contar` | Cola y timer garantizan ejecución en el hilo principal. |
| [`addons/revit/.../startup.py`](../buildai/addons/revit/BuildAI.extension/startup.py) | rutas decoradas `/ping`, `/info`, `/ejecutar`, `_contar` | Abre `revit.Transaction("BuildAI")` y expone `doc`, `uidoc`, `DB`, `revit`, `salida`. |
| [`addons/sketchup/buildai_sketchup.rb`](../buildai/addons/sketchup/buildai_sketchup.rb) | servidor, cola, `procesar`, `registrar` | Ruby HTTP sobre TCP 8602 y `UI.start_timer`. |
| [`build_pkg/run_buildai.py`](../build_pkg/run_buildai.py) | entry point | Llama a `buildai.main.arrancar`. |
| [`build_pkg/buildai.spec`](../build_pkg/buildai.spec) | configuración PyInstaller | Incluye UI, skills, addons y kits; salida onedir sin consola. |
| [`tests/test_adjuntos_historial.py`](../tests/test_adjuntos_historial.py) | tests de historial | Adjuntos viejos no se reenvían y el historial no se muta. |
| [`tests/test_sanear_adjuntos.py`](../tests/test_sanear_adjuntos.py) | tests de saneado | Inválidos, límite 12, no imágenes y base64 inválido. |

## Locks, cache y casos borde

El lock de configuración protege lecturas y escrituras concurrentes; el lock
de `main` serializa turnos. La cola conecta hilo de trabajo y SSE. Catálogos
y memoria usan cache con firma o TTL y respaldo best-effort. IDs de sesión y
nombres de render se validan antes del disco. Un CAD cerrado hace que
`disponible()` sea falso, no que arranque el programa; una herramienta que
falla retorna texto de error al agente para que pueda continuar o informar.
