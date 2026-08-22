# 05 · Módulos y funciones

Las tablas se generaron contrastando nombres y firmas con el AST del árbol actual. Las firmas incluyen los parámetros declarados; los retornos solo aparecen cuando el código anota el retorno.

## `buildai/agent.py`

El turno crea el proveedor con la configuración activa, obtiene conectores disponibles y añade la entrada de usuario al historial. `ejecutar_turno` emite `estado`, `respuesta`, `herramienta`, `render` o `error`; al terminar sin llamadas devuelve la respuesta textual. Cada resultado recién obtenido se limita a `MAX_RESULTADO`; al alcanzar `MAX_PASOS` se añade una pausa de seguridad sin borrar lo avanzado.

| Símbolo | Firma o tipo | Qué hace y qué devuelve | Casos borde y estado |
|---|---|---|---|
| `renders_en_resultado` | `renders_en_resultado(resultado: str) -> list` | Extrae nombres de renders válidos de un resultado. | Puede propagar errores del canal o del disco; el llamador decide cómo presentarlos. |
| `_sistema` | `_sistema(conectados: list) -> str` | Construye el prompt de sistema con capacidades y memoria. | Helper interno; no constituye API estable. |
| `_herramientas` | `_herramientas(conectados: list) -> list` | Reúne los esquemas de herramientas conectadas. | Helper interno; no constituye API estable. |
| `_recortar_historial` | `_recortar_historial(historial: list) -> None` | Elimina turnos antiguos hasta el límite de contexto. | Helper interno; no constituye API estable. |
| `_comprimir_resultados` | `_comprimir_resultados(historial: list) -> None` | Recorta resultados antiguos y conserva marcas de render. | Helper interno; no constituye API estable. |
| `_historial_para_modelo` | `_historial_para_modelo(historial: list) -> list` | Crea la vista enviada al proveedor sin adjuntos viejos. | Helper interno; no constituye API estable. |
| `ejecutar_turno` | `ejecutar_turno(historial: list, mensaje_usuario: str, emitir, cancelado=None, adjuntos=None) -> None` | Ejecuta un turno completo de conversación y tool calling. | Puede propagar errores del canal o del disco; el llamador decide cómo presentarlos. |

**Constantes de módulo:** `CARPETA_RENDERS`, `_MARCA_RENDER`, `MAX_PASOS`, `MAX_HISTORIAL`, `MAX_RESULTADO`, `RESULTADO_ANTIGUO_MAX`, `ENTRADAS_SIN_COMPRIMIR`, `SISTEMA_BASE`.

## `buildai/config.py`

`cargar` parte de `_CONFIG_DEFECTO`, tolera un JSON inexistente, corrupto o incompleto y migra modelos retirados. `guardar` escribe el JSON con un lock de proceso. `clave_activa`, `proveedor_listo` y `modelo_activo` aceptan configuración opcional y, si no se entrega, cargan la persistida.

| Símbolo | Firma o tipo | Qué hace y qué devuelve | Casos borde y estado |
|---|---|---|---|
| `cargar` | `cargar() -> dict` | Carga y normaliza la configuración persistida. | Puede propagar errores del canal o del disco; el llamador decide cómo presentarlos. |
| `guardar` | `guardar(config: dict) -> None` | Guarda configuración bajo lock. | Puede propagar errores del canal o del disco; el llamador decide cómo presentarlos. |
| `clave_activa` | `clave_activa(config: dict | None=None) -> str` | Devuelve la clave del proveedor activo. | Puede propagar errores del canal o del disco; el llamador decide cómo presentarlos. |
| `proveedor_listo` | `proveedor_listo(config: dict | None=None) -> bool` | Indica si el proveedor activo está configurado. | Puede propagar errores del canal o del disco; el llamador decide cómo presentarlos. |
| `modelo_activo` | `modelo_activo(config: dict | None=None) -> str` | Devuelve el modelo seleccionado o el predeterminado. | Puede propagar errores del canal o del disco; el llamador decide cómo presentarlos. |

**Constantes de módulo:** `OLLAMA_URL`, `MODELOS_POR_DEFECTO`, `_MODELOS_MIGRADOS`, `PROVEEDORES`, `_CONFIG_DEFECTO`.

## `buildai/rutas.py`

`CARPETA_DATOS` se basa en el directorio personal del usuario y no en `%APPDATA%`. La migración se ejecuta solo cuando falta el destino; `carpeta_sesiones` crea la carpeta bajo demanda.

| Símbolo | Firma o tipo | Qué hace y qué devuelve | Casos borde y estado |
|---|---|---|---|
| `_migrar_si_hace_falta` | `_migrar_si_hace_falta(nombre: str) -> None` | Migra una ruta antigua si el destino aún no existe. | Helper interno; no constituye API estable. |
| `ruta_config` | `ruta_config() -> Path` | Devuelve la ruta de config.json. | Puede propagar errores del canal o del disco; el llamador decide cómo presentarlos. |
| `carpeta_sesiones` | `carpeta_sesiones() -> Path` | Devuelve y prepara la carpeta de sesiones. | Puede propagar errores del canal o del disco; el llamador decide cómo presentarlos. |

**Constantes de módulo:** `CARPETA_DATOS`, `_RAIZ_PROYECTO`.

## `buildai/sesiones.py`

Cada sesión se guarda como un JSON independiente. `_ruta` restringe el identificador a caracteres alfanuméricos antes de construir el nombre de archivo; `cargar` devuelve `None` cuando no existe y `borrar` ignora la ausencia del archivo. La serialización conserva las llamadas de herramienta y los campos originales necesarios para los adaptadores.

| Símbolo | Firma o tipo | Qué hace y qué devuelve | Casos borde y estado |
|---|---|---|---|
| `nuevo_id` | `nuevo_id() -> str` | Genera el identificador hexadecimal de una sesión. | Puede propagar errores del canal o del disco; el llamador decide cómo presentarlos. |
| `_ruta` | `_ruta(sesion_id: str) -> Path` | Valida el id y devuelve su archivo JSON. | Helper interno; no constituye API estable. |
| `_serializar` | `_serializar(historial: list) -> list` | Convierte entradas neutras a JSON. | Helper interno; no constituye API estable. |
| `_deserializar` | `_deserializar(entradas: list) -> list` | Reconstruye llamadas de herramienta desde JSON. | Helper interno; no constituye API estable. |
| `_titulo` | `_titulo(historial: list) -> str` | Calcula el título visible de una sesión. | Helper interno; no constituye API estable. |
| `guardar` | `guardar(sesion_id: str, historial: list) -> None` | Persiste id, metadatos e historial. | Puede propagar errores del canal o del disco; el llamador decide cómo presentarlos. |
| `cargar` | `cargar(sesion_id: str)` | Carga una sesión o indica que no existe. | Puede propagar errores del canal o del disco; el llamador decide cómo presentarlos. |
| `listar` | `listar() -> list` | Lista metadatos de sesiones guardadas. | Puede propagar errores del canal o del disco; el llamador decide cómo presentarlos. |
| `borrar` | `borrar(sesion_id: str) -> None` | Elimina el archivo de una sesión. | Puede propagar errores del canal o del disco; el llamador decide cómo presentarlos. |
| `para_ui` | `para_ui(historial: list) -> list` | Convierte el historial al formato de la interfaz. | Puede propagar errores del canal o del disco; el llamador decide cómo presentarlos. |

