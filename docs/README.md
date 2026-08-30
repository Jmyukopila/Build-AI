# Documentación técnica de BuildAI

BuildAI es una aplicación de escritorio local para arquitectos. La ventana nativa se sirve con pywebview y muestra una interfaz web de JavaScript y CSS sin proceso de compilación. FastAPI escucha en `127.0.0.1:8600`; el agente conversa con el proveedor de IA elegido y ejecuta herramientas de Blender, AutoCAD, SketchUp y Revit mediante conectores.

Esta documentación describe el comportamiento implementado, no una arquitectura futura. Las referencias enlazan a la fuente de verdad del código.

## Mapa de documentación

| Documento | Contenido |
|---|---|
| [01 · Arquitectura](01-arquitectura.md) | Capas, dependencias, decisiones y límites. |
| [02 · Stack tecnológico](02-stack-tecnologico.md) | Tecnologías, versiones y compatibilidad. |
| [03 · Flujos de trabajo](03-flujos-de-trabajo.md) | Arranque, chat, herramientas, renders y sesiones. |
| [04 · API HTTP](04-api-http.md) | Endpoints locales y formato SSE. |
| [05 · Módulos y funciones](05-modulos-y-funciones.md) | Referencia de Python, kits, empaquetado y pruebas. |
| [06 · Conectores](06-conectores.md) | Protocolo, herramientas, puentes y extensión. |
| [07 · Proveedores de IA](07-proveedores-ia.md) | Historial neutro, adaptadores, reintentos y modelos. |
| [08 · Skills](08-skills.md) | Formato, carga y las 21 tareas predefinidas. |
| [09 · Datos, sesiones y memoria](09-datos-sesiones-y-memoria.md) | Persistencia local y preferencias. |
| [10 · Empaquetado y distribución](10-empaquetado-y-distribucion.md) | Instalación, PyInstaller e Inno Setup. |
| [11 · Buenas prácticas](11-buenas-practicas.md) | Convenciones existentes y deuda técnica. |
| [12 · Pruebas y desarrollo](12-pruebas-y-desarrollo.md) | Desarrollo en Windows y pruebas. |
| [13 · MCP y entorno asistido](13-mcp-y-entorno-asistido.md) | Servidores MCP del entorno de desarrollo y su relación con los conectores. |
| [14 · Plan de entrenamiento](14-plan-de-entrenamiento.md) | Plan por fases (trabajo futuro) para el dominio de las cuatro apps y el criterio de diseño. |

## Quiero… → lee…

| Quiero… | Lee… |
|---|---|
| Entender un turno de chat | [03 · Flujos](03-flujos-de-trabajo.md) y [04 · API](04-api-http.md) |
| Añadir una skill | [08 · Skills](08-skills.md) |
| Añadir un conector o puente | [06 · Conectores](06-conectores.md) |
| Añadir un proveedor | [07 · Proveedores](07-proveedores-ia.md) |
| Conocer una función | [05 · Módulos y funciones](05-modulos-y-funciones.md) |
| Entender claves, sesiones o memoria | [09 · Datos](09-datos-sesiones-y-memoria.md) |
| Empaquetar o instalar | [10 · Empaquetado](10-empaquetado-y-distribucion.md) |
| Ejecutar pruebas | [12 · Pruebas](12-pruebas-y-desarrollo.md) |
| Saber qué MCP se usan y por qué | [13 · MCP](13-mcp-y-entorno-asistido.md) |
| Mejorar lo que BuildAI sabe hacer | [14 · Plan de entrenamiento](14-plan-de-entrenamiento.md) |
| Revisar decisiones y límites | [01 · Arquitectura](01-arquitectura.md) y [11 · Buenas prácticas](11-buenas-practicas.md) |

## Fuente de verdad

El paquete ejecutable está en [`buildai/`](../buildai/__init__.py) y contiene también los recursos que se distribuyen con la aplicación: [`buildai/addons/`](../buildai/addons/blender/buildai_blender.py) (puentes), [`buildai/skills_data/`](../buildai/skills_data/01-casa-basica.json) (tareas rápidas) y `buildai/ui/` (interfaz). Son la única copia: en ejecución se leen desde ahí y son las que empaqueta PyInstaller, como explica [10](10-empaquetado-y-distribucion.md).

## Estructura del repositorio

| Carpeta | Contenido |
|---|---|
| `buildai/` | Paquete de la aplicación: servidor, agente, conectores, proveedores, interfaz y recursos. |
| `docs/` | Esta documentación técnica. |
| `empaquetado/` | Empaquetado de escritorio: spec de PyInstaller, script de Inno Setup y `build_installer.ps1`. |
| `tests/` | Pruebas con pytest. |
| `website/` | Landing estática de descarga, ajena al servidor de la app. |
