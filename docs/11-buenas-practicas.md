# 11 · Buenas prácticas observadas

Este documento registra prácticas que ya aparecen en el código. Las
observaciones de deuda no son cambios propuestos ni sustituyen decisiones del
proyecto.

## Convenciones existentes

### Lenguaje y nombres

Funciones, variables, docstrings y textos de UI están mayoritariamente en
español: `ejecutar_turno`, `disponible`, `sesiones` y `recortar`. Mantener la
convención hace que el código y los mensajes sean coherentes
([`agent.py`](../buildai/agent.py)).

### Explicar el porqué

Los docstrings de [`rutas.py`](../buildai/rutas.py) justifican no usar
`%APPDATA%`; los de conectores explican los hilos principales de Blender y
SketchUp, y los comentarios de historial explican por qué se cortan entradas
al comienzo de un turno. Al añadir documentación o código, priorizar la
decisión y su restricción, no repetir literalmente el nombre de la función.

### Capas unidireccionales

El agente trabaja con contratos neutros; los adaptadores conocen cada API de
IA y los conectores conocen cada CAD. `main.py` coordina, pero no contiene la
traducción de todos los proveedores. Esta frontera limita el acoplamiento
([`providers/base.py`](../buildai/providers/base.py)).

### Conectores tolerantes

`disponible()` captura fallos de conexión. `main.py` comprueba programas en
paralelo y un fallo de un programa no impide mostrar los demás. Una herramienta
devuelve un error textual al agente en lugar de provocar que desaparezca todo
el turno ([`connectors/__init__.py`](../buildai/connectors/__init__.py)).

### Validación defensiva

`/api/renders/{nombre}` rechaza separadores, nombres ocultos, extensiones
incorrectas y archivos inexistentes. `sesiones._ruta` exige ids alfanuméricos.
`_sanear_adjuntos` valida tipo, base64, tamaño y cupo antes de guardar o
enviar ([`main.py`](../buildai/main.py)).

### Límites explícitos

Los límites de 100 pasos, 120 entradas, 8000 caracteres por resultado nuevo,
600 para resultados antiguos, 12 imágenes y 8 MiB por adjunto acotan coste,
memoria y riesgo. No se deben eliminar sin analizar el efecto en proveedores
y UI.

### Thread-safety

`_ocupado` serializa la conversación activa, `config._lock` protege el JSON,
los bridges usan `queue` o `Mutex` y el trabajo del agente corre en un hilo
separado. La cola entre trabajo y SSE evita ejecutar una petición bloqueante
en el event loop.

### Degradación elegante

El catálogo de modelos tiene respaldos y cache cuando no hay red. Si falta
pywebview, `arrancar()` abre el navegador. La memoria devuelve texto vacío
ante fallos. Esta política de best-effort mantiene disponible la aplicación,
pero no inventa que un CAD esté conectado.

### Datos y frontend

Los datos de usuario se mantienen en `~/.buildai`, fuera del código instalado.
La UI es JavaScript/CSS vanilla, se sirve como estática y no exige Node ni
build step. Esto reduce la cadena de herramientas, a cambio de más lógica
manual en [`app.js`](../buildai/ui/app.js).

## Cómo contribuir

1. Leer el módulo y sus docstrings antes de modificarlo.
2. Mantener nombres y mensajes en español y cambios pequeños.
3. Añadir la lógica en la capa correcta: adaptación en proveedor o conector,
   no en el contrato neutro.
4. Validar entradas externas y conservar límites y timeouts.
5. Añadir o actualizar pruebas cuando el comportamiento sea aislable.
6. Ejecutar `python -m pytest tests -q` desde un entorno virtual (el suite
   no necesita Windows ni programas CAD abiertos: usa dobles).
7. Para cambios de UI, revisar el navegador local; para bridges, probar con
   el programa abierto y también comprobar el fallo desconectado.

## Qué no hacer

* No ejecutar código CAD/BIM recibido sin comprender el contexto de
  transacción, unidades y permisos.
* No guardar secretos en el repositorio ni devolverlos por la API.
* No introducir formatos específicos de proveedor en las sesiones.
* No aceptar rutas o ids sin validación.
* No volver a crear copias de `addons/` o `skills_data/` fuera del paquete: el
  runtime y el empaquetado solo leen las de `buildai/`.
* No crear una segunda transacción en Revit ni bloquear el hilo principal de
  Blender o SketchUp.

## Deuda técnica observada

* No hay CI, linter, formateador ni pre-commit configurados.
* La cobertura automatizada se concentra en adjuntos e historial.
* `main.py` mantiene estado global y solo soporta una conversación activa.
* Los puentes dependen de instalaciones y versiones externas difíciles de
  cubrir en pruebas unitarias.

Son riesgos de mantenimiento a vigilar, no defectos que esta documentación
pretenda corregir.