**Constantes de módulo:** `TITULO_MAX`.

## `buildai/memoria.py`

La memoria es best-effort: analiza sesiones guardadas, extrae textos y fragmentos de código reconocibles y devuelve un perfil textual. Su firma usa cantidad de archivos y modificación más reciente; una lectura o extracción fallida no debe impedir el turno.

| Símbolo | Firma o tipo | Qué hace y qué devuelve | Casos borde y estado |
|---|---|---|---|
| `_firma` | `_firma(carpeta)` | Calcula la firma de cache a partir de sesiones. | Helper interno; no constituye API estable. |
| `_codigos_y_textos` | `_codigos_y_textos(historial)` | Extrae código y texto útil del historial. | Helper interno; no constituye API estable. |
| `perfil_texto` | `perfil_texto() -> str` | Construye un perfil textual de preferencias; falla vacío. | Puede propagar errores del canal o del disco; el llamador decide cómo presentarlos. |

**Constantes de módulo:** `_MATERIALES`, `_CATEGORIAS`, `_TEMAS`, `_RE_FUNC`, `_RE_MAT`.

## `buildai/modelos.py`

`listar` aplica `_CACHE_SEGUNDOS` al catálogo general y un TTL de 5 segundos a Ollama. OpenRouter filtra ids terminados en `:free` que declaran `tools`; Ollama consulta `/api/tags`; OpenCode consulta `/v1/models`; los demás proveedores usan `_ESTATICOS`. Los fallos usan respaldos incorporados o, para Ollama, catálogo vacío no disponible.

| Símbolo | Firma o tipo | Qué hace y qué devuelve | Casos borde y estado |
|---|---|---|---|
| `_openrouter_gratuitos` | `_openrouter_gratuitos() -> dict` | Consulta modelos gratuitos de OpenRouter con tools. | Helper interno; no constituye API estable. |
| `_ollama_locales` | `_ollama_locales() -> dict` | Consulta modelos locales de Ollama. | Helper interno; no constituye API estable. |
| `_opencode_zen_models` | `_opencode_zen_models() -> dict` | Consulta modelos de OpenCode Zen. | Helper interno; no constituye API estable. |
| `listar` | `listar(proveedor: str) -> dict` | Devuelve catálogo remoto, estático o de respaldo con cache. | Puede propagar errores del canal o del disco; el llamador decide cómo presentarlos. |

**Constantes de módulo:** `_RESPALDO_OPENROUTER`, `_ESTATICOS`, `_RESPALDO_OPENCODE`, `_CACHE_SEGUNDOS`.

## `buildai/skills.py`

`cargar_skills` recorre `CARPETA_SKILLS`, acepta objetos JSON con los campos requeridos y descarta archivos ilegibles o elementos inválidos. La ejecución del agente no concede permisos adicionales: las operaciones siguen limitadas por los conectores.

| Símbolo | Firma o tipo | Qué hace y qué devuelve | Casos borde y estado |
|---|---|---|---|
| `cargar_skills` | `cargar_skills() -> list` | Carga JSON válidos desde buildai/skills_data. | Puede propagar errores del canal o del disco; el llamador decide cómo presentarlos. |

**Constantes de módulo:** `CARPETA_SKILLS`.

## `buildai/instalador.py`

Los instaladores devuelven diccionarios con `ok` y `mensaje`; `instalar` captura excepciones por programa y `instalar_todos` continúa con el resto. Blender, SketchUp y Revit reciben archivos desde `ADDONS`; AutoCAD no recibe addon y se limita a comprobar COM. `crear_acceso_directo` devuelve `{ok:false}` fuera de Windows.

| Símbolo | Firma o tipo | Qué hace y qué devuelve | Casos borde y estado |
|---|---|---|---|
| `_es_python_de_store` | `_es_python_de_store() -> bool` | Detecta la instalación Python de Microsoft Store. | Helper interno; no constituye API estable. |
| `_cmd` | `_cmd(argumentos: list) -> bool` | Ejecuta un comando auxiliar y devuelve éxito. | Helper interno; no constituye API estable. |
| `_crear_carpeta` | `_crear_carpeta(carpeta: Path) -> None` | Crea una carpeta si falta. | Helper interno; no constituye API estable. |
| `_copiar_archivo` | `_copiar_archivo(origen: Path, destino: Path) -> None` | Copia un archivo de puente. | Helper interno; no constituye API estable. |
| `_copiar_carpeta` | `_copiar_carpeta(origen: Path, destino: Path) -> None` | Copia una carpeta de recursos. | Helper interno; no constituye API estable. |
| `_escribir_texto` | `_escribir_texto(destino: Path, texto: str) -> None` | Escribe texto UTF-8 en una ruta. | Helper interno; no constituye API estable. |
| `_programas_files` | `_programas_files() -> list` | Obtiene rutas de Program Files. | Helper interno; no constituye API estable. |
| `_versiones_blender` | `_versiones_blender() -> set` | Detecta versiones instaladas de Blender. | Helper interno; no constituye API estable. |
| `_instalar_blender` | `_instalar_blender() -> dict` | Instala el addon de Blender. | Helper interno; no constituye API estable. |
| `_instalar_sketchup` | `_instalar_sketchup() -> dict` | Instala la extensión de SketchUp. | Helper interno; no constituye API estable. |
| `_pyrevit_detectado` | `_pyrevit_detectado() -> bool` | Comprueba si pyRevit está disponible. | Helper interno; no constituye API estable. |
| `_revit_detectado` | `_revit_detectado() -> bool` | Comprueba si está instalada una extensión Revit. | Helper interno; no constituye API estable. |
| `_instalar_revit` | `_instalar_revit() -> dict` | Instala la extensión de Revit. | Helper interno; no constituye API estable. |
| `_instalar_autocad` | `_instalar_autocad() -> dict` | Devuelve el resultado de instalación para AutoCAD. | Helper interno; no constituye API estable. |
| `aviso_instalacion_arriesgada` | `aviso_instalacion_arriesgada() -> str | None` | Devuelve el aviso sobre ejecución de código. | Puede propagar errores del canal o del disco; el llamador decide cómo presentarlos. |
| `crear_acceso_directo` | `crear_acceso_directo() -> dict` | Crea un acceso directo de Windows. | Puede propagar errores del canal o del disco; el llamador decide cómo presentarlos. |
| `instalar` | `instalar(programa_id: str) -> dict` | Instala el puente solicitado y devuelve resultado. | Puede propagar errores del canal o del disco; el llamador decide cómo presentarlos. |
| `instalar_todos` | `instalar_todos() -> None` | Intenta instalar todos los puentes. | Puede propagar errores del canal o del disco; el llamador decide cómo presentarlos. |

**Constantes de módulo:** `ADDONS`, `APPDATA`, `_CARPETA_SEGURA`, `_INSTALADORES`.

## `buildai/main.py`

Las funciones de ruta son los handlers de FastAPI y devuelven `FileResponse`, diccionarios o `StreamingResponse` según el caso. `chat` define `flujo` y `trabajo` dentro del propio handler: el primero consume la cola y el segundo ejecuta el turno, guarda la sesión en `finally` y libera el lock. `ver_render` valida extensión, separadores, nombre oculto y existencia antes de servir el archivo.

