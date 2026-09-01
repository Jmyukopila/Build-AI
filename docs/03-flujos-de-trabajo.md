# 03 · Flujos de trabajo

## Arranque

```mermaid
flowchart TD
  A[arrancar] --> B[comprobar aviso]
  B --> C[iniciar hilo uvicorn]
  C --> D[esperar respuesta 15 segundos]
  D --> E{pywebview disponible}
  E -->|sí| F[crear ventana nativa]
  F --> G[iniciar webview]
  E -->|no| H[abrir navegador local]
  H --> I[unir hilo servidor]
```

[`arrancar()`](../buildai/main.py) muestra el aviso de instalación peligrosa, inicia uvicorn como daemon y espera con `_esperar_servidor`. Con pywebview crea una ventana 1280×820, mínima 960×640; sin él abre el navegador en 8600.

## Turno de chat

```mermaid
sequenceDiagram
  participant U as UI
  participant M as FastAPI
  participant Q as Cola SSE
  participant T as Hilo
  participant G as Agente
  participant P as Proveedor
  participant C as Conector
  participant X as Puente
  U->>M: POST api chat
  M->>M: sanear adjuntos
  M->>M: adquirir lock
  M->>T: iniciar trabajo
  T->>G: ejecutar turno
  G->>P: conversar historial neutro
  P-->>G: texto y llamadas
  G->>C: buscar herramienta
  C->>X: socket HTTP o COM
  X-->>C: resultado
  C-->>G: resultado textual
  G->>Q: eventos de estado
  Q-->>M: eventos
  M-->>U: SSE
  T->>M: guardar sesión y fin
  M-->>U: evento fin
```

[`chat()`](../buildai/main.py) rechaza una petición sin texto ni adjuntos o un segundo trabajo. El hilo ejecuta [`ejecutar_turno()`](../buildai/agent.py), guarda en `finally`, publica fin y libera el lock.

## Bucle del agente

```mermaid
flowchart TD
  A[crear proveedor] --> B[detectar conectores]
  B --> C[construir sistema y herramientas]
  C --> D[añadir usuario]
  D --> E[recortar historial]
  E --> F{pasos antes de 100}
  F -->|no| G[pausa de seguridad]
  F -->|sí| H{cancelado}
  H -->|sí| I[respuesta detenida]
  H -->|no| J[comprimir resultados]
  J --> K[emitir pensando]
  K --> L[conversar]
  L --> M{hay llamadas}
  M -->|no| N[respuesta final]
  M -->|sí| O[ejecutar herramientas]
  O --> P[guardar resultados y repetir]
  P --> F
```

Se permiten 100 iteraciones. La cancelación se consulta entre pasos; una herramienta ya iniciada termina para no dejar una llamada sin resultado. Herramientas desconocidas generan texto `ERROR`. Las marcas de render producen eventos después de validarse.

## Contexto

```mermaid
flowchart LR
  A[historial original] --> B[recorte por turnos]
  B --> C[comprimir resultados viejos]
  C --> D[vista modelo]
  D --> E[quitar imágenes viejas]
  E --> F[adaptador]
  A --> G[UI y sesión conservan adjuntos]
```

`_recortar_historial` elimina entradas antiguas hasta un mensaje `usuario`, evitando romper parejas tool-call y resultado. `_comprimir_resultados` deja los últimos 24 elementos intactos, recorta antiguos a 600 caracteres y conserva las marcas `RENDER_GUARDADO:` y `ARCHIVO_GUARDADO:`. `_historial_para_modelo` omite adjuntos de turnos cerrados, pero no muta la lista original.

## Render

```mermaid
sequenceDiagram
  participant G as Agente
  participant B as Blender
  participant K as Kit
  participant D as Disco
  participant M as API
  participant U as UI
  G->>B: ejecutar código con kit
  B->>K: llamar render
  K->>D: guardar PNG
  B-->>G: marca RENDER_GUARDADO
  G->>M: emitir render
  M-->>U: SSE render
  U->>M: GET renders nombre
  M->>D: validar ruta
  D-->>U: PNG
```

