# 09 · Datos, sesiones y memoria

## Ubicación

[`rutas.py`](../buildai/rutas.py) centraliza el almacenamiento en
`Path.home() / ".buildai"`. No usa `%APPDATA%` para los datos propios, porque
el código contempla problemas de virtualización del Python de Microsoft Store.

```text
~/.buildai/
├── config.json
├── sesiones/
│   ├── <id>.json
│   └── ...
└── renders/
    └── *.png
```

La carpeta se crea bajo demanda. Durante una migración, si el destino no
existe, `rutas.py` copia o mueve los datos desde la ubicación antigua en la
raíz prevista por versiones anteriores; no sustituye un destino ya existente.

## Configuración

`config.json` contiene la selección de proveedor, modelos y claves:

```json
{
  "proveedor": "openrouter",
  "claves": {
    "openrouter": "secreto",
    "anthropic": ""
  },
  "modelos": {
    "openrouter": "qwen/qwen3-coder:free"
  }
}
```

Los campos exactos se normalizan en [`config.cargar`](../buildai/config.py).
`guardar` usa un lock de proceso. Se migran modelos retirados, por ejemplo
`deepseek/deepseek-chat-v3.1:free` a `qwen/qwen3-coder:free`. La API nunca
devuelve las claves completas.

## Sesiones

Cada conversación es un JSON de `sesiones/<id>.json`:

```json
{
  "id": "a1b2c3d4e5f6",
  "titulo": "Casa con patio",
  "creada": "2025-01-01T12:00:00",
  "actualizada": "2025-01-01T12:10:00",
  "historial": [
    {"tipo": "usuario", "texto": "Crea una planta", "adjuntos": []},
    {"tipo": "asistente", "texto": "", "llamadas": []},
    {"tipo": "resultado", "id": "x", "nombre": "muro", "contenido": "ok"}
  ]
}
```

`nuevo_id` genera 12 caracteres hexadecimales. `_ruta` acepta solo ids
alfanuméricos, evitando separadores y traversal. `guardar` serializa
`LlamadaHerramienta`; `cargar` reconstruye sus dataclasses. `para_ui` traduce
el historial a mensajes, llamadas y renders consumibles por JavaScript.

El ciclo de vida es: conversación nueva al arrancar, acumulación en memoria,
guardado en `finally` al terminar un turno, apertura mediante endpoint,
eliminación explícita y reinicio solo cuando no hay trabajo. Un trabajo en
curso se protege con el lock global de `main.py`.

## Memoria derivada

[`memoria.py`](../buildai/memoria.py) analiza sesiones guardadas y extrae
preferencias o contexto recurrente: materiales, funciones del kit, categorías
de proyecto y temas. Es una memoria derivada, no un almacén vectorial.

La cache se identifica por una firma basada en cantidad de archivos y mtime
más reciente. Si falla la lectura, el parseo o la extracción, devuelve texto
vacío para no impedir un turno. El agente incorpora ese texto en `_sistema`
como contexto de preferencias; no sustituye el historial activo.

## Renders

Los kits pueden guardar PNG en `~/.buildai/renders`. El agente conserva una
marca `RENDER_GUARDADO:` en resultados comprimidos y la API valida de nuevo el
nombre antes de servirlo. Solo se aceptan archivos `.png` sin separadores ni
nombre oculto.

## Privacidad y copias

Las sesiones contienen mensajes, resultados de herramientas y posiblemente
adjuntos base64; los renders pueden contener información del proyecto. Las
claves son secretos locales, aunque el proveedor remoto recibe los datos
necesarios para responder. El repositorio no cifra estos JSON ni implementa
caducidad o borrado automático. Deben protegerse la cuenta de Windows, las
copias de seguridad y cualquier exportación.