| Símbolo | Firma o tipo | Qué hace y qué devuelve | Casos borde y estado |
|---|---|---|---|
| `portada` | `portada()` | Sirve index.html. | Puede propagar errores del canal o del disco; el llamador decide cómo presentarlos. |
| `manual` | `manual()` | Sirve manual.html. | Puede propagar errores del canal o del disco; el llamador decide cómo presentarlos. |
| `ver_render` | `ver_render(nombre: str)` | Valida y sirve un PNG de renders. | Puede propagar errores del canal o del disco; el llamador decide cómo presentarlos. |
| `_disponible_seguro` | `_disponible_seguro(conector) -> bool` | Convierte una excepción de disponibilidad en false. | Helper interno; no constituye API estable. |
| `estado` | `estado()` | Devuelve conectores, proveedor, modelo y configuración. | Puede propagar errores del canal o del disco; el llamador decide cómo presentarlos. |
| `leer_config` | `leer_config()` | Devuelve configuración sin secretos. | Puede propagar errores del canal o del disco; el llamador decide cómo presentarlos. |
| `guardar_config` | `guardar_config(peticion: Request)` | Actualiza y persiste proveedor, claves y modelos. | Puede propagar errores del canal o del disco; el llamador decide cómo presentarlos. |
| `oauth_login` | `oauth_login(proveedor: str)` | Redirige al OAuth disponible. | Puede propagar errores del canal o del disco; el llamador decide cómo presentarlos. |
| `oauth_callback` | `oauth_callback()` | Sirve la página que recoge el token del fragmento. | Puede propagar errores del canal o del disco; el llamador decide cómo presentarlos. |
| `oauth_save` | `oauth_save(peticion: Request)` | Guarda el token OAuth. | Puede propagar errores del canal o del disco; el llamador decide cómo presentarlos. |
| `conectar` | `conectar(programa_id: str)` | Instala un puente y comprueba disponibilidad. | Puede propagar errores del canal o del disco; el llamador decide cómo presentarlos. |
| `modelos_de` | `modelos_de(proveedor: str)` | Devuelve el catálogo de un proveedor. | Puede propagar errores del canal o del disco; el llamador decide cómo presentarlos. |
| `skills` | `skills()` | Devuelve las skills cargadas. | Puede propagar errores del canal o del disco; el llamador decide cómo presentarlos. |
| `reiniciar` | `reiniciar()` | Cambia a una conversación nueva si está libre. | Puede propagar errores del canal o del disco; el llamador decide cómo presentarlos. |
| `listar_sesiones` | `listar_sesiones()` | Lista sesiones y la actual. | Puede propagar errores del canal o del disco; el llamador decide cómo presentarlos. |
| `abrir_sesion` | `abrir_sesion(sesion_id: str)` | Abre una sesión validada. | Puede propagar errores del canal o del disco; el llamador decide cómo presentarlos. |
| `borrar_sesion` | `borrar_sesion(sesion_id: str)` | Borra una sesión no activa. | Puede propagar errores del canal o del disco; el llamador decide cómo presentarlos. |
| `cancelar` | `cancelar()` | Solicita cancelación del trabajo. | Puede propagar errores del canal o del disco; el llamador decide cómo presentarlos. |
| `_sanear_adjuntos` | `_sanear_adjuntos(bruto) -> list` | Filtra imágenes base64 y aplica límites. | Helper interno; no constituye API estable. |
| `chat` | `chat(peticion: Request)` | Crea el stream SSE y el hilo del turno. | Puede propagar errores del canal o del disco; el llamador decide cómo presentarlos. |
| `_sse` | `_sse(evento: dict) -> str` | Codifica un evento como SSE. | Helper interno; no constituye API estable. |
| `_esperar_servidor` | `_esperar_servidor(timeout: float=15.0) -> bool` | Espera hasta que el servidor local responda. | Helper interno; no constituye API estable. |
| `arrancar` | `arrancar()` | Inicia servidor y ventana o navegador. | Puede propagar errores del canal o del disco; el llamador decide cómo presentarlos. |
| `flujo` | `flujo()` | Generador interno del stream. | Puede propagar errores del canal o del disco; el llamador decide cómo presentarlos. |
| `trabajo` | `trabajo()` | Función interna que ejecuta y guarda el turno. | Puede propagar errores del canal o del disco; el llamador decide cómo presentarlos. |

**Constantes de módulo:** `PUERTO`, `CARPETA_UI`, `_OAUTH_CLIENT_ID`, `_MAX_ADJUNTOS`, `_MAX_BYTES_ADJUNTO`.

## `buildai/connectors/base.py`

`Conector` es el contrato mínimo para detectar un programa, describir herramientas y ejecutar una llamada. `recortar` limita la salida textual a `MAX_SALIDA`; los conectores concretos convierten excepciones de disponibilidad en `False` y devuelven errores textuales para no tumbar el turno.

| Símbolo | Firma o tipo | Qué hace y qué devuelve | Casos borde y estado |
|---|---|---|---|
| `Conector` | clase | Base de la que heredan los cuatro conectores; define `id`, `nombre`, `icono`, `ayuda` (texto de conexión mostrado al usuario) y los tres métodos abstractos que cada subclase implementa. | Los métodos abstractos lanzan `NotImplementedError`; no se instancia directamente. |
| `recortar` | `recortar(texto: str, limite: int=MAX_SALIDA) -> str` | Limita la salida de una herramienta a MAX_SALIDA. | Puede propagar errores del canal o del disco; el llamador decide cómo presentarlos. |
| `disponible` | `disponible(self) -> bool` | Implementa la operación interna indicada por su nombre. | Puede propagar errores del canal o del disco; el llamador decide cómo presentarlos. |
| `herramientas` | `herramientas(self) -> list` | Implementa la operación interna indicada por su nombre. | Puede propagar errores del canal o del disco; el llamador decide cómo presentarlos. |
| `ejecutar` | `ejecutar(self, nombre: str, argumentos: dict) -> str` | Implementa la operación interna indicada por su nombre. | Puede propagar errores del canal o del disco; el llamador decide cómo presentarlos. |

**Constantes de módulo:** `MAX_SALIDA`.

## `buildai/connectors/__init__.py`

`CONECTORES` es el registro de instancias. `conectores_disponibles` prueba cada instancia y `buscar_herramienta` solo resuelve una herramienta perteneciente a un conector disponible.

| Símbolo | Firma o tipo | Qué hace y qué devuelve | Casos borde y estado |
|---|---|---|---|
| `conectores_disponibles` | `conectores_disponibles()` | Devuelve conectores actualmente disponibles. | Puede propagar errores del canal o del disco; el llamador decide cómo presentarlos. |
| `buscar_herramienta` | `buscar_herramienta(nombre: str)` | Busca una herramienta por nombre. | Puede propagar errores del canal o del disco; el llamador decide cómo presentarlos. |

**Constantes de módulo:** `CONECTORES`.

## `buildai/connectors/autocad.py`

El conector inicializa COM y obtiene el documento activo. `autocad_informacion` requiere al menos un dibujo; `autocad_ejecutar_python` expone `acad`, `doc`, `ms`, `punto` y `puntos`; `autocad_comando` envía el campo `orden`. AutoCAD LT no ofrece el canal COM requerido.