[`renders_en_resultado`](../buildai/agent.py) acepta solo archivos reales dentro de `~/.buildai/renders`; [`ver_render`](../buildai/main.py) rechaza separadores, nombres ocultos, extensiones no PNG o archivos inexistentes.

## Entregables

Los renders son imágenes; los entregables son los archivos de trabajo reales (IFC, DWG, DXF, PDF, GLB…) que exporta el propio programa del usuario. BuildAI no los construye: cada conector expone una herramienta `..._exportar` que le pide la exportación a Revit, AutoCAD, SketchUp o Blender y recoge el archivo.

```mermaid
sequenceDiagram
  participant G as Agente
  participant C as Conector
  participant P as Programa
  participant D as Disco
  participant M as API
  participant U as UI
  G->>C: llamar X_exportar formato
  C->>C: entregables.ruta_para
  C->>P: exportar con su propia API
  P->>D: escribir IFC DWG DXF PDF
  C-->>G: marca ARCHIVO_GUARDADO
  G->>M: emitir entregable
  M-->>U: SSE entregable
  U->>M: GET entregables nombre
  M->>D: validar ruta y extensión
  D-->>U: archivo como adjunto
```

El conector reserva el nombre con [`ruta_para`](../buildai/entregables.py), que sanea lo que propone el modelo. [`entregables_en_resultado`](../buildai/entregables.py) acepta solo archivos reales dentro de `~/.buildai/entregables` con extensión de `FORMATOS`, y [`descargar_entregable`](../buildai/main.py) repite esas comprobaciones sobre el nombre que llega por HTTP.

Revit es el único caso con ruta propia en el puente: su API prohíbe `Document.Export` dentro de una transacción y `/ejecutar` abre una siempre, así que la extensión expone `POST /exportar` aparte. Si esa ruta responde 404, la extensión instalada es anterior a esta función y el conector lo dice en vez de fallar en seco.

## Adjuntos

```mermaid
flowchart TD
  A[foto o vídeo] --> B[reducir en app.js]
  B --> C[vídeo extrae cuatro fotogramas]
  C --> D[base64]
  D --> E[POST chat]
  E --> F[filtrar image y base64]
  F --> G[historial usuario]
  G --> H[traducir visión]
  H --> I[modelo]
```

La UI usa canvas y selecciona cuatro tiempos de vídeo. El servidor admite como máximo 12 imágenes válidas y 8 MiB por cadena base64. Los proveedores convierten el formato a bloques Anthropic o `data:` URLs compatibles.

## Puentes

```mermaid
sequenceDiagram
  participant U as UI
  participant M as API
  participant I as Instalador
  participant P as Programa
  participant C as Conector
  U->>M: POST conectar id
  M->>I: instalar id
  I->>I: detectar y copiar puente
  I-->>M: resultado
  U->>P: abrir o reiniciar
  M->>C: disponible
  C->>P: ping o COM
  P-->>C: respuesta
  C-->>M: conectado
  M-->>U: punto verde
```

[`conectar`](../buildai/main.py) instala y llama a `disponible()` una vez. Puertos y protocolos están en [06](06-conectores.md).

## Sesiones

```mermaid
stateDiagram-v2
  [*] --> Nueva
  Nueva --> Activa: enviar mensaje
  Activa --> Guardada: guardar al final
  Guardada --> Activa: abrir
  Guardada --> Eliminada: borrar
  Activa --> Nueva: reiniciar si libre
  Guardada --> Exportada: exportar UI
  Exportada --> Guardada
```

`reiniciar`, `abrir`, `borrar` y `listar` están en [`main.py`](../buildai/main.py) y [`sesiones.py`](../buildai/sesiones.py). Exportar es una operación de `app.js` que descarga Markdown y no un endpoint.