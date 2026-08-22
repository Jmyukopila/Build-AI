# 05 · Módulos y funciones

Las tablas se generaron contrastando nombres y firmas con el AST del árbol actual. Las firmas incluyen los parámetros declarados; los retornos solo aparecen cuando el código anota el retorno.

## `buildai/agent.py`

El turno crea el proveedor con la configuración activa, obtiene conectores disponibles y añade la entrada de usuario al historial. `ejecutar_turno` emite `estado`, `respuesta`, `herramienta`, `render` o `error`; al terminar sin llamadas devuelve la respuesta textual. Cada resultado recién obtenido se limita a `MAX_RESULTADO`; al alcanzar `MAX_PASOS` se añade una pausa de seguridad sin borrar lo avanzado.

| Símbolo | Firma o tipo | Qué hace y qué devuelve | Casos borde y estado |
|---|---|---|---|
| `renders_en_resultado` | `renders_en_resultado(resultado: str) -> list` | Valida cada marca `RENDER_GUARDADO:` contra la carpeta de renders y devuelve solo nombres de archivos seguros. | Captura `OSError` al comprobar la ruta y descarta esa marca; no escribe en disco. |
| `_sistema` | `_sistema(conectados: list) -> str` | Construye el prompt de sistema con capacidades y memoria. | Sin conectores lo dice en el propio prompt; el bloque de memoria solo se añade si `perfil_texto` devuelve algo. |
| `_herramientas` | `_herramientas(conectados: list) -> list` | Reúne los esquemas de herramientas conectadas. | Concatena los esquemas en el orden del registro `CONECTORES`; sin programas conectados devuelve lista vacía. |
| `_recortar_historial` | `_recortar_historial(historial: list) -> None` | Muta el historial eliminando turnos completos desde el inicio hasta quedar dentro de `MAX_HISTORIAL`. | Solo corta en entradas `usuario`; si no encuentra otro turno de usuario deja la lista intacta. |
| `_comprimir_resultados` | `_comprimir_resultados(historial: list) -> None` | Muta los resultados antiguos, limita su contenido a `RESULTADO_ANTIGUO_MAX` y conserva las marcas de render. | No modifica las últimas `ENTRADAS_SIN_COMPRIMIR` entradas ni resultados ya cortos. |
| `_historial_para_modelo` | `_historial_para_modelo(historial: list) -> list` | Construye una vista sin adjuntos de turnos cerrados y conserva el historial original sin mutarlo. | Solo el último mensaje `usuario` conserva imágenes; devuelve una lista de entradas. |
| `ejecutar_turno` | `ejecutar_turno(historial: list, mensaje_usuario: str, emitir, cancelado=None, adjuntos=None) -> None` | Coordina proveedor, conectores, llamadas de herramientas, límites de pasos y eventos del turno. | Emite `error` si falta proveedor, comprueba cancelación entre pasos y modifica el historial recibido in situ. |

**Constantes de módulo:** `CARPETA_RENDERS`, `_MARCA_RENDER`, `MAX_PASOS`, `MAX_HISTORIAL`, `MAX_RESULTADO`, `RESULTADO_ANTIGUO_MAX`, `ENTRADAS_SIN_COMPRIMIR`, `SISTEMA_BASE`.

## `buildai/config.py`

`cargar` parte de `_CONFIG_DEFECTO`, tolera un JSON inexistente, corrupto o incompleto y migra modelos retirados. `guardar` escribe el JSON con un lock de proceso. `clave_activa`, `proveedor_listo` y `modelo_activo` aceptan configuración opcional y, si no se entrega, cargan la persistida.

| Símbolo | Firma o tipo | Qué hace y qué devuelve | Casos borde y estado |
|---|---|---|---|
| `cargar` | `cargar() -> dict` | Combina el JSON persistido con `_CONFIG_DEFECTO` y migra modelos retirados. | Captura `JSONDecodeError` y `OSError` como configuración vacía; devuelve siempre las secciones normalizadas. |
| `guardar` | `guardar(config: dict) -> None` | Serializa la configuración y la escribe en `config.json` bajo un lock de proceso. | Crea el directorio padre; errores de escritura o permisos sí escapan. |
| `clave_activa` | `clave_activa(config: dict \| None=None) -> str` | Devuelve la clave del proveedor activo. | Recarga la configuración si no se le pasa una; un proveedor sin clave guardada devuelve cadena vacía. |
| `proveedor_listo` | `proveedor_listo(config: dict \| None=None) -> bool` | Indica si el proveedor activo está configurado. | Los proveedores con `requiere_clave` falso (Ollama) siempre dan `True` sin mirar las claves. |
| `modelo_activo` | `modelo_activo(config: dict \| None=None) -> str` | Devuelve el modelo seleccionado o el predeterminado. | Un valor vacío en `modelos` cae en `MODELOS_POR_DEFECTO`; un proveedor no listado ahí daría `KeyError`. |

**Constantes de módulo:** `OLLAMA_URL`, `MODELOS_POR_DEFECTO`, `_MODELOS_MIGRADOS`, `PROVEEDORES`, `_CONFIG_DEFECTO`.

## `buildai/rutas.py`

`CARPETA_DATOS` se basa en el directorio personal del usuario y no en `%APPDATA%`. La migración se ejecuta solo cuando falta el destino; la carpeta de sesiones la crea `sesiones.guardar` al escribir el primer JSON.

| Símbolo | Firma o tipo | Qué hace y qué devuelve | Casos borde y estado |
|---|---|---|---|
| `_migrar_si_hace_falta` | `_migrar_si_hace_falta(nombre: str) -> None` | Migra un archivo o carpeta histórica a `~/.buildai` únicamente si falta el destino. | Usa `copy2` o `copytree`; errores de copia no se absorben. |
| `ruta_config` | `ruta_config() -> Path` | Devuelve la ruta de config.json. | Dispara la migración de `config.json` en cada llamada y devuelve la ruta aunque el archivo aún no exista. |
| `carpeta_sesiones` | `carpeta_sesiones() -> Path` | Devuelve y prepara la carpeta de sesiones. | Migra la carpeta histórica solo si falta el destino; no crea el directorio, lo hace `guardar` al escribir. |

**Constantes de módulo:** `CARPETA_DATOS`, `_RAIZ_PROYECTO`.

## `buildai/sesiones.py`

Cada sesión se guarda como un JSON independiente. `_ruta` restringe el identificador a caracteres alfanuméricos antes de construir el nombre de archivo; `cargar` devuelve `None` cuando no existe y `borrar` ignora la ausencia del archivo. La serialización conserva las llamadas de herramienta y los campos originales necesarios para los adaptadores.

| Símbolo | Firma o tipo | Qué hace y qué devuelve | Casos borde y estado |
|---|---|---|---|
| `nuevo_id` | `nuevo_id() -> str` | Genera el identificador hexadecimal de una sesión. | Devuelve los 12 primeros dígitos hexadecimales de un UUID4, alfanuméricos como exige `_ruta`. |
| `_ruta` | `_ruta(sesion_id: str) -> Path` | Valida el identificador y construye su ruta JSON dentro de la carpeta de sesiones. | Lanza `ValueError` para ids no alfanuméricos antes de tocar el disco. |
| `_serializar` | `_serializar(historial: list) -> list` | Copia las entradas y convierte cada `LlamadaHerramienta` en un diccionario JSON. | No muta el historial original y conserva los demás campos. |
| `_deserializar` | `_deserializar(entradas: list) -> list` | Copia entradas JSON y reconstruye sus llamadas como `LlamadaHerramienta`. | Una entrada incompatible puede producir `TypeError`; no captura esa validación. |
| `_titulo` | `_titulo(historial: list) -> str` | Calcula el título visible de una sesión. | Toma el primer mensaje de usuario, colapsa espacios y corta a `TITULO_MAX`; sin texto devuelve «Conversación sin título». |
| `guardar` | `guardar(sesion_id: str, historial: list) -> None` | Escribe id, título, fechas e historial serializado en un JSON de sesión. | Ignora historiales vacíos; conserva `creada` si el JSON anterior es legible y toma `_lock` al escribir. |
| `cargar` | `cargar(sesion_id: str)` | Lee una sesión y devuelve su historial neutro reconstruido. | Id inválido, archivo ausente, JSON corrupto o `OSError` producen `None`; lee bajo `_lock`. |
| `listar` | `listar() -> list` | Recorre sesiones JSON, extrae metadatos y ordena de la más reciente a la más antigua. | La carpeta ausente produce `[]`; cada JSON ilegible se omite y el lock cubre el recorrido. |
| `borrar` | `borrar(sesion_id: str) -> None` | Elimina el archivo JSON asociado a una sesión. | Ids inválidos se ignoran y `unlink(missing_ok=True)` hace silenciosa la ausencia del archivo. |
| `para_ui` | `para_ui(historial: list) -> list` | Convierte el historial neutro en la lista de eventos que pinta la interfaz. | Convierte resultados en eventos `render` y llamadas en eventos `herramienta` con el detalle recortado a 400 caracteres; una herramienta desconocida aparece como «?». |