| Símbolo | Firma o tipo | Qué hace y qué devuelve | Casos borde y estado |
|---|---|---|---|
| `ConectorAutoCAD` | clase, hereda de `Conector` | `id="autocad"`, `nombre="AutoCAD"`; `ayuda` explica que no requiere addon, solo COM de Windows. | No expone estado propio entre llamadas; cada `ejecutar` obtiene el documento activo de nuevo. |
| `_obtener_acad` | `_obtener_acad()` | Obtiene una instancia COM de AutoCAD. | Helper interno; no constituye API estable. |
| `disponible` | `disponible(self) -> bool` | Comprueba AutoCAD mediante COM. | Puede propagar errores del canal o del disco; el llamador decide cómo presentarlos. |
| `herramientas` | `herramientas(self) -> list` | Declara las herramientas de AutoCAD. | Puede propagar errores del canal o del disco; el llamador decide cómo presentarlos. |
| `ejecutar` | `ejecutar(self, nombre: str, argumentos: dict) -> str` | Ejecuta Python u orden COM y recorta salida. | Puede propagar errores del canal o del disco; el llamador decide cómo presentarlos. |
| `punto` | `punto(x, y, z=0.0)` | Crea un punto COM. | Puede propagar errores del canal o del disco; el llamador decide cómo presentarlos. |
| `puntos` | `puntos(lista)` | Convierte una lista a puntos COM. | Puede propagar errores del canal o del disco; el llamador decide cómo presentarlos. |

**Constantes de módulo:** `_PROG_IDS`.

## `buildai/connectors/blender.py`

El transporte usa una línea JSON por socket TCP. `disponible` envía `ping`; `ejecutar` antepone `KIT_FUENTE`, compila el código con nombre `<codigo>` y usa 600 segundos de timeout local, enviando 570 al puente para permitir renders largos.

| Símbolo | Firma o tipo | Qué hace y qué devuelve | Casos borde y estado |
|---|---|---|---|
| `ConectorBlender` | clase, hereda de `Conector` | `id="blender"`, `nombre="Blender"`; `ayuda` describe la conexión automática del puente para todas las versiones instaladas (2.80+). | No mantiene socket abierto entre llamadas; cada `_enviar` abre y cierra su propia conexión TCP. |
| `_enviar` | `_enviar(peticion: dict, timeout: float=60.0) -> dict` | Envía JSON por socket local y espera respuesta. | Helper interno; no constituye API estable. |
| `disponible` | `disponible(self) -> bool` | Comprueba ping de Blender. | Puede propagar errores del canal o del disco; el llamador decide cómo presentarlos. |
| `herramientas` | `herramientas(self) -> list` | Declara las herramientas de Blender. | Puede propagar errores del canal o del disco; el llamador decide cómo presentarlos. |
| `ejecutar` | `ejecutar(self, nombre: str, argumentos: dict) -> str` | Anteponer kit y ejecuta Python en Blender. | Puede propagar errores del canal o del disco; el llamador decide cómo presentarlos. |

**Constantes de módulo:** `PUERTO_BLENDER`, `KIT_FUENTE`, `REFERENCIA_KIT`.

## `buildai/connectors/sketchup.py`

El conector llama al bridge HTTP local y delega la ejecución Ruby. El bridge encola cada petición y la procesa en el hilo principal de SketchUp; el sondeo HTTP tiene un límite de 120 segundos.

| Símbolo | Firma o tipo | Qué hace y qué devuelve | Casos borde y estado |
|---|---|---|---|
| `ConectorSketchUp` | clase, hereda de `Conector` | `id="sketchup"`, `nombre="SketchUp"`; `ayuda` describe la extensión instalada automáticamente para todas las versiones (2014+). | No mantiene estado propio; cada llamada es una petición HTTP independiente al bridge. |
| `disponible` | `disponible(self) -> bool` | Comprueba GET /ping. | Puede propagar errores del canal o del disco; el llamador decide cómo presentarlos. |
| `herramientas` | `herramientas(self) -> list` | Declara las herramientas de SketchUp. | Puede propagar errores del canal o del disco; el llamador decide cómo presentarlos. |
| `ejecutar` | `ejecutar(self, nombre: str, argumentos: dict) -> str` | Envía Ruby a POST /ejecutar. | Puede propagar errores del canal o del disco; el llamador decide cómo presentarlos. |

**Constantes de módulo:** `PUERTO_SKETCHUP`, `BASE`.

## `buildai/connectors/revit.py`

El bridge de Routes expone `/ping`, `/info` y `/ejecutar` bajo `/buildai`. El conector antepone `KIT_FUENTE`, retira la cabecera de codificación incompatible con IronPython 2 y recorta la respuesta textual.

| Símbolo | Firma o tipo | Qué hace y qué devuelve | Casos borde y estado |
|---|---|---|---|
| `ConectorRevit` | clase, hereda de `Conector` | `id="revit"`, `nombre="Revit"`; `ayuda` indica que requiere pyRevit (gratuito, 2014+) instalado por el usuario. | No mantiene estado propio; depende de que el bridge de Routes esté cargado en Revit. |
| `disponible` | `disponible(self) -> bool` | Comprueba Routes /ping. | Puede propagar errores del canal o del disco; el llamador decide cómo presentarlos. |
| `herramientas` | `herramientas(self) -> list` | Declara las herramientas de Revit. | Puede propagar errores del canal o del disco; el llamador decide cómo presentarlos. |
| `ejecutar` | `ejecutar(self, nombre: str, argumentos: dict) -> str` | Anteponer kit y envía Python a Routes. | Puede propagar errores del canal o del disco; el llamador decide cómo presentarlos. |

**Constantes de módulo:** `PUERTO_REVIT`, `BASE`, `KIT_FUENTE`.

## `buildai/providers/base.py`

`LlamadaHerramienta` y `RespuestaLLM` forman el formato neutro; `ErrorProveedor` normaliza fallos mostrables. `Proveedor.conversar` es una interfaz abstracta documentada para que cada adaptador traduzca el historial sin contaminar las sesiones.

| Símbolo | Firma o tipo | Qué hace y qué devuelve | Casos borde y estado |
|---|---|---|---|
| `ErrorProveedor` | clase, hereda de `Exception` | Excepción usada por los adaptadores para envolver fallos de red, autenticación o cuota con un mensaje apto para mostrar al usuario. | Sin atributos propios; el mensaje va en el `str()` de la excepción. |
| `LlamadaHerramienta` | `@dataclass`: `id: str`, `nombre: str`, `argumentos: dict` | Representa una petición de tool calling emitida por el modelo dentro de `RespuestaLLM.llamadas`. | Estructura de solo datos; cada adaptador la construye al traducir la respuesta de su API. |
| `RespuestaLLM` | `@dataclass`: `texto: str=""`, `llamadas: list=[]`, `raw: object=None` | Formato neutro de salida de `Proveedor.conversar`; `raw` guarda los bloques originales del proveedor para reenviarlos en el siguiente turno (p. ej. `thinking`/`tool_use` de Anthropic). | `llamadas` puede quedar vacía si el modelo no invoca herramientas. |
| `Proveedor` | clase | Contrato abstracto que implementan `ProveedorAnthropic` y `ProveedorOpenAICompatible`; expone `notificar`, un callback opcional que el agente asigna para mostrar esperas y reintentos. | `notificar` es `None` por defecto; `conversar` lanza `NotImplementedError` si no se sobreescribe. |
| `conversar` | `conversar(self, sistema: str, historial: list, herramientas: list) -> RespuestaLLM` | Implementa la operación interna indicada por su nombre. | Puede propagar errores del canal o del disco; el llamador decide cómo presentarlos. |

## `buildai/providers/__init__.py`

