# 02 · Stack tecnológico

| Tecnología | Versión o compatibilidad | Papel | Dónde se usa | Encaje |
|---|---|---|---|---|
| Python | `>=3.11` | App, API, agente, conectores y empaquetado. | [`buildai/`](../buildai/__init__.py) | APIs, automatización y threading. |
| FastAPI | `>=0.110` | Rutas y `StreamingResponse`. | [`main.py`](../buildai/main.py) | API local pequeña y asíncrona. |
| uvicorn | `>=0.29` | Servidor ASGI en 8600. | [`main.py`](../buildai/main.py) | Embebido y sencillo. |
| httpx | `>=0.27` | Proveedores compatibles, Ollama, SketchUp, Revit y catálogo. | [`openai_compat.py`](../buildai/providers/openai_compat.py) | Timeouts y errores explícitos. |
| anthropic | `>=0.90` | SDK Claude y tool calling. | [`anthropic_provider.py`](../buildai/providers/anthropic_provider.py) | Conserva bloques originales. |
| pywebview | `>=5.3` | Ventana nativa de la UI. | [`main.py`](../buildai/main.py) | Escritorio sin servidor público; tiene fallback web. |
| pywin32 | `>=306`, Windows | COM y utilidades Windows. | [`autocad.py`](../buildai/connectors/autocad.py) | AutoCAD no necesita addon. |
| JavaScript y CSS vanilla | Sin build step | Chat, SSE, ajustes, historial y adjuntos. | [`ui/app.js`](../buildai/ui/app.js), [`ui/style.css`](../buildai/ui/style.css) | Se sirven como estáticos. |
| Ruby | Según SketchUp | Bridge y API de SketchUp. | [`buildai_sketchup.rb`](../buildai/addons/sketchup/buildai_sketchup.rb) | Lenguaje de extensiones. |
| IronPython o CPython | Según pyRevit | Routes y BIM en Revit. | [`startup.py`](../buildai/addons/revit/BuildAI.extension/startup.py) | Motores soportados por pyRevit. |
| COM | AutoCAD completo 2004+ | Instancia abierta y órdenes. | [`autocad.py`](../buildai/connectors/autocad.py) | Automatización incluida en AutoCAD. |
| JSON | Sin versión | Configuración, sesiones, skills y puentes. | [`config.py`](../buildai/config.py), [`sesiones.py`](../buildai/sesiones.py) | Legible y portable. |
| PyInstaller | Invocado por script | Directorio ejecutable. | [`buildai.spec`](../empaquetado/buildai.spec) | Distribución sin Python. |
| Inno Setup | `ISCC.exe` | Instalador, accesos y desinstalador. | [`BuildAI.iss`](../empaquetado/BuildAI.iss) | Instalación por usuario sin UAC. |

Las versiones de ejecución están en [`pyproject.toml`](../pyproject.toml) y [`requirements.txt`](../requirements.txt). Los entry points son `buildai = buildai.main:arrancar` y `buildai-instalar = buildai.instalador:instalar_todos`.

## Compatibilidad

| Programa | Canal y detección | Compatibilidad del código | Requisito |
|---|---|---|---|
| Blender | Socket 8601 y script startup. | Mínimo 2.80 en el conector y addon. README: 2.80–4.x. | Abrir o reiniciar. |
| AutoCAD | ProgID COM genérico y versionados 18–25. | Completo 2004+; no LT. | Dibujo abierto y permisos equivalentes. |
| SketchUp | HTTP 8602 y Ruby en Plugins. | Instalador busca 2014+; addon menciona camino histórico 8+. | Abrir una instalación nueva una vez. |
| Revit | Routes de pyRevit en 48884. | Revit 2014+ y pyRevit 4.8+. | pyRevit, Routes y proyecto abierto. |

El manual web menciona Blender 5.x y SketchUp 8+ en algunos textos, mientras README y detección automática son más conservadores. Se marca como limitación: la garantía operativa verificable por el código es Blender 2.80+ y SketchUp detectado desde 2014.

## Windows-first

El instalador consulta `%APPDATA%` y `%ProgramFiles%`, usa `cmd`, PowerShell, COM y accesos `.lnk`. `pywin32` se restringe a Windows en el proyecto. [`crear_acceso_directo`](../buildai/instalador.py) no lanza una excepción fuera de Windows: devuelve `{ok:false}` con el mensaje de que el acceso directo solo se crea en Windows. El núcleo HTTP puede ser portable, pero las integraciones CAD/BIM y distribución no lo son.