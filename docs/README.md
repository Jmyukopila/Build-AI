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
| Revisar decisiones y límites | [01 · Arquitectura](01-arquitectura.md) y [11 · Buenas prácticas](11-buenas-practicas.md) |

## Fuente de verdad

El paquete ejecutable está en [`buildai/`](../buildai/__init__.py). Las copias visibles de [`addons/`](../addons/blender/buildai_blender.py) y [`skills/`](../skills/01-casa-basica.json) son recursos de raíz; en ejecución se leen los recursos incluidos bajo `buildai/`, como explica [10](10-empaquetado-y-distribucion.md). La duplicación queda documentada como deuda técnica y no se modifica aquí.