| Símbolo | Firma o tipo | Qué hace y qué devuelve | Casos borde y estado |
|---|---|---|---|
| `crear_proveedor` | `crear_proveedor(config: dict)` | Crea el adaptador según la configuración. | Puede propagar errores del canal o del disco; el llamador decide cómo presentarlos. |

## `buildai/providers/anthropic_provider.py`

Anthropic recibe imágenes como bloques base64 y conserva los bloques originales en `raw` para reenviar `thinking` y `tool_use`. `conversar` usa `max_tokens` 16000 y thinking adaptativo; autenticación, rate limit, rechazo, estado HTTP y conexión se convierten a `ErrorProveedor`.

| Símbolo | Firma o tipo | Qué hace y qué devuelve | Casos borde y estado |
|---|---|---|---|
| `ProveedorAnthropic` | clase, hereda de `Proveedor` | Guarda `clave` y `modelo` (por defecto `claude-opus-4-8` si no se especifica). | Sin caché ni reintentos propios; cada `conversar` es una llamada directa al SDK de Anthropic. |
| `__init__` | `__init__(self, clave: str, modelo: str)` | Guarda clave y modelo. | Helper interno; no constituye API estable. |
| `_convertir_historial` | `_convertir_historial(self, historial: list) -> list` | Traduce el historial al formato Anthropic. | Helper interno; no constituye API estable. |
| `conversar` | `conversar(self, sistema: str, historial: list, herramientas: list) -> RespuestaLLM` | Realiza una llamada Claude y devuelve RespuestaLLM. | Puede propagar errores del canal o del disco; el llamador decide cómo presentarlos. |

## `buildai/providers/openai_compat.py`

El adaptador envía `/chat/completions`. Convierte usuario, asistente y resultado a `messages`, serializa llamadas como `tool_calls` y reconstruye sus argumentos JSON. Reintenta `429`, `408`, 5xx y errores de red hasta `_MAX_REINTENTOS`; usa espera inicial `_ESPERA_INICIAL`, tope `_ESPERA_MAXIMA` y `Retry-After` cuando es válido.

| Símbolo | Firma o tipo | Qué hace y qué devuelve | Casos borde y estado |
|---|---|---|---|
| `ProveedorOpenAICompatible` | clase, hereda de `Proveedor` | Guarda `base_url`, `clave`, `modelo`, `nombre` y `timeout` (180s por defecto); usado para OpenAI, OpenRouter y cualquier API compatible con Chat Completions. | `_respetar_ritmo` añade una pausa fija solo cuando `nombre` corresponde al plan gratuito de OpenRouter. |
| `__init__` | `__init__(self, base_url: str, clave: str, modelo: str, nombre: str, timeout: float=180.0)` | Configura endpoint, credenciales, modelo y timeout. | Helper interno; no constituye API estable. |
| `_cabeceras` | `_cabeceras(self) -> dict` | Construye cabeceras HTTP. | Helper interno; no constituye API estable. |
| `_convertir_historial` | `_convertir_historial(self, sistema: str, historial: list) -> list` | Traduce historial a Chat Completions. | Helper interno; no constituye API estable. |
| `_avisar` | `_avisar(self, texto: str) -> None` | Notifica estado al callback configurado. | Helper interno; no constituye API estable. |
| `_respetar_ritmo` | `_respetar_ritmo(self) -> None` | Aplica intervalo especial a OpenRouter free. | Helper interno; no constituye API estable. |
| `_espera_reintento` | `_espera_reintento(respuesta, espera: float) -> float` | Calcula espera progresiva y Retry-After. | Helper interno; no constituye API estable. |
| `_mensaje_agotado` | `_mensaje_agotado(self, codigo: int) -> str` | Genera mensaje para respuestas agotadas. | Helper interno; no constituye API estable. |
| `conversar` | `conversar(self, sistema: str, historial: list, herramientas: list) -> RespuestaLLM` | Realiza llamada con reintentos y devuelve RespuestaLLM. | Puede propagar errores del canal o del disco; el llamador decide cómo presentarlos. |

**Constantes de módulo:** `_MAX_REINTENTOS`, `_ESPERA_INICIAL`, `_ESPERA_MAXIMA`, `_INTERVALO_FREE`.

## `buildai/connectors/blender_kit.py`

Funciones públicas agrupadas por familia. Estas son las que el prompt del conector ofrece al modelo; las privadas se enumeran después.