**Constantes de módulo:** `TITULO_MAX`.

## `buildai/memoria.py`

La memoria es best-effort: analiza sesiones guardadas, extrae textos y fragmentos de código reconocibles y devuelve un perfil textual. Su firma usa cantidad de archivos y modificación más reciente; una lectura o extracción fallida no debe impedir el turno.

| Símbolo | Firma o tipo | Qué hace y qué devuelve | Casos borde y estado |
|---|---|---|---|
| `_firma` | `_firma(carpeta)` | Calcula la firma de cache a partir de sesiones. | Devuelve (número de JSON, mtime más reciente) y (0, 0.0) si la carpeta no tiene sesiones. |
| `_codigos_y_textos` | `_codigos_y_textos(historial)` | Extrae código y texto útil del historial. | Recoge el texto de las entradas `usuario` y solo el argumento `codigo` de las llamadas; ignora los demás argumentos. |
| `perfil_texto` | `perfil_texto() -> str` | Destila materiales, categorías, temas y renders de sesiones para inyectarlos en el prompt. | Usa cache por firma de carpeta; omite JSON inválidos y cualquier excepción exterior devuelve `""`. |

**Constantes de módulo:** `_MATERIALES`, `_CATEGORIAS`, `_TEMAS`, `_RE_FUNC`, `_RE_MAT`.

## `buildai/modelos.py`

`listar` aplica `_CACHE_SEGUNDOS` al catálogo general y un TTL de 5 segundos a Ollama. OpenRouter filtra ids terminados en `:free` que declaran `tools`; Ollama consulta `/api/tags`; OpenCode consulta `/v1/models`; los demás proveedores usan `_ESTATICOS`. Los fallos usan respaldos incorporados o, para Ollama, catálogo vacío no disponible.

| Símbolo | Firma o tipo | Qué hace y qué devuelve | Casos borde y estado |
|---|---|---|---|
| `_openrouter_gratuitos` | `_openrouter_gratuitos() -> dict` | Consulta modelos gratuitos de OpenRouter con tools. | Filtra por sufijo `:free` y soporte de `tools` y ordena por contexto; cualquier fallo de red devuelve `_RESPALDO_OPENROUTER` con nota de «sin conexión». |
| `_ollama_locales` | `_ollama_locales() -> dict` | Consulta modelos locales de Ollama. | Timeout de 2 s; si Ollama no responde devuelve `disponible: False` con instrucciones de instalación, y distingue el caso «en marcha pero sin modelos». |
| `_opencode_zen_models` | `_opencode_zen_models() -> dict` | Consulta modelos de OpenCode Zen. | Sin conexión devuelve `_RESPALDO_OPENCODE`; conserva los identificadores tal como los publica la API. |
| `listar` | `listar(proveedor: str) -> dict` | Selecciona el catálogo del proveedor y devuelve disponibilidad, modelos y nota. | Usa TTL de 5 segundos para Ollama y de una hora para los demás; proveedores desconocidos devuelven catálogo vacío. |

**Constantes de módulo:** `_RESPALDO_OPENROUTER`, `_ESTATICOS`, `_RESPALDO_OPENCODE`, `_CACHE_SEGUNDOS`.

## `buildai/skills.py`

`cargar_skills` recorre `CARPETA_SKILLS`, acepta objetos JSON con los campos requeridos y descarta archivos ilegibles o elementos inválidos. La ejecución del agente no concede permisos adicionales: las operaciones siguen limitadas por los conectores.

| Símbolo | Firma o tipo | Qué hace y qué devuelve | Casos borde y estado |
|---|---|---|---|
| `cargar_skills` | `cargar_skills() -> list` | Carga JSON ordenados, aplica `icono` y `descripcion` por defecto y devuelve las skills válidas. | Carpeta ausente, JSON ilegible o campos obligatorios ausentes se omiten sin abortar la carga. |

**Constantes de módulo:** `CARPETA_SKILLS`.

## `buildai/instalador.py`

Los instaladores devuelven diccionarios con `ok` y `mensaje`; `instalar` captura excepciones por programa y `instalar_todos` continúa con el resto. Blender, SketchUp y Revit reciben archivos desde `ADDONS`; AutoCAD no recibe addon y se limita a comprobar COM. `crear_acceso_directo` devuelve `{ok:false}` fuera de Windows.

| Símbolo | Firma o tipo | Qué hace y qué devuelve | Casos borde y estado |
|---|---|---|---|
| `_es_python_de_store` | `_es_python_de_store() -> bool` | Python de Microsoft Store: virtualiza las escrituras a AppData (van a su contenedor privado y los programas reales no las ven). | Se decide por la ruta de `sys.executable` (`windowsapps` o `pythonsoftwarefoundation`); no inspecciona el paquete real. |
| `_cmd` | `_cmd(argumentos: list) -> bool` | Ejecuta un comando auxiliar y devuelve éxito. | Lanza el comando con `cmd /c` capturando la salida y solo informa de si el código de retorno fue 0. |
| `_crear_carpeta` | `_crear_carpeta(carpeta: Path) -> None` | Crea la carpeta y sus padres, usando `cmd mkdir` para Python Store en Windows. | Verifica la creación en esa ruta y lanza `OSError` si `cmd` no la deja disponible. |
| `_copiar_archivo` | `_copiar_archivo(origen: Path, destino: Path) -> None` | Crea el padre y copia un archivo con `copy2` o `cmd copy /y` según el entorno. | Los fallos de copia no se ocultan; en Store se convierten en `OSError` propio. |
| `_copiar_carpeta` | `_copiar_carpeta(origen: Path, destino: Path) -> None` | Copia el árbol del addon con `xcopy` o `copytree(..., dirs_exist_ok=True)`. | No devuelve estado; un error interrumpe el instalador que lo invocó. |
| `_escribir_texto` | `_escribir_texto(destino: Path, texto: str) -> None` | Escribe UTF-8, usando un temporal fuera de AppData y `cmd copy` en Python Store. | Intenta borrar el temporal en `finally`; errores de escritura o copia pueden escapar. |
| `_programas_files` | `_programas_files() -> list` | Obtiene rutas de Program Files. | Lee las variables `ProgramFiles` y `ProgramFiles(x86)` con rutas por defecto y omite las que no sean directorios. |
| `_versiones_blender` | `_versiones_blender() -> set` | Versiones (como '4.2') detectadas por perfil de usuario o instalación. | Reúne versiones del perfil de usuario, de Program Files y de la instalación de Steam; solo acepta carpetas con formato `N.N`. |
| `_instalar_blender` | `_instalar_blender() -> dict` | Detecta versiones y copia el bridge a `scripts/startup`, actualizando un addon clásico si existe. | Ignora Blender anterior a 2.80 y devuelve mensajes diferenciados para ausencia, incompatibilidad o éxito. |
| `_instalar_sketchup` | `_instalar_sketchup() -> dict` | Busca perfiles `SketchUp YYYY` y copia el Ruby en su carpeta `Plugins`. | Si no hay perfiles devuelve `ok: False`; la extensión se autoarranca al reiniciar SketchUp. |
| `_pyrevit_detectado` | `_pyrevit_detectado() -> bool` | Comprueba si pyRevit está disponible. | Busca el comando `pyrevit` en el PATH y carpetas `pyRevit*` en APPDATA, ProgramData y Program Files. |
| `_revit_detectado` | `_revit_detectado() -> bool` | Comprueba si está instalada una extensión Revit. | Solo comprueba carpetas `Autodesk/Revit 20*` en Program Files; no valida que Revit pueda arrancar. |
| `_instalar_revit` | `_instalar_revit() -> dict` | Copia la extensión pyRevit y fuerza `routes.enabled=true` en su INI. | Puede dejar archivos preparados aunque falte pyRevit; devuelve aviso `ok: False` en ese caso. |
| `_instalar_autocad` | `_instalar_autocad() -> dict` | Prueba COM y, si falla, busca una instalación para explicar que AutoCAD no necesita bridge. | Devuelve éxito si conecta o detecta AutoCAD; LT queda explícitamente fuera. |
| `aviso_instalacion_arriesgada` | `aviso_instalacion_arriesgada() -> str \| None` | Devuelve el aviso sobre instalación en AppData con el Python de la Store. | Solo avisa en Windows, con Python de la Store y si el paquete quedó bajo AppData; en cualquier otro caso devuelve `None`. |
| `crear_acceso_directo` | `crear_acceso_directo() -> dict` | Crea `BuildAI.lnk` mediante PowerShell apuntando al BAT del checkout o a `python -m buildai.main`. | Fuera de Windows devuelve un diccionario `ok: False`; en Windows convierte el fallo de PowerShell en resultado de error. |
| `instalar` | `instalar(programa_id: str) -> dict` | Selecciona el instalador por id y devuelve su diccionario de resultado. | Id desconocido y excepciones internas se convierten en `ok: False` con mensaje. |
| `instalar_todos` | `instalar_todos() -> None` | Ejecuta todos los instaladores, imprime sus resultados y crea el acceso directo. | No devuelve valor; captura el fallo del acceso directo para continuar el resumen. |

