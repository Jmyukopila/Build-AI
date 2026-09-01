# 12 · Pruebas y desarrollo

## Entorno Windows

El proyecto está orientado a Windows por sus conectores COM, pywin32,
PyInstaller, Inno Setup y las instalaciones de CAD/BIM. Desde PowerShell:

```powershell
cd C:\Users\Administrator\repos\Build-AI
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Para instalar el proyecto editable se puede usar `python -m pip install -e .`.
La aplicación se arranca con:

```powershell
python -m buildai.main
```

Si falta pywebview, el servidor sigue funcionando y abre
`http://127.0.0.1:8600` en el navegador. Sin CAD abiertos, la UI y la API
pueden inspeccionarse, pero los conectores aparecerán desconectados.

## Pruebas existentes

```powershell
python -m pip install -e ".[dev]"
python -m playwright install chromium   # solo para las pruebas de interfaz
python -m pytest tests -q
```

Todas las pruebas usan `unittest.TestCase`, así que funcionan igual con
`python -m unittest tests.<modulo>`. No es un detalle estético: un archivo con
funciones sueltas al estilo pytest quedó meses sin ejecutarse porque `unittest`
no lo recogía y pytest no estaba instalado.

| Archivo | Qué fija |
|---|---|
| [`test_adjuntos_historial.py`](../tests/test_adjuntos_historial.py) | Los adjuntos de turnos cerrados no se reenvían al modelo y el historial no se muta. |
| [`test_sanear_adjuntos.py`](../tests/test_sanear_adjuntos.py) | Las entradas inválidas no consumen cupo; máximo 12 imágenes; se descarta base64 inválido. |
| [`test_conocimiento.py`](../tests/test_conocimiento.py) | Carga, búsqueda y guardado de recetas, con la carpeta del usuario aislada en un temporal. |
| [`test_entregables.py`](../tests/test_entregables.py) | Frontera de seguridad del canal de entregables: nada fuera de su carpeta, ninguna extensión que no sea de dibujo. |
| [`test_exportar_autocad.py`](../tests/test_exportar_autocad.py) | Se exporta una copia con `-WBLOCK` y **nunca** con `SaveAs`, que renombraría el dibujo abierto. |
| [`test_exportar_blender.py`](../tests/test_exportar_blender.py) | Validación de formato antes de abrir el puente y elección de operador `bpy`, con la caída de OBJ en Blender 3. |
| [`test_exportar_sketchup.py`](../tests/test_exportar_sketchup.py) | Ruby generado: guardia de SketchUp Pro, escapado de rutas de Windows y valor final como marca. |
| [`test_exportar_revit.py`](../tests/test_exportar_revit.py) | La ruta `/exportar` no abre transacción, versiones de IFC, selección de vistas y nombre real del archivo. |
| [`test_entregables_agente.py`](../tests/test_entregables_agente.py) | Circuito completo: la herramienta emite la marca, el agente el evento, y la marca sobrevive al recorte. |
| [`test_ui_entregables.py`](../tests/test_ui_entregables.py) | Interfaz real en Chromium: burbuja, rail, descarga íntegra. Se omite sola si falta Playwright. |
| [`test_empaquetado.py`](../tests/test_empaquetado.py) | Todas las rutas de `datas` del `.spec` existen. |

### Dobles de prueba

[`tests/dobles.py`](../tests/dobles.py) sustituye a los programas que BuildAI
pilota, porque ninguno existe fuera de Windows con la aplicación abierta:
`bpy` y `mathutils` falsos (sin ellos `blender_kit.py` ni siquiera se importa),
un documento COM de AutoCAD, un `httpx` de ida y vuelta para SketchUp y Revit, y
un pyRevit falso que captura las rutas que la extensión registra al importarse
— única forma de invocar `/exportar` sin Revit delante.

Los dobles **imitan el efecto, no solo la llamada**: escriben el archivo en
disco, porque el código de exportación espera a que aparezca. Prueban qué orden
se elige y qué se hace con la respuesta, no que AutoCAD acepte la orden; eso
sigue exigiendo un Windows con los programas instalados.

### Integración continua

[`.github/workflows/pruebas.yml`](../.github/workflows/pruebas.yml) ejecuta el
suite completo en Ubuntu con Python 3.11 y 3.13 en cada push y pull request.
Corre en Linux porque los dobles no necesitan Windows y `pywin32` solo se
instala en Windows por su marcador de entorno. No hay linter ni pre-commit.

## Depuración local

* Revisar la consola de `python -m buildai.main` para el aviso de instalación,
  servidor y errores de arranque.
* Consultar `GET /api/estado`, `GET /api/config` y `GET /api/skills` desde el
  navegador para separar problemas de UI y backend.
* Usar un proveedor Ollama local o un mock para no depender de una API remota.
* Probar `/api/chat` con un mensaje sencillo y observar cada evento SSE.
* Para un bridge, comprobar primero `ping`, después `info` y finalmente una
  operación de escritura pequeña en un archivo de prueba.
* En Revit revisar la transacción abierta; en Blender y SketchUp respetar la
  ejecución en hilo principal.
* No ejecutar código generado contra un modelo de producción sin copia.

## Cobertura futura sugerida

Sin convertir estas sugerencias en comportamiento existente, sería útil
cubrir:

* serialización y migración de sesiones;
* límites de historial, compresión y cancelación;
* validación de nombres de render;
* errores de cada proveedor, 429, `Retry-After` y respuestas malformadas;
* catálogo con cache, respaldo y ausencia de red;
* esquemas y búsquedas de todos los conectores;
* endpoints FastAPI mediante `TestClient`;
* carga de skills inválidas y duplicadas;
* instalación cuando no existe cada programa;
* contratos de los puentes con mocks de socket, HTTP y COM.

Las pruebas que necesiten Blender, SketchUp, Revit o AutoCAD deben separarse
de la suite rápida y declarar claramente sus requisitos externos.