| Familia | Función y firma exacta | Qué hace y devuelve | Notas |
|---|---|---|---|
| Terreno y estructura | `caja(nombre, origen, dimensiones, material='gris_claro', capa=None)` | Crea o modifica elementos en la escena/modelo y devuelve el objeto cuando el código lo hace. | Unidades y defaults son los de la firma. |
| Terreno y estructura | `limpiar_todo()` | Crea o modifica elementos en la escena/modelo y devuelve el objeto cuando el código lo hace. | Unidades y defaults son los de la firma. |
| Terreno y estructura | `muro(inicio, fin, alto=2.7, espesor=0.2, nivel=0.0, huecos=None, material='blanco', capa=None, nombre=None)` | Crea o modifica elementos en la escena/modelo y devuelve el objeto cuando el código lo hace. | Unidades y defaults son los de la firma. |
| Terreno y estructura | `ventanal(inicio, fin, alto=2.5, nivel=0.0, division=1.2, capa=None)` | Crea o modifica elementos en la escena/modelo y devuelve el objeto cuando el código lo hace. | Unidades y defaults son los de la firma. |
| Terreno y estructura | `forjado(contorno, nivel=0.0, espesor=0.3, material='hormigon', capa=None, nombre=None)` | Crea o modifica elementos en la escena/modelo y devuelve el objeto cuando el código lo hace. | Unidades y defaults son los de la firma. |
| Terreno y estructura | `escalera(origen, direccion='+x', ancho=1.0, alto_total=2.7, nivel=0.0, huella=0.28, material='hormigon', capa=None)` | Crea o modifica elementos en la escena/modelo y devuelve el objeto cuando el código lo hace. | Unidades y defaults son los de la firma. |
| Terreno y estructura | `barandilla(inicio, fin, nivel=0.0, alto=1.0, capa=None)` | Crea o modifica elementos en la escena/modelo y devuelve el objeto cuando el código lo hace. | Unidades y defaults son los de la firma. |
| Terreno y estructura | `rejilla_pilares(origen, num_x, num_y, sep_x, sep_y, alto, nivel=0.0, lado=0.3, material='hormigon', capa=None)` | Crea o modifica elementos en la escena/modelo y devuelve el objeto cuando el código lo hace. | Unidades y defaults son los de la firma. |
| Terreno y estructura | `terreno(ancho=60, fondo=60, centro=(0, 0), material='cesped', capa=None, ondulacion=0.0)` | Crea o modifica elementos en la escena/modelo y devuelve el objeto cuando el código lo hace. | Unidades y defaults son los de la firma. |
| Cubiertas | `cubierta_plana(contorno, nivel, espesor=0.3, peto=0.6, material='hormigon', capa=None)` | Crea o modifica elementos en la escena/modelo y devuelve el objeto cuando el código lo hace. | Unidades y defaults son los de la firma. |
| Cubiertas | `cubierta_dos_aguas(origen, ancho, fondo, nivel, pendiente=30, alero=0.5, eje='x', material='teja', capa=None)` | Crea o modifica elementos en la escena/modelo y devuelve el objeto cuando el código lo hace. | Unidades y defaults son los de la firma. |
| Mobiliario y estancias | `cama(origen, ancho=1.5, largo=2.0, rotacion=0, nivel=0.0, capa=None, ropa='tela_azul', madera='madera_clara')` | Crea o modifica elementos en la escena/modelo y devuelve el objeto cuando el código lo hace. | Unidades y defaults son los de la firma. |
| Mobiliario y estancias | `mesita_noche(origen, ancho=0.45, rotacion=0, nivel=0.0, capa=None, material='madera_clara')` | Crea o modifica elementos en la escena/modelo y devuelve el objeto cuando el código lo hace. | Unidades y defaults son los de la firma. |
| Mobiliario y estancias | `mesa(origen, ancho=1.6, fondo=0.9, alto=0.75, rotacion=0, nivel=0.0, capa=None, material='madera')` | Crea o modifica elementos en la escena/modelo y devuelve el objeto cuando el código lo hace. | Unidades y defaults son los de la firma. |
| Mobiliario y estancias | `silla(origen, rotacion=0, nivel=0.0, capa=None, material='madera', tapizado='tela_gris')` | Crea o modifica elementos en la escena/modelo y devuelve el objeto cuando el código lo hace. | Unidades y defaults son los de la firma. |
| Mobiliario y estancias | `sofa(origen, plazas=3, rotacion=0, nivel=0.0, capa=None, tela='tela_gris')` | Crea o modifica elementos en la escena/modelo y devuelve el objeto cuando el código lo hace. | Unidades y defaults son los de la firma. |
| Mobiliario y estancias | `sillon(origen, rotacion=0, nivel=0.0, capa=None, tela='tela_beige')` | Crea o modifica elementos en la escena/modelo y devuelve el objeto cuando el código lo hace. | Unidades y defaults son los de la firma. |
| Mobiliario y estancias | `comedor(origen, comensales=6, rotacion=0, nivel=0.0, capa=None, material='madera')` | Crea o modifica elementos en la escena/modelo y devuelve el objeto cuando el código lo hace. | Unidades y defaults son los de la firma. |
| Mobiliario y estancias | `armario(origen, ancho=2.0, alto=2.2, fondo=0.6, rotacion=0, nivel=0.0, capa=None, material='madera_clara')` | Crea o modifica elementos en la escena/modelo y devuelve el objeto cuando el código lo hace. | Unidades y defaults son los de la firma. |
| Mobiliario y estancias | `estanteria(origen, ancho=0.9, alto=1.8, fondo=0.35, baldas=4, rotacion=0, nivel=0.0, capa=None, material='madera')` | Crea o modifica elementos en la escena/modelo y devuelve el objeto cuando el código lo hace. | Unidades y defaults son los de la firma. |
| Mobiliario y estancias | `cocina(origen, largo=3.0, rotacion=0, nivel=0.0, capa=None, con_altos=True, mueble='madera_clara', encimera='marmol')` | Crea o modifica elementos en la escena/modelo y devuelve el objeto cuando el código lo hace. | Unidades y defaults son los de la firma. |
| Mobiliario y estancias | `lavabo(origen, ancho=0.8, rotacion=0, nivel=0.0, capa=None)` | Crea o modifica elementos en la escena/modelo y devuelve el objeto cuando el código lo hace. | Unidades y defaults son los de la firma. |
| Mobiliario y estancias | `inodoro(origen, rotacion=0, nivel=0.0, capa=None)` | Crea o modifica elementos en la escena/modelo y devuelve el objeto cuando el código lo hace. | Unidades y defaults son los de la firma. |
| Mobiliario y estancias | `ducha(origen, ancho=0.9, fondo=0.9, rotacion=0, nivel=0.0, capa=None)` | Crea o modifica elementos en la escena/modelo y devuelve el objeto cuando el código lo hace. | Unidades y defaults son los de la firma. |
| Mobiliario y estancias | `banera(origen, largo=1.7, ancho=0.75, rotacion=0, nivel=0.0, capa=None)` | Crea o modifica elementos en la escena/modelo y devuelve el objeto cuando el código lo hace. | Unidades y defaults son los de la firma. |
| Mobiliario y estancias | `alfombra(origen, ancho=2.5, fondo=1.8, rotacion=0, nivel=0.0, capa=None, material='tela_beige')` | Crea o modifica elementos en la escena/modelo y devuelve el objeto cuando el código lo hace. | Unidades y defaults son los de la firma. |
| Mobiliario y estancias | `cuadro(posicion, ancho=0.8, alto=0.6, altura_centro=1.5, rotacion=0, nivel=0.0, capa=None, color=(0.35, 0.42, 0.5))` | Crea o modifica elementos en la escena/modelo y devuelve el objeto cuando el código lo hace. | Unidades y defaults son los de la firma. |
| Mobiliario y estancias | `espejo_pared(posicion, ancho=0.6, alto=1.0, altura_centro=1.5, rotacion=0, nivel=0.0, capa=None)` | Crea o modifica elementos en la escena/modelo y devuelve el objeto cuando el código lo hace. | Unidades y defaults son los de la firma. |
| Mobiliario y estancias | `television(posicion, pulgadas=55, altura=1.0, rotacion=0, nivel=0.0, capa=None)` | Crea o modifica elementos en la escena/modelo y devuelve el objeto cuando el código lo hace. | Unidades y defaults son los de la firma. |
| Mobiliario y estancias | `planta_decorativa(centro, alto=1.3, nivel=0.0, capa=None)` | Crea o modifica elementos en la escena/modelo y devuelve el objeto cuando el código lo hace. | Unidades y defaults son los de la firma. |
| Mobiliario y estancias | `dormitorio(origen, ancho, fondo, pared_cama='S', nivel=0.0, capa=None, ropa='tela_azul', madera='madera_clara', altura_techo=2.7)` | Crea o modifica elementos en la escena/modelo y devuelve el objeto cuando el código lo hace. | Unidades y defaults son los de la firma. |
| Mobiliario y estancias | `salon(origen, ancho, fondo, pared_sofa='S', nivel=0.0, capa=None, tela='tela_gris', altura_techo=2.7)` | Crea o modifica elementos en la escena/modelo y devuelve el objeto cuando el código lo hace. | Unidades y defaults son los de la firma. |
| Mobiliario y estancias | `bano(origen, ancho, fondo, pared_aparatos='S', nivel=0.0, capa=None, con_ducha=True, altura_techo=2.7)` | Crea o modifica elementos en la escena/modelo y devuelve el objeto cuando el código lo hace. | Unidades y defaults son los de la firma. |
| Exterior | `piscina(origen, ancho=8.0, fondo=4.0, profundidad=1.5, borde=0.6, nivel=0.0, rotacion=0, luces=2, capa=None, material_borde='pavimento')` | Crea o modifica elementos en la escena/modelo y devuelve el objeto cuando el código lo hace. | Unidades y defaults son los de la firma. |
| Exterior | `arbol(centro, alto=6.0, tipo='frondoso', nivel=0.0, capa=None, semilla=None)` | Crea o modifica elementos en la escena/modelo y devuelve el objeto cuando el código lo hace. | Unidades y defaults son los de la firma. |
| Exterior | `arbusto(centro, alto=0.7, nivel=0.0, capa=None, semilla=None)` | Crea o modifica elementos en la escena/modelo y devuelve el objeto cuando el código lo hace. | Unidades y defaults son los de la firma. |
| Exterior | `seto(inicio, fin, alto=1.2, espesor=0.5, nivel=0.0, capa=None)` | Crea o modifica elementos en la escena/modelo y devuelve el objeto cuando el código lo hace. | Unidades y defaults son los de la firma. |
| Exterior | `tumbona(origen, rotacion=0, nivel=0.0, capa=None, tela='tela_beige')` | Crea o modifica elementos en la escena/modelo y devuelve el objeto cuando el código lo hace. | Unidades y defaults son los de la firma. |
| Exterior | `barbacoa(centro, nivel=0.0, capa=None)` | Crea o modifica elementos en la escena/modelo y devuelve el objeto cuando el código lo hace. | Unidades y defaults son los de la firma. |
| Exterior | `celosia(inicio, fin, alto=2.5, nivel=0.0, orientacion='vertical', separacion=0.12, espesor=0.04, capa=None, material='madera')` | Crea o modifica elementos en la escena/modelo y devuelve el objeto cuando el código lo hace. | Unidades y defaults son los de la firma. |
| Exterior | `pergola(origen, ancho=4.0, fondo=3.0, altura=2.4, rotacion=0, nivel=0.0, capa=None, material='madera', lamas=True)` | Crea o modifica elementos en la escena/modelo y devuelve el objeto cuando el código lo hace. | Unidades y defaults son los de la firma. |
| Exterior | `valla(inicio, fin, alto=1.6, nivel=0.0, tipo='tablas', capa=None, material='madera')` | Crea o modifica elementos en la escena/modelo y devuelve el objeto cuando el código lo hace. | Unidades y defaults son los de la firma. |
| Exterior | `camino(inicio, fin, ancho=1.2, nivel=0.0, material='pavimento', capa=None)` | Crea o modifica elementos en la escena/modelo y devuelve el objeto cuando el código lo hace. | Unidades y defaults son los de la firma. |
| Exterior | `palmera(centro, alto=7.0, nivel=0.0, capa=None)` | Crea o modifica elementos en la escena/modelo y devuelve el objeto cuando el código lo hace. | Unidades y defaults son los de la firma. |
| Exterior | `farola(posicion, alto=4.0, nivel=0.0, fuerza=120, capa=None)` | Crea o modifica elementos en la escena/modelo y devuelve el objeto cuando el código lo hace. | Unidades y defaults son los de la firma. |
| Exterior | `coche(origen, rotacion=0, nivel=0.0, color=(0.15, 0.16, 0.18), capa=None)` | Crea o modifica elementos en la escena/modelo y devuelve el objeto cuando el código lo hace. | Unidades y defaults son los de la firma. |
| Materiales | `material(nombre, color=None, rugosidad=None, metalico=None, transparente=None, textura=None, escala=None, emision=None)` | Crea o modifica elementos en la escena/modelo y devuelve el objeto cuando el código lo hace. | Unidades y defaults son los de la firma. |
| Iluminación | `sol(elevacion=35, azimut=200, fuerza=3.0)` | Crea o modifica elementos en la escena/modelo y devuelve el objeto cuando el código lo hace. | Unidades y defaults son los de la firma. |
| Iluminación | `luz_interior(posicion, fuerza=40, calida=True)` | Crea o modifica elementos en la escena/modelo y devuelve el objeto cuando el código lo hace. | Unidades y defaults son los de la firma. |
| Iluminación | `lampara_colgante(posicion, altura_techo=2.7, descuelgue=0.9, nivel=0.0, fuerza=70, capa=None)` | Crea o modifica elementos en la escena/modelo y devuelve el objeto cuando el código lo hace. | Unidades y defaults son los de la firma. |
| Iluminación | `lampara_pie(centro, nivel=0.0, fuerza=50, capa=None)` | Crea o modifica elementos en la escena/modelo y devuelve el objeto cuando el código lo hace. | Unidades y defaults son los de la firma. |
| Iluminación | `foco_empotrado(posicion, altura_techo=2.7, nivel=0.0, fuerza=75, capa=None)` | Crea o modifica elementos en la escena/modelo y devuelve el objeto cuando el código lo hace. | Unidades y defaults son los de la firma. |
| Iluminación | `foco_jardin(posicion, nivel=0.0, fuerza=40, capa=None)` | Crea o modifica elementos en la escena/modelo y devuelve el objeto cuando el código lo hace. | Unidades y defaults son los de la firma. |
| Iluminación | `cielo(momento='dia', azimut=200, intensidad=None)` | Crea o modifica elementos en la escena/modelo y devuelve el objeto cuando el código lo hace. | Unidades y defaults son los de la firma. |
| Cámara y render | `camara(objetivo=(0, 0, 2), distancia=20, azimut=225, altura=6, lente=50, apertura=None)` | Crea o modifica elementos en la escena/modelo y devuelve el objeto cuando el código lo hace. | Unidades y defaults son los de la firma. |
| Cámara y render | `revisar_escena()` | Crea o modifica elementos en la escena/modelo y devuelve el objeto cuando el código lo hace. | Unidades y defaults son los de la firma. |
| Cámara y render | `render(ruta=None, calidad='media', ancho=None, alto=None)` | Guarda PNG y devuelve texto con la marca de render. | Unidades y defaults son los de la firma. |
| Utilidades públicas | `coleccion(nombre)` | Obtiene o crea la colección de Blender indicada. | Se usa para organizar elementos por capas lógicas. |
| Utilidades públicas | `convertir(u, v)` | Utilidad de unidades o compatibilidad; consultar implementación. | Unidades y defaults son los de la firma. |
| Utilidades públicas | `_mundo(u, v)` | Utilidad de unidades o compatibilidad; consultar implementación. | Unidades y defaults son los de la firma. |
| Utilidades públicas | `jit(v, frac)` | Utilidad de unidades o compatibilidad; consultar implementación. | Unidades y defaults son los de la firma. |