**Constantes de módulo:** `ADDONS`, `APPDATA`, `_CARPETA_SEGURA`, `_INSTALADORES`.

## `buildai/main.py`

Las funciones de ruta son los handlers de FastAPI y devuelven `FileResponse`, diccionarios o `StreamingResponse` según el caso. `chat` define `flujo` y `trabajo` dentro del propio handler: el primero consume la cola y el segundo ejecuta el turno, guarda la sesión en `finally` y libera el lock. `ver_render` valida extensión, separadores, nombre oculto y existencia antes de servir el archivo.

| Símbolo | Firma o tipo | Qué hace y qué devuelve | Casos borde y estado |
|---|---|---|---|
| `portada` | `portada()` | Sirve index.html. | Sirve el archivo del paquete sin comprobar que exista; no depende del estado de la conversación. |
| `manual` | `manual()` | Sirve manual.html. | Ruta estática equivalente a `portada`; no consulta configuración ni conectores. |
| `ver_render` | `ver_render(nombre: str)` | Sirve un render generado por Blender. | Responde 404 ante nombres con separadores, nombres ocultos, extensión distinta de `.png` o archivo inexistente. |
| `_disponible_seguro` | `_disponible_seguro(conector) -> bool` | Consulta un conector aislando la comprobación del resto del endpoint. | Cualquier excepción del conector se convierte en `False`. |
| `estado` | `estado()` | Devuelve conectores, proveedor, modelo y configuración. | Consulta los cuatro conectores en paralelo con `ThreadPoolExecutor` para no sumar timeouts, y `_disponible_seguro` convierte cualquier excepción en `False`. |
| `leer_config` | `leer_config()` | Devuelve configuración sin secretos. | Devuelve `claves_configuradas` como booleanos; nunca expone el valor de las claves. |
| `guardar_config` | `guardar_config(peticion: Request)` | Actualiza y persiste proveedor, claves y modelos. | Ignora proveedores desconocidos y valores vacíos (vacío = no cambiar) y recorta espacios antes de persistir. |
| `oauth_login` | `oauth_login(proveedor: str)` | Redirige al OAuth disponible. | Devuelve un objeto `error` en lugar de redirigir si el proveedor no declara `oauth_disponible`. |
| `oauth_callback` | `oauth_callback()` | Sirve la página que recoge el token del fragmento. | El token viaja en el fragmento de la URL, que no llega al servidor: lo reenvía la propia página a `/api/oauth/save`. |
| `oauth_save` | `oauth_save(peticion: Request)` | Guarda el token OAuth. | Un token vacío devuelve `ok: False`; el token se guarda en el primer proveedor con OAuth disponible. |
| `conectar` | `conectar(programa_id: str)` | Instala un puente y comprueba disponibilidad. | Añade `conectado` llamando a `disponible()` sin protección, así que un fallo del canal sí puede propagarse. |
| `modelos_de` | `modelos_de(proveedor: str)` | Devuelve el catálogo de un proveedor. | Delega en `modelos.listar` con su cache; un proveedor desconocido devuelve catálogo vacío en vez de error HTTP. |
| `skills` | `skills()` | Devuelve las skills cargadas. | Relee la carpeta en cada petición; las skills inválidas quedan fuera sin aviso. |
| `reiniciar` | `reiniciar()` | Cambia a una conversación nueva si está libre. | Con `_ocupado` tomado devuelve `ok: False` y no vacía el historial, para no romper el emparejado herramienta/resultado. |
| `listar_sesiones` | `listar_sesiones()` | Lista sesiones y la actual. | Incluye el id de la conversación activa aunque todavía no se haya escrito en disco. |
| `abrir_sesion` | `abrir_sesion(sesion_id: str)` | Abre una sesión validada. | Rechaza el cambio si el agente trabaja y devuelve `ok: False` si la sesión ya no existe; al abrirla sustituye el historial en memoria. |
| `borrar_sesion` | `borrar_sesion(sesion_id: str)` | Borra una sesión no activa. | Solo se niega si la sesión es la activa y hay trabajo en curso; al borrar la activa abre una conversación nueva. |
| `cancelar` | `cancelar()` | Solicita cancelación del trabajo. | Marca el evento `_cancelar` únicamente si hay trabajo en curso y siempre responde `ok: True`. |
| `_sanear_adjuntos` | `_sanear_adjuntos(bruto) -> list` | Filtra imágenes base64, normaliza el tipo y aplica los límites de cantidad y tamaño. | Descarta entradas inválidas sin consumir cupo; acepta como máximo 12 y 8 MiB por cadena de datos. |
| `chat` | `chat(peticion: Request)` | Crea el stream SSE y un hilo que ejecuta y guarda el turno tras adquirir `_ocupado`. | Mensaje vacío o lock ocupado generan un evento `error`; el hilo libera el lock en `finally`. |
| `_sse` | `_sse(evento: dict) -> str` | Codifica un evento como SSE. | Serializa con `ensure_ascii=False` y cierra con una línea en blanco, el formato que espera el cliente. |
| `_esperar_servidor` | `_esperar_servidor(timeout: float=15.0) -> bool` | Sondea `127.0.0.1:8600` hasta recibir respuesta o agotar el timeout. | Captura cualquier error de conexión y devuelve booleano; espera en intervalos de 0.2 segundos. |
| `arrancar` | `arrancar()` | Inicia uvicorn en un hilo, espera a que responda y abre la ventana nativa. | Sin `pywebview` cae al navegador y se queda esperando al hilo del servidor; antes imprime el aviso de instalación arriesgada si aplica. |
| `flujo` | `flujo()` | Generador que emite los eventos del turno como SSE hasta el centinela de fin. | Sondea la cola cada 0,1 s con `queue.Empty`; si el lock está tomado emite un único evento `error` y termina. |
| `trabajo` | `trabajo()` | Ejecuta el turno en un hilo aparte y persiste la sesión al terminar. | Guarda la sesión en el `finally` ignorando fallos de disco, encola el centinela de fin y libera `_ocupado`. |

**Constantes de módulo:** `PUERTO`, `CARPETA_UI`, `_OAUTH_CLIENT_ID`, `_MAX_ADJUNTOS`, `_MAX_BYTES_ADJUNTO`.

## `buildai/connectors/base.py`

`Conector` es el contrato mínimo para detectar un programa, describir herramientas y ejecutar una llamada. `recortar` limita la salida textual a `MAX_SALIDA`; los conectores concretos convierten excepciones de disponibilidad en `False` y devuelven errores textuales para no tumbar el turno.

