# 06 · Conectores

Un conector es el adaptador que hace visible un programa CAD/BIM al agente.
El protocolo base está en [`connectors/base.py`](../buildai/connectors/base.py).

## Contrato y descubrimiento

Cada clase define `id`, `nombre`, `icono` y `ayuda`, e implementa:

| Método | Contrato |
|---|---|
| `disponible() -> bool` | Comprueba de forma tolerante si el programa responde. No debe tumbar `/api/estado`. |
| `herramientas() -> list` | Devuelve esquemas con `nombre`, `descripcion` y parámetros JSON. |
| `ejecutar(nombre: str, argumentos: dict) -> str` | Ejecuta una herramienta conocida y devuelve texto truncado. |

[`CONECTORES`](../buildai/connectors/__init__.py) es el registro de instancias.
`buscar_herramienta` recorre conectores conectados y devuelve el conector y
la definición. La comprobación de disponibilidad de `main.py` se hace en
paralelo; una excepción se trata como desconectado.

## Blender

* **Detección y canal:** socket TCP en `127.0.0.1:8601`; `_enviar` manda una
  línea JSON y espera otra línea JSON. `ping` determina disponibilidad.
* **Herramientas:** `blender_informacion` y
  `blender_ejecutar_python(codigo)`. El segundo antepone el contenido de
  [`blender_kit.py`](../buildai/connectors/blender_kit.py) y compila el código
  con nombre `<codigo>`.
* **Puente:** [`buildai_blender.py`](../buildai/addons/blender/buildai_blender.py)
  registra un servidor y un timer. Las peticiones de hilos se encolan y
  `_bombear_trabajos` las ejecuta en el hilo principal de Blender.
* **Instalación:** [`instalador.py`](../buildai/instalador.py) copia el addon
  en la carpeta de scripts/addons detectada. Hay una copia raíz histórica,
  pero el empaquetado usa `buildai/addons`.

El kit ofrece muros, forjados, cubiertas, mobiliario, materiales, iluminación,
cámara y render en metros, evitando que el modelo repita detalles de `bpy`.

## AutoCAD

* **Detección y canal:** COM mediante `pythoncom.CoInitialize()`. Se prueban
  `AutoCAD.Application` y los ProgID versionados `.25` hasta `.18`.
* **Herramientas:** `autocad_informacion`,
  `autocad_ejecutar_python(codigo)` y `autocad_comando(comando)`.
* **Contexto Python:** el código recibe `acad`, `doc`, `ms`, `punto` y
  `puntos`; se ejecuta con `exec` y la salida se recorta con `recortar`.
* **Puente:** no hay addon: el canal COM es parte de AutoCAD y pywin32.
  El dibujo debe estar abierto y AutoCAD no puede ser LT.

## SketchUp

* **Detección y canal:** HTTP local en `127.0.0.1:8602`, con `GET /ping`,
  `GET /info` y `POST /ejecutar`.
* **Herramientas:** `sketchup_informacion` y
  `sketchup_ejecutar_ruby(codigo)`.
* **Puente:** [`buildai_sketchup.rb`](../buildai/addons/sketchup/buildai_sketchup.rb)
  ofrece un servidor HTTP sobre TCP, cola protegida por `Mutex` y
  `UI.start_timer` para ejecutar en el hilo de SketchUp. Incluye fallback JSON
  mínimo si no está disponible la librería `json`.
* **Instalación:** el instalador busca la carpeta Plugins de SketchUp y copia
  el Ruby. Se autoarranca al cargar la extensión.

La API de SketchUp usa pulgadas internamente; la descripción de herramienta
recomienda sufijos métricos Ruby como `.m`, `.cm` y `.mm`. El código enviado
debe respetar la API de Ruby de la versión instalada.

## Revit

* **Detección y canal:** pyRevit Routes en
  `http://127.0.0.1:48884/buildai`, con `/ping`, `/info` y `/ejecutar`.
* **Herramientas:** `revit_informacion` y
  `revit_ejecutar_python(codigo)`.
* **Puente:** [`startup.py`](../buildai/addons/revit/BuildAI.extension/startup.py)
  registra las rutas, abre `revit.Transaction("BuildAI")` y ejecuta con
  `doc`, `uidoc`, `DB`, `revit` y `salida`.
* **Unidades:** el kit recibe metros y traduce a pies. El código del conector
  elimina la cabecera de codificación para IronPython 2 y antepone el kit.
* **Instalación:** se copia la extensión bajo la estructura de pyRevit; se
  requiere pyRevit, Routes, proyecto abierto y reinicio cuando corresponda.

El modelo no debe abrir otra transacción: el puente ya la mantiene abierta.

## Kits frente a API cruda

`blender_kit.py` y `revit_kit.py` encapsulan unidades, creación repetitiva,
selección de tipos, materiales y errores comunes. Una skill puede pedir
`muro`, `suelo`, `cama` o `render` en vez de generar cientos de líneas de API.
No son una capa transaccional común ni garantizan que cualquier modelo
geométrico sea válido; los resultados siguen dependiendo del programa abierto.

## Añadir un conector

1. Crear una clase en `buildai/connectors/` heredando `Conector`.
2. Definir identidad, `disponible()` tolerante y canal local.
3. Diseñar herramientas pequeñas con esquemas y argumentos explícitos.
4. Implementar `ejecutar()` con validación, timeout y `recortar`.
5. Añadir la instancia a `CONECTORES` y verificar `buscar_herramienta`.
6. Añadir el puente dentro de `buildai/addons/` si el programa requiere
   ejecución en su hilo principal.
7. Incorporar copia e instalación en `instalador.py` y en
   [`buildai.spec`](../build_pkg/buildai.spec).
8. Añadir estado y ayuda a la UI solo si el contrato existente lo requiere.
9. Documentar puerto, versiones, unidades, instalación y límites.
10. Escribir pruebas de esquemas y fallos sin el programa abierto; no hacer
    depender las pruebas unitarias de una instalación CAD real.

La copia raíz de addons no es la fuente usada por las rutas de ejecución;
si se actualiza manualmente debe evitarse que diverja de `buildai/addons`.
