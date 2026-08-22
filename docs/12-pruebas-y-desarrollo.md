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
python -m pytest tests -q
```

[`test_adjuntos_historial.py`](../tests/test_adjuntos_historial.py) verifica
que los adjuntos de turnos cerrados no se reenvíen al modelo, que el historial
original no se mute y que el texto de turnos antiguos permanezca. 
[`test_sanear_adjuntos.py`](../tests/test_sanear_adjuntos.py) comprueba que
entradas inválidas no consumen el cupo, que se acepten como máximo 12 imágenes
y que se descarten no-imágenes y base64 inválido.

No hay CI, linter ni pre-commit configurados. La prueba no requiere red,
claves ni un programa CAD abierto porque se centra en estructuras y
validación.

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