| Símbolo | Firma o tipo | Qué hace y qué devuelve | Casos borde y estado |
|---|---|---|---|
| `Conector` | clase | Base de la que heredan los cuatro conectores; define `id`, `nombre`, `icono`, `ayuda` (texto de conexión mostrado al usuario) y los tres métodos abstractos que cada subclase implementa. | Los métodos abstractos lanzan `NotImplementedError`; no se instancia directamente. |
| `recortar` | `recortar(texto: str, limite: int=MAX_SALIDA) -> str` | Convierte a texto y aplica el límite solicitado, añadiendo el tamaño original si recorta. | El límite por defecto es `MAX_SALIDA`; no captura errores de conversión. |
| `disponible` | `disponible(self) -> bool` | Comprueba si el programa está abierto y responde ahora mismo. | La implementación base lanza `NotImplementedError`. |
| `herramientas` | `herramientas(self) -> list` | Devuelve los esquemas de herramientas que el conector ofrece al modelo. | La implementación base lanza `NotImplementedError`. |
| `ejecutar` | `ejecutar(self, nombre: str, argumentos: dict) -> str` | Ejecuta una herramienta por nombre y devuelve su salida como texto. | La implementación base lanza `NotImplementedError`; las subclases recortan la salida con `recortar`. |

**Constantes de módulo:** `MAX_SALIDA`.

## `buildai/connectors/__init__.py`

`CONECTORES` es el registro de instancias. `conectores_disponibles` prueba cada instancia y `buscar_herramienta` solo resuelve una herramienta perteneciente a un conector disponible.

| Símbolo | Firma o tipo | Qué hace y qué devuelve | Casos borde y estado |
|---|---|---|---|
| `conectores_disponibles` | `conectores_disponibles()` | Conectores cuyo programa está abierto y responde ahora mismo. | Consulta `disponible()` en serie, por lo que suma los timeouts de los programas cerrados; `estado()` usa su propia comprobación en paralelo. |
| `buscar_herramienta` | `buscar_herramienta(nombre: str)` | Busca el primer esquema cuyo campo `nombre` coincide y devuelve `(conector, herramienta)`. | Devuelve `None` si no encuentra coincidencia y no comprueba disponibilidad. |

**Constantes de módulo:** `CONECTORES`.

## `buildai/connectors/autocad.py`

El conector inicializa COM y obtiene el documento activo. `autocad_informacion` requiere al menos un dibujo; `autocad_ejecutar_python` expone `acad`, `doc`, `ms`, `punto` y `puntos`; `autocad_comando` envía el campo `orden`. AutoCAD LT no ofrece el canal COM requerido.

| Símbolo | Firma o tipo | Qué hace y qué devuelve | Casos borde y estado |
|---|---|---|---|
| `ConectorAutoCAD` | clase, hereda de `Conector` | `id="autocad"`, `nombre="AutoCAD"`; `ayuda` explica que no requiere addon, solo COM de Windows. | No expone estado propio entre llamadas; cada `ejecutar` obtiene el documento activo de nuevo. |
| `_obtener_acad` | `_obtener_acad()` | Prueba ProgID genérico y versionados de AutoCAD hasta obtener una instancia COM. | La ausencia de AutoCAD o de COM se propaga al llamador; `disponible` la convierte en `False`. |
| `disponible` | `disponible(self) -> bool` | Comprueba que AutoCAD responde mediante COM. | Captura cualquier excepción y devuelve `False`. |
| `herramientas` | `herramientas(self) -> list` | Declara las herramientas de AutoCAD. | Lista declarativa de tres herramientas; sus descripciones llevan el manual de COM que lee el modelo. |
| `ejecutar` | `ejecutar(self, nombre: str, argumentos: dict) -> str` | Ejecuta información, Python con `acad/doc/ms/punto/puntos` u orden COM y recorta la salida. | Sin documento devuelve error; errores de COM o `exec` se devuelven como texto `ERROR`. |
| `punto` | `punto(x, y, z=0.0)` | Crea un punto COM. | Definida en el preámbulo inyectado antes de cada ejecución; envuelve las coordenadas en el VARIANT que exige COM. |
| `puntos` | `puntos(lista)` | Lista plana de coordenadas 2D, formato de AddLightWeightPolyline. | Aplana pares (x, y) en la lista plana que exige `AddLightWeightPolyline`; descarta la coordenada Z. |

**Constantes de módulo:** `_PROG_IDS`.

## `buildai/connectors/blender.py`

El transporte usa una línea JSON por socket TCP. `disponible` envía `ping`; `ejecutar` antepone `KIT_FUENTE`, compila el código con nombre `<codigo>` y usa 600 segundos de timeout local, enviando 570 al puente para permitir renders largos.

| Símbolo | Firma o tipo | Qué hace y qué devuelve | Casos borde y estado |
|---|---|---|---|
| `ConectorBlender` | clase, hereda de `Conector` | `id="blender"`, `nombre="Blender"`; `ayuda` describe la conexión automática del puente para todas las versiones instaladas (2.80+). | No mantiene socket abierto entre llamadas; cada `_enviar` abre y cierra su propia conexión TCP. |
| `_enviar` | `_enviar(peticion: dict, timeout: float=60.0) -> dict` | Envía una línea JSON por socket TCP local y devuelve la respuesta JSON. | Errores de socket, timeout, protocolo o decodificación escapan a `disponible`/`ejecutar`. |
| `disponible` | `disponible(self) -> bool` | Envía `ping` al bridge de Blender y devuelve su campo `ok`. | Captura `OSError` y `ValueError`, por lo que un bridge cerrado produce `False`. |
| `herramientas` | `herramientas(self) -> list` | Declara las herramientas de Blender. | Lista declarativa de dos herramientas; la descripción incorpora el kit paramétrico disponible para el modelo. |
| `ejecutar` | `ejecutar(self, nombre: str, argumentos: dict) -> str` | Anteponer `KIT_FUENTE` al código del usuario y lo envía al bridge con timeout amplio. | Usa 600 segundos localmente y 570 en la petición; errores de transporte se convierten en texto. |

**Constantes de módulo:** `PUERTO_BLENDER`, `KIT_FUENTE`, `REFERENCIA_KIT`.

## `buildai/connectors/sketchup.py`

El conector llama al bridge HTTP local y delega la ejecución Ruby. El bridge encola cada petición y la procesa en el hilo principal de SketchUp; el sondeo HTTP tiene un límite de 120 segundos.

| Símbolo | Firma o tipo | Qué hace y qué devuelve | Casos borde y estado |
|---|---|---|---|
| `ConectorSketchUp` | clase, hereda de `Conector` | `id="sketchup"`, `nombre="SketchUp"`; `ayuda` describe la extensión instalada automáticamente para todas las versiones (2014+). | No mantiene estado propio; cada llamada es una petición HTTP independiente al bridge. |
| `disponible` | `disponible(self) -> bool` | Consulta `GET /ping` en el bridge HTTP de SketchUp. | Errores de conexión o respuesta producen `False`. |
| `herramientas` | `herramientas(self) -> list` | Declara las herramientas de SketchUp. | Lista declarativa de dos herramientas; la descripción resume el API Ruby que puede usar el modelo. |
| `ejecutar` | `ejecutar(self, nombre: str, argumentos: dict) -> str` | Solicita `/info` o `/ejecutar`, comprueba `ok` y recorta el resultado textual. | Usa 30 segundos para información y 120 para Ruby; errores HTTP o JSON se devuelven como texto. |

**Constantes de módulo:** `PUERTO_SKETCHUP`, `BASE`.

## `buildai/connectors/revit.py`

El bridge de Routes expone `/ping`, `/info` y `/ejecutar` bajo `/buildai`. El conector antepone `KIT_FUENTE`, retira la cabecera de codificación incompatible con IronPython 2 y recorta la respuesta textual.

| Símbolo | Firma o tipo | Qué hace y qué devuelve | Casos borde y estado |
|---|---|---|---|
| `ConectorRevit` | clase, hereda de `Conector` | `id="revit"`, `nombre="Revit"`; `ayuda` indica que requiere pyRevit (gratuito, 2014+) instalado por el usuario. | No mantiene estado propio; depende de que el bridge de Routes esté cargado en Revit. |
| `disponible` | `disponible(self) -> bool` | Consulta `/ping` en Routes bajo `/buildai`. | Los errores HTTP o de conexión producen `False`. |
| `herramientas` | `herramientas(self) -> list` | Declara las herramientas de Revit. | Lista declarativa de dos herramientas; la descripción advierte de que la unidad interna de Revit son los pies. |
| `ejecutar` | `ejecutar(self, nombre: str, argumentos: dict) -> str` | Anteponer el kit Revit al código y enviar información o ejecución a Routes. | Usa 60 segundos para información y 180 para ejecución; respuestas no JSON se convierten en error textual. |

