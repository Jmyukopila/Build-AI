# 17 · IA incluida (gratis, sin clave)

BuildAI funciona nada más instalarlo, sin cuenta, sin clave y sin límites: trae un modelo ligero que corre en el propio ordenador. Es el proveedor por defecto (`"local"`). Los proveedores en la nube siguen disponibles en Ajustes para quien quiera más capacidad o rapidez.

## Por qué así

| Opción | Por qué no es la predeterminada |
|---|---|
| OpenRouter `:free` | Necesita cuenta y clave, y sin crédito solo admite 50 peticiones al día. Una tarea grande lo agota: es el origen del aviso «saturado». |
| Gemini gratis | Necesita cuenta de Google y clave. |
| Ollama | Hay que instalarlo aparte. Además su API compatible con OpenAI no deja ampliar el contexto: con 4 GB de VRAM se queda en 4 096 tokens y rechaza la petición completa de BuildAI. |
| **llama.cpp incluido** | Licencia MIT, 38 MB, viaja dentro del instalador y el contexto se fija al arrancar. **Elegido.** |

## Piezas

- [`buildai/ia_local.py`](../buildai/ia_local.py):
  - **Motor:** `llama-server` (llama.cpp), versión fijada (`_VERSION_MOTOR`) con su SHA-256. Se busca primero el incluido en la instalación (`<app>\motor`); si no está, se descarga la versión oficial.
  - **Modelo:** Qwen3.5-4B Q4_K_M (Apache 2.0, 2,7 GB), con URL y SHA-256 fijados. La descarga se verifica y se **reanuda** si se corta.
  - **Arranque del motor:** solo en `127.0.0.1:8610`, con 16 k de contexto, un solo hilo de servicio (`-np 1`), sin visión (`--no-mmproj`, ahorra unos 0,7 GB) y sin «pensar» en voz alta (`--reasoning-budget 0`). Se espera a `/health` y se cierra al salir de BuildAI.
  - **Estado** (`pendiente` → `descargando` → `arrancando` → `lista` | `error`): se publica en `/api/estado` como `ia_local` y la interfaz lo muestra en el banner.
- **Instalador:**
  - [`build_installer.ps1`](../empaquetado/build_installer.ps1) descarga y verifica el motor para Windows y lo mete en `dist\BuildAI\motor`.
  - [`BuildAI.iss`](../empaquetado/BuildAI.iss) descarga el modelo **durante la instalación** con la página de descarga de Inno Setup y lo deja en `%USERPROFILE%\.buildai\ia_local\modelos`. Si se cancela o falla, BuildAI lo descarga al arrancar.
  - `tests/test_ia_local.py` comprueba que las URL y los hashes del instalador coinciden con los de `ia_local.py`.

## Modo ligero

Un modelo de 4B con 16 k de contexto no puede con las instrucciones completas (unos 6 000 tokens de sistema y 3 000 de la referencia del kit), y además le confunden. Los proveedores `local` y `ollama` marcan `ligero = True`. Con eso, el agente ([`agent.py`](../buildai/agent.py)):

- **Instrucciones compactas:** usa `SISTEMA_LIGERO` y `SECCION_PLANOS_LIGERA` (unos 1 500 caracteres en vez de 17 000).
- **Herramientas reducidas:** usa `herramientas_ligeras()` de los conectores que la tienen; en Blender, la referencia compacta del kit con un ejemplo completo. Omite las herramientas de recursos y referencias.
- **Conversación acotada:**
  - recorta los resultados a 3 000 caracteres y comprime antes los antiguos;
  - ajusta la conversación a un presupuesto, quitando turnos enteros (`_ajustar_a_contexto`);
  - si el motor responde que no cabe (`ErrorContextoExcedido`), reintenta con la mitad.
- **No fingir trabajo:** si el usuario pidió un cambio y el modelo intenta terminar sin haber ejecutado ninguna herramienta, se le recuerda que lo haga de verdad (dos veces como máximo). Lo hicieron modelos reales en las pruebas. El recordatorio se marca `interno` y no se pinta en la interfaz.

## Límites honestos

- **Velocidad:** depende del equipo. En la máquina de desarrollo (GTX 1650, 4 GB) una petición ligera tarda decenas de segundos.
- **Capacidad:** un modelo de 4B resuelve bien tareas concretas (un muro, una estancia, una casa sencilla), pero se equivoca más en proyectos grandes de muchos pasos. Para eso conviene un proveedor en la nube.
- **Visión:** el modelo incluido arranca sin visión para ahorrar memoria. Los planos funcionan igual, porque las herramientas de planos miden la imagen.
- **Sin verificar:** solo hay motor fijado para Windows x64 y Linux x64; macOS queda pendiente. El instalador de Inno Setup no se ha compilado en esta sesión (requiere Windows).