**Funciones privadas o auxiliares:** `_entrada`, `_conectar_relieve`, `_nodos_textura`, `_mat`, `_nuevo_objeto`, `_agregar_caja`, `_agregar_cilindro`, `_agregar_esfera`, `_malla_piezas`, `_malla_cajas`, `_colocar`, `_sin_sombra`, `_local_a_mundo`, `_carpinteria`, `_contorno_ccw`, `_malla_grid_ondulada`, `_quitar_objetos`, `_crear_sol`, `_suavizar`, `_pieza`, `_situar`, `_luz_puntual`, `_luz_foco`, `_sobre_pared`, `_mat_vegetacion`, `_mat_corteza`, `_fijar`, `_activar_gpu`, `_activar_resplandor`, `_vidrios_opacos_cycles`, `_auto_camara`.
**Constantes:** `_PRESETS`, `_RELIEVE`, `_CARAS_CAJA`, `_OPUESTA`, `_VEG_VARIANTES`, `_MOMENTOS`, `CARPETA_RENDERS`, `_CALIDADES`.

## `buildai/connectors/revit_kit.py`

Funciones públicas agrupadas por familia. Estas son las que el prompt del conector ofrece al modelo; las privadas se enumeran después.

| Familia | Función y firma exacta | Qué hace y devuelve | Notas |
|---|---|---|---|
| Conversiones y salida | `xyz(x, y, z=0.0)` | Crea o modifica elementos en la escena/modelo y devuelve el objeto cuando el código lo hace. | Unidades y defaults son los de la firma. |
| Conversiones y salida | `imprimir(texto)` | Crea o modifica elementos en la escena/modelo y devuelve el objeto cuando el código lo hace. | Unidades y defaults son los de la firma. |
| Niveles | `niveles()` | Crea o modifica elementos en la escena/modelo y devuelve el objeto cuando el código lo hace. | Unidades y defaults son los de la firma. |
| Niveles | `nivel(altura, nombre=None)` | Crea o modifica elementos en la escena/modelo y devuelve el objeto cuando el código lo hace. | Unidades y defaults son los de la firma. |
| Muros y suelos | `tipo_muro(nombre=None)` | Crea o modifica elementos en la escena/modelo y devuelve el objeto cuando el código lo hace. | Unidades y defaults son los de la firma. |
| Muros y suelos | `muro(inicio, fin, nivel_base, altura=2.7, tipo=None, estructural=False)` | Crea o modifica elementos en la escena/modelo y devuelve el objeto cuando el código lo hace. | Unidades y defaults son los de la firma. |
| Muros y suelos | `suelo(contorno, nivel_base, tipo=None)` | Crea o modifica elementos en la escena/modelo y devuelve el objeto cuando el código lo hace. | Unidades y defaults son los de la firma. |
| Familias y símbolos | `familias(categoria='puertas')` | Crea o modifica elementos en la escena/modelo y devuelve el objeto cuando el código lo hace. | Unidades y defaults son los de la firma. |
| Puertas y ventanas | `puerta(muro_obj, a, nivel_base, tipo=None)` | Crea o modifica elementos en la escena/modelo y devuelve el objeto cuando el código lo hace. | Unidades y defaults son los de la firma. |
| Puertas y ventanas | `ventana(muro_obj, a, nivel_base, antepecho=0.9, tipo=None)` | Crea o modifica elementos en la escena/modelo y devuelve el objeto cuando el código lo hace. | Unidades y defaults son los de la firma. |
| Colocación y pilares | `colocar(categoria, posicion, nivel_base, rotacion=0, tipo=None)` | Crea o modifica elementos en la escena/modelo y devuelve el objeto cuando el código lo hace. | Unidades y defaults son los de la firma. |
| Colocación y pilares | `pilar(posicion, nivel_base, rotacion=0, tipo=None)` | Crea o modifica elementos en la escena/modelo y devuelve el objeto cuando el código lo hace. | Unidades y defaults son los de la firma. |
| Borrado | `borrar(elemento)` | Crea o modifica elementos en la escena/modelo y devuelve el objeto cuando el código lo hace. | Unidades y defaults son los de la firma. |