**Constantes de módulo:** `PUERTO_REVIT`, `BASE`, `KIT_FUENTE`.

## `buildai/providers/base.py`

`LlamadaHerramienta` y `RespuestaLLM` forman el formato neutro; `ErrorProveedor` normaliza fallos mostrables. `Proveedor.conversar` es una interfaz abstracta documentada para que cada adaptador traduzca el historial sin contaminar las sesiones.

| Símbolo | Firma o tipo | Qué hace y qué devuelve | Casos borde y estado |
|---|---|---|---|
| `ErrorProveedor` | clase, hereda de `Exception` | Excepción usada por los adaptadores para envolver fallos de red, autenticación o cuota con un mensaje apto para mostrar al usuario. | Sin atributos propios; el mensaje va en el `str()` de la excepción. |
| `LlamadaHerramienta` | dataclass | Petición de herramienta normalizada: `id`, `nombre` y `argumentos` ya deserializados. | El `id` es el que exige el proveedor para emparejar el resultado; los adaptadores rellenan `argumentos` con un dict vacío si el JSON no es válido. |
| `RespuestaLLM` | dataclass | Respuesta unificada del modelo: `texto`, `llamadas` y el `raw` del proveedor. | `llamadas` vacía significa turno final; `raw` solo lo usa Anthropic para reenviar sus bloques originales. |
| `Proveedor` | clase | Contrato abstracto que implementan `ProveedorAnthropic` y `ProveedorOpenAICompatible`; expone `notificar`, un callback opcional que el agente asigna para mostrar esperas y reintentos. | `notificar` es `None` por defecto; `conversar` lanza `NotImplementedError` si no se sobreescribe. |
| `conversar` | `conversar(self, sistema: str, historial: list, herramientas: list) -> RespuestaLLM` | `herramientas` es una lista de dicts {nombre, descripcion, parametros(JSON Schema)}. | La implementación base lanza `NotImplementedError`. |

## `buildai/providers/__init__.py`

| Símbolo | Firma o tipo | Qué hace y qué devuelve | Casos borde y estado |
|---|---|---|---|
| `crear_proveedor` | `crear_proveedor(config: dict)` | Elige adaptador, valida la clave requerida y configura URL, modelo y timeout. | La clave ausente produce `ErrorProveedor`; un nombre no contemplado falla al resolver la URL. |

## `buildai/providers/anthropic_provider.py`

Anthropic recibe imágenes como bloques base64 y conserva los bloques originales en `raw` para reenviar `thinking` y `tool_use`. `conversar` usa `max_tokens` 16000 y thinking adaptativo; autenticación, rate limit, rechazo, estado HTTP y conexión se convierten a `ErrorProveedor`.

| Símbolo | Firma o tipo | Qué hace y qué devuelve | Casos borde y estado |
|---|---|---|---|
| `ProveedorAnthropic` | clase, hereda de `Proveedor` | Guarda `clave` y `modelo` (por defecto `claude-opus-4-8` si no se especifica). | Sin caché ni reintentos propios; cada `conversar` es una llamada directa al SDK de Anthropic. |
| `__init__` | `__init__(self, clave: str, modelo: str)` | Guarda clave y modelo. | Aplica `claude-opus-4-8` cuando el modelo llega vacío; no valida la clave. |
| `_convertir_historial` | `_convertir_historial(self, historial: list) -> list` | Traduce el historial al formato Anthropic. | Coloca las imágenes antes del texto y reenvía `_raw` cuando existe, para conservar los bloques `thinking` y `tool_use`. |
| `conversar` | `conversar(self, sistema: str, historial: list, herramientas: list) -> RespuestaLLM` | Envía Messages con thinking adaptativo y transforma texto y tool use a `RespuestaLLM`. | Convierte autenticación, rate limit, estados HTTP, conexión y refusal en `ErrorProveedor`; conserva bloques `raw`. |

## `buildai/providers/openai_compat.py`

El adaptador envía `/chat/completions`. Convierte usuario, asistente y resultado a `messages`, serializa llamadas como `tool_calls` y reconstruye sus argumentos JSON. Reintenta `429`, `408`, 5xx y errores de red hasta `_MAX_REINTENTOS`; usa espera inicial `_ESPERA_INICIAL`, tope `_ESPERA_MAXIMA` y `Retry-After` cuando es válido.

| Símbolo | Firma o tipo | Qué hace y qué devuelve | Casos borde y estado |
|---|---|---|---|
| `ProveedorOpenAICompatible` | clase, hereda de `Proveedor` | Guarda `base_url`, `clave`, `modelo`, `nombre` y `timeout` (180s por defecto); usado para OpenAI, OpenRouter y cualquier API compatible con Chat Completions. | `_respetar_ritmo` añade una pausa fija solo cuando `nombre` corresponde al plan gratuito de OpenRouter. |
| `__init__` | `__init__(self, base_url: str, clave: str, modelo: str, nombre: str, timeout: float=180.0)` | Configura endpoint, credenciales, modelo y timeout. | Normaliza `base_url` quitando la barra final; el timeout por defecto son 180 s. |
| `_cabeceras` | `_cabeceras(self) -> dict` | Construye cabeceras HTTP. | Añade `HTTP-Referer` y `X-Title` solo cuando `nombre` es `openrouter`. |
| `_convertir_historial` | `_convertir_historial(self, sistema: str, historial: list) -> list` | Traduce historial a Chat Completions. | Inserta el prompt de sistema como primer mensaje y envía las imágenes como `image_url` con data URI. |
| `_avisar` | `_avisar(self, texto: str) -> None` | Llama al callback `notificar` para comunicar esperas y reintentos. | Captura cualquier excepción del callback para no abortar la conversación. |
| `_respetar_ritmo` | `_respetar_ritmo(self) -> None` | Espacia globalmente las peticiones de modelos OpenRouter terminados en `:free`. | Solo duerme si queda intervalo; actualiza siempre la marca de última petición. |
| `_espera_reintento` | `_espera_reintento(respuesta, espera: float) -> float` | Lee `Retry-After` y lo limita a `_ESPERA_MAXIMA` para calcular la espera. | Cabecera ausente, vacía o inválida conserva la espera recibida. |
| `_mensaje_agotado` | `_mensaje_agotado(self, codigo: int) -> str` | Construye el mensaje final después de agotar los reintentos. | Distingue 429 de otros códigos y añade el cupo diario específico de OpenRouter free. |
| `conversar` | `conversar(self, sistema: str, historial: list, herramientas: list) -> RespuestaLLM` | Envía Chat Completions, reintenta fallos transitorios y reconstruye llamadas de herramienta. | Reintenta 429, 408, 5xx y red; argumentos JSON inválidos se convierten en `{}` y errores permanentes salen como `ErrorProveedor`. |

**Constantes de módulo:** `_MAX_REINTENTOS`, `_ESPERA_INICIAL`, `_ESPERA_MAXIMA`, `_INTERVALO_FREE`.

## `buildai/connectors/blender_kit.py`

Funciones públicas agrupadas por familia. Estas son las que el prompt del conector ofrece al modelo; las privadas se enumeran después.

| Familia | Función y firma exacta | Qué hace (docstring del kit) |
|---|---|---|
| Terreno y estructura | `caja(nombre, origen, dimensiones, material='gris_claro', capa=None)` | Caja simple. `origen` es la esquina mínima (x, y, z); `dimensiones` (dx, dy, dz). |
| Terreno y estructura | `limpiar_todo()` | Borra TODOS los objetos de la escena. Úsalo solo con permiso del usuario. |
| Terreno y estructura | `muro(inicio, fin, alto=2.7, espesor=0.2, nivel=0.0, huecos=None, material='blanco', capa=None, nombre=None)` | Muro recto de (x, y) inicio a fin, con huecos y carpinterías automáticas. Cada hueco es un dict: {"tipo": "ventana"\|"puerta"\|"ventanal"\|"paso", "a": |
| Terreno y estructura | `ventanal(inicio, fin, alto=2.5, nivel=0.0, division=1.2, capa=None)` | Muro cortina acristalado de suelo a techo, con montantes cada `division` m. Ideal para fachadas de casas modernas y plantas bajas de edificios. |
| Terreno y estructura | `forjado(contorno, nivel=0.0, espesor=0.3, material='hormigon', capa=None, nombre=None)` | Losa horizontal con planta poligonal. `contorno` es una lista de (x, y); la cara superior queda en `nivel` (la cota del suelo terminado). |
| Terreno y estructura | `escalera(origen, direccion='+x', ancho=1.0, alto_total=2.7, nivel=0.0, huella=0.28, material='hormigon', capa=None)` | Tramo recto de escalera maciza desde `origen` (x, y) subiendo `alto_total` m. `direccion`: "+x", "-x", "+y" o "-y". |
| Terreno y estructura | `barandilla(inicio, fin, nivel=0.0, alto=1.0, capa=None)` | Barandilla moderna (postes + pasamanos + panel de vidrio) entre dos puntos (x, y). |
| Terreno y estructura | `rejilla_pilares(origen, num_x, num_y, sep_x, sep_y, alto, nivel=0.0, lado=0.3, material='hormigon', capa=None)` | Retícula estructural de pilares (num_x × num_y) desde la esquina `origen`, separados sep_x / sep_y metros. La base de todos queda en `nivel`. |
| Terreno y estructura | `terreno(ancho=60, fondo=60, centro=(0, 0), material='cesped', capa=None, ondulacion=0.0)` | Plano de suelo centrado en `centro`, con la cara superior en cota 0. |
| Cubiertas | `cubierta_plana(contorno, nivel, espesor=0.3, peto=0.6, material='hormigon', capa=None)` | Cubierta plana moderna: losa + peto perimetral. `nivel` es la cara superior de la losa (cota del suelo de la azotea). |
| Cubiertas | `cubierta_dos_aguas(origen, ancho, fondo, nivel, pendiente=30, alero=0.5, eje='x', material='teja', capa=None)` | Cubierta a dos aguas sobre un rectángulo. |
| Mobiliario y estancias | `cama(origen, ancho=1.5, largo=2.0, rotacion=0, nivel=0.0, capa=None, ropa='tela_azul', madera='madera_clara')` | Cama con cabecero, colchón, almohadas y colcha. `ancho` 0.9 individual, 1.35/1.5/1.8 doble. El cabecero queda contra la línea del origen. |
| Mobiliario y estancias | `mesita_noche(origen, ancho=0.45, rotacion=0, nivel=0.0, capa=None, material='madera_clara')` | Mesita de noche con cajón. |
| Mobiliario y estancias | `mesa(origen, ancho=1.6, fondo=0.9, alto=0.75, rotacion=0, nivel=0.0, capa=None, material='madera')` | Mesa de patas en las esquinas (comedor, escritorio o, con alto=0.4, de centro). |
| Mobiliario y estancias | `silla(origen, rotacion=0, nivel=0.0, capa=None, material='madera', tapizado='tela_gris')` | Silla de 45 cm de asiento; el respaldo queda contra la línea del origen. |
| Mobiliario y estancias | `sofa(origen, plazas=3, rotacion=0, nivel=0.0, capa=None, tela='tela_gris')` | Sofá de `plazas` asientos con brazos y cojines; espalda en la línea del origen. |
| Mobiliario y estancias | `sillon(origen, rotacion=0, nivel=0.0, capa=None, tela='tela_beige')` | Sillón de una plaza. |
| Mobiliario y estancias | `comedor(origen, comensales=6, rotacion=0, nivel=0.0, capa=None, material='madera')` | Mesa de comedor con las sillas ya colocadas para `comensales` personas. |
| Mobiliario y estancias | `armario(origen, ancho=2.0, alto=2.2, fondo=0.6, rotacion=0, nivel=0.0, capa=None, material='madera_clara')` | Armario de puertas batientes; espalda en la línea del origen. |
| Mobiliario y estancias | `estanteria(origen, ancho=0.9, alto=1.8, fondo=0.35, baldas=4, rotacion=0, nivel=0.0, capa=None, material='madera')` | Estantería abierta con `baldas` alturas. |
| Mobiliario y estancias | `cocina(origen, largo=3.0, rotacion=0, nivel=0.0, capa=None, con_altos=True, mueble='madera_clara', encimera='marmol')` | Bancada de cocina completa: muebles bajos, encimera con placa y fregadero y, opcionalmente, muebles altos. La espalda va contra la pared (línea del origen). |
| Mobiliario y estancias | `lavabo(origen, ancho=0.8, rotacion=0, nivel=0.0, capa=None)` | Mueble de lavabo con seno, grifo y espejo (espalda contra la pared). |
| Mobiliario y estancias | `inodoro(origen, rotacion=0, nivel=0.0, capa=None)` | Inodoro con cisterna (espalda contra la pared; ocupa unos 0,5 × 0,7 m). |
| Mobiliario y estancias | `ducha(origen, ancho=0.9, fondo=0.9, rotacion=0, nivel=0.0, capa=None)` | Ducha de obra: plato, mamparas de vidrio y columna (para un rincón: las dos caras sin mampara van contra las paredes). |
| Mobiliario y estancias | `banera(origen, largo=1.7, ancho=0.75, rotacion=0, nivel=0.0, capa=None)` | Bañera exenta contra la pared (línea del origen). |
| Mobiliario y estancias | `alfombra(origen, ancho=2.5, fondo=1.8, rotacion=0, nivel=0.0, capa=None, material='tela_beige')` | Alfombra rectangular. |
| Mobiliario y estancias | `cuadro(posicion, ancho=0.8, alto=0.6, altura_centro=1.5, rotacion=0, nivel=0.0, capa=None, color=(0.35, 0.42, 0.5))` | Cuadro colgado en una pared: `posicion` (x, y) es su esquina izquierda contra la pared y `rotacion` la orientación de esa pared. |
| Mobiliario y estancias | `espejo_pared(posicion, ancho=0.6, alto=1.0, altura_centro=1.5, rotacion=0, nivel=0.0, capa=None)` | Espejo colgado en una pared (misma colocación que `cuadro`). |
| Mobiliario y estancias | `television(posicion, pulgadas=55, altura=1.0, rotacion=0, nivel=0.0, capa=None)` | Televisor plano contra una pared o sobre un mueble; `posicion` es la esquina izquierda de su parte trasera. |
| Mobiliario y estancias | `planta_decorativa(centro, alto=1.3, nivel=0.0, capa=None)` | Planta de interior en maceta; `centro` es el (x, y) de la maceta. |
| Mobiliario y estancias | `dormitorio(origen, ancho, fondo, pared_cama='S', nivel=0.0, capa=None, ropa='tela_azul', madera='madera_clara', altura_techo=2.7)` | Dormitorio completo: cama centrada en `pared_cama` (elige una pared SIN puerta ni ventana), mesitas si caben, armario, alfombra, cuadro y lámpara. Mínimo razonable: |
| Mobiliario y estancias | `salon(origen, ancho, fondo, pared_sofa='S', nivel=0.0, capa=None, tela='tela_gris', altura_techo=2.7)` | Salón completo: |
| Mobiliario y estancias | `bano(origen, ancho, fondo, pared_aparatos='S', nivel=0.0, capa=None, con_ducha=True, altura_techo=2.7)` | Baño completo: ducha en la esquina inicial de `pared_aparatos`, inodoro y lavabo con espejo en línea, y foco de techo. Mínimo razonable: 1,6 × 1,5 m. |
| Exterior | `piscina(origen, ancho=8.0, fondo=4.0, profundidad=1.5, borde=0.6, nivel=0.0, rotacion=0, luces=2, capa=None, material_borde='pavimento')` | Piscina enterrada con vaso alicatado, agua realista, coronación de borde y luces sumergidas. |
| Exterior | `arbol(centro, alto=6.0, tipo='frondoso', nivel=0.0, capa=None, semilla=None)` | Árbol de jardín en (x, y): "frondoso" (copa irregular) o "cipres" (columnar, para alinear junto a muros). |
| Exterior | `arbusto(centro, alto=0.7, nivel=0.0, capa=None, semilla=None)` | Arbusto redondeado en (x, y); en grupos de 2-3 junto a fachadas y muros (ponles un foco_jardin delante para el efecto de la foto nocturna). |
| Exterior | `seto(inicio, fin, alto=1.2, espesor=0.5, nivel=0.0, capa=None)` | Seto vegetal recto entre dos puntos (x, y): cierra parcelas con verde. |
| Exterior | `tumbona(origen, rotacion=0, nivel=0.0, capa=None, tela='tela_beige')` | Tumbona de piscina (0,7 × 1,95 m); el respaldo queda hacia el origen. |
| Exterior | `barbacoa(centro, nivel=0.0, capa=None)` | Barbacoa de carbón tipo kettle en (x, y), para terrazas y jardines. |
| Exterior | `celosia(inicio, fin, alto=2.5, nivel=0.0, orientacion='vertical', separacion=0.12, espesor=0.04, capa=None, material='madera')` | Celosía / lamas de parasol entre dos puntos (x, y): |
| Exterior | `pergola(origen, ancho=4.0, fondo=3.0, altura=2.4, rotacion=0, nivel=0.0, capa=None, material='madera', lamas=True)` | Pérgola de vigas sobre 4 pilares: sombra de terrazas, porches y accesos. `origen` es la esquina (x, y); ocupa `ancho`×`fondo` y `altura` de alto. |
| Exterior | `valla(inicio, fin, alto=1.6, nivel=0.0, tipo='tablas', capa=None, material='madera')` | Valla/cerca recta entre dos puntos (x, y) para cerrar una parcela. tipo: "tablas" (listones verticales juntos, opaca) o "postes" (postes con dos travesaños, ligera). |
| Exterior | `camino(inicio, fin, ancho=1.2, nivel=0.0, material='pavimento', capa=None)` | Camino/sendero recto entre dos puntos (x, y): accesos y senderos de jardín. Se apoya sobre el terreno (cota 0). |
| Exterior | `palmera(centro, alto=7.0, nivel=0.0, capa=None)` | Palmera en (x, y): tronco esbelto y corona de hojas. Da carácter mediterráneo/tropical a jardines y piscinas. |
| Exterior | `farola(posicion, alto=4.0, nivel=0.0, fuerza=120, capa=None)` | Farola de exterior en (x, y): poste con luminaria y luz cálida. Para accesos, caminos y calles; se enciende de noche/atardecer. |
| Exterior | `coche(origen, rotacion=0, nivel=0.0, color=(0.15, 0.16, 0.18), capa=None)` | Coche sencillo aparcado, para dar escala y realismo al exterior. `origen` es la esquina trasera izquierda; mide ~4,4 × 1,8 m. |
| Materiales | `material(nombre, color=None, rugosidad=None, metalico=None, transparente=None, textura=None, escala=None, emision=None)` | Crea (o reutiliza) un material. Presets con acabado listo: |
| Iluminación | `sol(elevacion=35, azimut=200, fuerza=3.0)` | Luz de sol con cielo básico. `elevacion` en grados sobre el horizonte, `azimut` giro en planta (200 ≈ luz cálida de tarde desde el suroeste). |
| Iluminación | `luz_interior(posicion, fuerza=40, calida=True)` | Luz puntual genérica en (x, y, z) — vatios aproximados en `fuerza`. |
| Iluminación | `lampara_colgante(posicion, altura_techo=2.7, descuelgue=0.9, nivel=0.0, fuerza=70, capa=None)` | Lámpara colgada del techo en (x, y); `altura_techo` es la altura libre de la estancia y `nivel` la cota de su suelo. |
| Iluminación | `lampara_pie(centro, nivel=0.0, fuerza=50, capa=None)` | Lámpara de pie (junto a un sofá o sillón); `centro` es su (x, y). |
| Iluminación | `foco_empotrado(posicion, altura_techo=2.7, nivel=0.0, fuerza=75, capa=None)` | Downlight empotrado en el techo en (x, y): aro + punto de luz cálida. `altura_techo` es la altura libre de la estancia y `nivel` la cota de su suelo. |
| Iluminación | `foco_jardin(posicion, nivel=0.0, fuerza=40, capa=None)` | Baliza de jardín que baña de luz cálida hacia ARRIBA lo que tenga encima o al lado (arbustos, árboles, fachadas). Clave en renders de atardecer/noche. |
| Iluminación | `cielo(momento='dia', azimut=200, intensidad=None)` | Cielo físico realista + sol sincronizado, según el momento del día: "amanecer", "dia", "tarde", "atardecer" (hora dorada/azul, la más fotogénica: |
| Cámara y render | `camara(objetivo=(0, 0, 2), distancia=20, azimut=225, altura=6, lente=50, apertura=None)` | Cámara mirando al punto `objetivo` desde `distancia` m, girada `azimut` grados en planta y a `altura` m del suelo. |
| Cámara y render | `revisar_escena()` | Control de calidad: revisa la escena y avisa de los fallos típicos de un render (sin cámara, sin luz cuando hay mobiliario, objetos sin material). |
| Cámara y render | `render(ruta=None, calidad='media', ancho=None, alto=None)` | Render fotorrealista con Cycles: activa GPU si la hay, denoise, tono AgX y halos de luz, y guarda un PNG que el usuario VE directamente en el chat. `calidad`: |
| Utilidades públicas | `coleccion(nombre)` | Devuelve la colección con ese nombre, creándola y enlazándola si no existe. |
| Utilidades públicas | `convertir(u, v)` | Cierre que pasa coordenadas locales (u, v) al sistema global rotado, devuelto por el generador de ejes. |
| Utilidades públicas | `_mundo(u, v)` | Traslada y rota (u, v) al origen y ángulo de la agrupación que se está colocando. |
| Utilidades públicas | `jit(v, frac)` | Aplica una variación aleatoria de ±`frac` a un valor para que la vegetación no salga clonada. |

**Funciones privadas o auxiliares:** `_entrada`, `_conectar_relieve`, `_nodos_textura`, `_mat`, `_nuevo_objeto`, `_agregar_caja`, `_agregar_cilindro`, `_agregar_esfera`, `_malla_piezas`, `_malla_cajas`, `_colocar`, `_sin_sombra`, `_local_a_mundo`, `_carpinteria`, `_contorno_ccw`, `_malla_grid_ondulada`, `_quitar_objetos`, `_crear_sol`, `_suavizar`, `_pieza`, `_situar`, `_luz_puntual`, `_luz_foco`, `_sobre_pared`, `_mat_vegetacion`, `_mat_corteza`, `_fijar`, `_activar_gpu`, `_activar_resplandor`, `_vidrios_opacos_cycles`, `_auto_camara`.
**Constantes:** `_PRESETS`, `_RELIEVE`, `_CARAS_CAJA`, `_OPUESTA`, `_VEG_VARIANTES`, `_MOMENTOS`, `CARPETA_RENDERS`, `_CALIDADES`.

## `buildai/connectors/revit_kit.py`

Funciones públicas agrupadas por familia. Estas son las que el prompt del conector ofrece al modelo; las privadas se enumeran después.

| Familia | Función y firma exacta | Qué hace (docstring del kit) |
|---|---|---|
| Conversiones y salida | `xyz(x, y, z=0.0)` | Punto DB.XYZ a partir de coordenadas en METROS. |
| Conversiones y salida | `imprimir(texto)` | Acumula texto en la lista `salida` que el conector devuelve al modelo (en Revit no hay `stdout`). |
| Niveles | `niveles()` | Lista los niveles existentes (nombre y cota en metros) y los devuelve ordenados de abajo arriba. |
| Niveles | `nivel(altura, nombre=None)` | Devuelve el nivel situado en `altura` (metros); si no existe, lo crea. Usalo SIEMPRE antes de construir cada planta: nivel(0), nivel(3), ... |
| Muros y suelos | `tipo_muro(nombre=None)` | Primer tipo de muro basico cargado (o el que contenga `nombre`). |
| Muros y suelos | `muro(inicio, fin, nivel_base, altura=2.7, tipo=None, estructural=False)` | Muro recto entre dos puntos (x, y) EN METROS sobre `nivel_base` (objeto devuelto por nivel()). Devuelve el muro creado; guardalo si vas a insertarle puertas o ventanas. |
| Muros y suelos | `suelo(contorno, nivel_base, tipo=None)` | Suelo/forjado con planta poligonal: `contorno` es una lista de (x, y) en metros (3 puntos o mas, sin repetir el primero al final). |
| Familias y símbolos | `familias(categoria='puertas')` | Lista las familias cargadas de una categoria: "puertas", "ventanas", "mobiliario", "pilares", "luminarias" o "aparatos" (sanitarios). Consultala antes de colocar: |
| Puertas y ventanas | `puerta(muro_obj, a, nivel_base, tipo=None)` | Puerta insertada en `muro_obj` a `a` metros del arranque del muro. `tipo` filtra por nombre de familia/tipo (p. ej. "0.80"). |
| Puertas y ventanas | `ventana(muro_obj, a, nivel_base, antepecho=0.9, tipo=None)` | Ventana en `muro_obj` a `a` metros del arranque, con `antepecho` en metros. |
| Colocación y pilares | `colocar(categoria, posicion, nivel_base, rotacion=0, tipo=None)` | Instancia de familia suelta (mobiliario, luminarias, aparatos, pilares) en (x, y) metros sobre `nivel_base`; `rotacion` en grados. |
| Colocación y pilares | `pilar(posicion, nivel_base, rotacion=0, tipo=None)` | Pilar en (x, y) metros sobre `nivel_base` (usa la primera familia de pilar cargada, o la que contenga `tipo`). |
| Borrado | `borrar(elemento)` | Elimina un elemento (objeto o ElementId). Solo con permiso del usuario. |

**Funciones privadas o auxiliares:** `_a_pies`, `_a_metros`, `_elementos`, `_tipo_suelo`, `_simbolos`, `_buscar_simbolo`, `_activar`.
**Constantes:** `_PIES_POR_METRO`, `_CATEGORIAS`.

## `buildai/addons/blender/buildai_blender.py`

| Símbolo | Firma o tipo | Qué hace y devuelve | Notas |
|---|---|---|---|
| `_info_escena` | `_info_escena() -> str` | Resume versión de Blender, escena, objetos y colecciones como texto. | Enumera como máximo 120 objetos y resume el resto en una línea final. |
| `_procesar` | `_procesar(peticion: dict) -> dict` | Se ejecuta SIEMPRE en el hilo principal de Blender. | Captura `Exception` en los caminos previstos. |
| `_bombear_trabajos` | `_bombear_trabajos()` | Timer de Blender: ejecuta los trabajos pendientes en el hilo principal. | Captura `Exception`, `queue.Empty` en los caminos previstos. |
| `_atender_cliente` | `_atender_cliente(conexion: socket.socket)` | Lee una petición JSON del socket, la encola para el hilo principal y devuelve su respuesta. | Lee hasta el salto de línea, acota el timeout de la petición entre 10 y 1800 s y devuelve el traceback como error si algo falla. |
| `_bucle_servidor` | `_bucle_servidor(servidor: socket.socket)` | Acepta conexiones mientras no se pida detener y atiende cada una en su propio hilo. | Un hilo por conexión; el bucle termina cuando `accept()` lanza `OSError` al cerrarse el socket. |
| `register` | `register()` | Abre el socket en `127.0.0.1:PUERTO` y registra el timer que bombea trabajos al hilo principal. | No hace nada si ya hay servidor activo; si el puerto está ocupado avisa por consola y ese Blender no atiende. |
| `unregister` | `unregister()` | Detiene el bucle y cierra el socket del puente. | Marca `_detener`, cierra el socket suprimiendo errores y deja terminar a los hilos daemon. |
| constantes | `PUERTO` | Datos de prueba. | |

## `buildai/addons/revit/BuildAI.extension/startup.py`

| Símbolo | Firma o tipo | Qué hace y devuelve | Notas |
|---|---|---|---|
| `_contar` | `_contar(coleccion)` | Recuento compatible: GetElementCount existe desde Revit 2016. | Captura `AttributeError` en los caminos previstos. |
| `ping` | `ping(request)` | Responde `pong` para que el conector detecte el puente. | Responde `pong` sin abrir transacción; es la comprobación que usa `disponible()` del conector. |
| `info` | `info(request)` | Devuelve versión, documento, niveles en metros y recuento por categoría del modelo abierto. | Sin documento abierto responde `ok: False`; convierte pies a metros al listar niveles y devuelve la traza como error. |
| `ejecutar` | `ejecutar(request)` | Ejecuta el código recibido con `doc`, `uidoc`, `DB`, `revit` y `salida` disponibles. | Abre una transacción «BuildAI» y devuelve el traceback si algo falla; sin documento abierto responde `ok: False`. |

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
| `TestAdjuntosHistorial` | clase de pruebas | Agrupa regresiones. | La implementación de `TestAdjuntosHistorial` se ejecuta en el contexto de `tests/test_adjuntos_historial.py` y devuelve el valor indicado por su firma. |
| `_historial_dos_turnos` | `_historial_dos_turnos()` | Construye el historial de dos turnos con adjuntos que usan los tests. | Fija los datos mínimos que necesitan las comprobaciones de `_historial_para_modelo`. |
| `test_imagenes_viejas_no_se_reenvian` | `test_imagenes_viejas_no_se_reenvian(self)` | Comprueba el comportamiento cubierto por la regresión `test_imagenes_viejas_no_se_reenvian`. | La implementación de `test_imagenes_viejas_no_se_reenvian` se ejecuta en el contexto de `tests/test_adjuntos_historial.py` y devuelve el valor indicado por su firma. |
| `test_no_muta_el_historial_original` | `test_no_muta_el_historial_original(self)` | Comprueba el comportamiento cubierto por la regresión `test_no_muta_el_historial_original`. | La implementación de `test_no_muta_el_historial_original` se ejecuta en el contexto de `tests/test_adjuntos_historial.py` y devuelve el valor indicado por su firma. |
| `test_texto_del_turno_viejo_se_conserva` | `test_texto_del_turno_viejo_se_conserva(self)` | Comprueba el comportamiento cubierto por la regresión `test_texto_del_turno_viejo_se_conserva`. | La implementación de `test_texto_del_turno_viejo_se_conserva` se ejecuta en el contexto de `tests/test_adjuntos_historial.py` y devuelve el valor indicado por su firma. |
| constantes | `IMG_VIEJA`, `IMG_ACTUAL` | Datos de prueba. | |

## `tests/test_sanear_adjuntos.py`

| Símbolo | Firma o tipo | Qué hace y devuelve | Notas |
|---|---|---|---|
| `TestSanearAdjuntos` | clase de pruebas | Agrupa regresiones. | La implementación de `TestSanearAdjuntos` se ejecuta en el contexto de `tests/test_sanear_adjuntos.py` y devuelve el valor indicado por su firma. |
| `test_entradas_invalidas_no_gastan_cupo` | `test_entradas_invalidas_no_gastan_cupo(self)` | Comprueba el comportamiento cubierto por la regresión `test_entradas_invalidas_no_gastan_cupo`. | La implementación de `test_entradas_invalidas_no_gastan_cupo` se ejecuta en el contexto de `tests/test_sanear_adjuntos.py` y devuelve el valor indicado por su firma. |
| `test_se_respeta_el_tope_con_todo_valido` | `test_se_respeta_el_tope_con_todo_valido(self)` | Comprueba el comportamiento cubierto por la regresión `test_se_respeta_el_tope_con_todo_valido`. | La implementación de `test_se_respeta_el_tope_con_todo_valido` se ejecuta en el contexto de `tests/test_sanear_adjuntos.py` y devuelve el valor indicado por su firma. |
| `test_descarta_no_imagenes_y_base64_invalido` | `test_descarta_no_imagenes_y_base64_invalido(self)` | Comprueba el comportamiento cubierto por la regresión `test_descarta_no_imagenes_y_base64_invalido`. | La implementación de `test_descarta_no_imagenes_y_base64_invalido` se ejecuta en el contexto de `tests/test_sanear_adjuntos.py` y devuelve el valor indicado por su firma. |
| constantes | `_IMG` | Datos de prueba. | |

## Locks, cache y límites

La configuración usa el lock de `config`; `main` usa `_ocupado` para serializar el turno y una `queue` para SSE. Memoria y modelos tienen cache con firma o TTL. Los límites del agente son `MAX_PASOS`, `MAX_HISTORIAL`, `MAX_RESULTADO`, `RESULTADO_ANTIGUO_MAX` y `ENTRADAS_SIN_COMPRIMIR`; adjuntos y renders se validan en `main`.