**Funciones privadas o auxiliares:** `_a_pies`, `_a_metros`, `_elementos`, `_tipo_suelo`, `_simbolos`, `_buscar_simbolo`, `_activar`.
**Constantes:** `_PIES_POR_METRO`, `_CATEGORIAS`.

## `buildai/addons/blender/buildai_blender.py`

| Símbolo | Firma o tipo | Qué hace y devuelve | Notas |
|---|---|---|---|
| `_info_escena` | `_info_escena() -> str` | Prueba o helper de la suite. | No depende de CAD abierto. |
| `_procesar` | `_procesar(peticion: dict) -> dict` | Prueba o helper de la suite. | No depende de CAD abierto. |
| `_bombear_trabajos` | `_bombear_trabajos()` | Prueba o helper de la suite. | No depende de CAD abierto. |
| `_atender_cliente` | `_atender_cliente(conexion: socket.socket)` | Prueba o helper de la suite. | No depende de CAD abierto. |
| `_bucle_servidor` | `_bucle_servidor(servidor: socket.socket)` | Prueba o helper de la suite. | No depende de CAD abierto. |
| `register` | `register()` | Prueba o helper de la suite. | No depende de CAD abierto. |
| `unregister` | `unregister()` | Prueba o helper de la suite. | No depende de CAD abierto. |
| constantes | `PUERTO` | Datos de prueba. | |

## `buildai/addons/revit/BuildAI.extension/startup.py`

| Símbolo | Firma o tipo | Qué hace y devuelve | Notas |
|---|---|---|---|
| `_contar` | `_contar(coleccion)` | Prueba o helper de la suite. | No depende de CAD abierto. |
| `ping` | `ping(request)` | Prueba o helper de la suite. | No depende de CAD abierto. |
| `info` | `info(request)` | Prueba o helper de la suite. | No depende de CAD abierto. |
| `ejecutar` | `ejecutar(request)` | Prueba o helper de la suite. | No depende de CAD abierto. |

## `buildai/addons/sketchup/buildai_sketchup.rb`

El archivo Ruby implementa el bridge y sus métodos de cola/timer; los nombres se mantienen en [06](06-conectores.md).

## `build_pkg/run_buildai.py`

| Símbolo | Firma o tipo | Qué hace y devuelve | Notas |
|---|---|---|---|

## `build_pkg/buildai.spec`

Configuración declarativa de PyInstaller: entry point, datos incluidos, hidden imports y modo onedir sin consola.

## `tests/test_adjuntos_historial.py`

| Símbolo | Firma o tipo | Qué hace y devuelve | Notas |
|---|---|---|---|
| `TestAdjuntosHistorial` | clase de pruebas | Agrupa regresiones. | Requiere pytest. |
| `_historial_dos_turnos` | `_historial_dos_turnos()` | Prueba o helper de la suite. | No depende de CAD abierto. |
| `test_imagenes_viejas_no_se_reenvian` | `test_imagenes_viejas_no_se_reenvian(self)` | Prueba o helper de la suite. | No depende de CAD abierto. |
| `test_no_muta_el_historial_original` | `test_no_muta_el_historial_original(self)` | Prueba o helper de la suite. | No depende de CAD abierto. |
| `test_texto_del_turno_viejo_se_conserva` | `test_texto_del_turno_viejo_se_conserva(self)` | Prueba o helper de la suite. | No depende de CAD abierto. |
| constantes | `IMG_VIEJA`, `IMG_ACTUAL` | Datos de prueba. | |

## `tests/test_sanear_adjuntos.py`

| Símbolo | Firma o tipo | Qué hace y devuelve | Notas |
|---|---|---|---|
| `TestSanearAdjuntos` | clase de pruebas | Agrupa regresiones. | Requiere pytest. |
| `test_entradas_invalidas_no_gastan_cupo` | `test_entradas_invalidas_no_gastan_cupo(self)` | Prueba o helper de la suite. | No depende de CAD abierto. |
| `test_se_respeta_el_tope_con_todo_valido` | `test_se_respeta_el_tope_con_todo_valido(self)` | Prueba o helper de la suite. | No depende de CAD abierto. |
| `test_descarta_no_imagenes_y_base64_invalido` | `test_descarta_no_imagenes_y_base64_invalido(self)` | Prueba o helper de la suite. | No depende de CAD abierto. |
| constantes | `_IMG` | Datos de prueba. | |

## Locks, cache y límites

La configuración usa el lock de `config`; `main` usa `_ocupado` para serializar el turno y una `queue` para SSE. Memoria y modelos tienen cache con firma o TTL. Los límites del agente son `MAX_PASOS`, `MAX_HISTORIAL`, `MAX_RESULTADO`, `RESULTADO_ANTIGUO_MAX` y `ENTRADAS_SIN_COMPRIMIR`; adjuntos y renders se validan en `main`.
