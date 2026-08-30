# 14 · Plan de entrenamiento

> ⚠️ A diferencia de los documentos 01–13, que describen el comportamiento **implementado**,
> este describe **trabajo futuro**: un plan por fases para que BuildAI domine las herramientas
> de los cuatro programas y perfeccione ambientación, interiorismo y tipologías. Nada de lo que
> aquí se propone existe todavía en el código.

## Restricción transversal: coste cero

Todas las alternativas de este plan son **gratuitas**. Cuando una fase depende de software de
pago, se dice explícitamente y se propone el camino libre equivalente, aunque sea menos cómodo.
Lo disponible hoy en el equipo, sin coste:

| Herramienta | Estado | Uso en el plan |
|---|---|---|
| Blender 5.1 | Instalado (`C:\Program Files\Blender Foundation\Blender 5.1\blender.exe`) | Ejecutar el banco headless y renderizar |
| Ollama + `llama3.1` | Instalado | Modelo local gratis para el banco |
| OpenRouter `:free` | Sin clave de pago; [`modelos.py`](../buildai/modelos.py) ya filtra los `:free` con soporte de herramientas | Segundo modelo del banco |
| Python 3.11 + pytest | Instalado, ver [12 · Pruebas](12-pruebas-y-desarrollo.md) | Checks y pruebas de lógica pura |
| GPU propia (Cycles OPTIX) | En uso por `render()` | Renders y, en la fase 5, entrenamiento local |

Software de pago que el plan **no** requiere para avanzar: SketchUp Pro, AutoCAD y Revit. La
fase 2 explica cómo desarrollar y probar sus kits sin tenerlos.

## 0 · Diagnóstico

BuildAI no se entrena con fine-tuning: ya "entrena" al modelo en cada turno por tres vías.

| Vía | Dónde | Tamaño real |
|---|---|---|
| Conocimiento arquitectónico | `SISTEMA_BASE`, [`agent.py`](../buildai/agent.py) | 15.203 caracteres (~4.300 tokens, **siempre** enviados) |
| Vocabulario de herramientas | `REFERENCIA_KIT`, [`blender.py`](../buildai/connectors/blender.py) | 9.244 caracteres (~2.600 tokens) |
| Tareas guiadas | 21 JSON en [`skills_data/`](../buildai/skills_data) | A demanda, ver [08 · Skills](08-skills.md) |

Tres problemas bloquean la mejora:

1. **Asimetría entre programas.** [`blender_kit.py`](../buildai/connectors/blender_kit.py) tiene
   1.980 líneas y ~90 funciones de arquitectura;
   [`revit_kit.py`](../buildai/connectors/revit_kit.py), 273 líneas y cobertura parcial.
   **SketchUp (109 líneas) y AutoCAD (178) no tienen kit**: sus herramientas son ejecución de
   código crudo con consejos en la descripción. Fuera de Blender el modelo improvisa, que es
   justo donde fallan los modelos gratuitos y locales — los que usa la mayoría.
2. **El conocimiento no escala.** Los ~7.000 tokens de criterio viajan en *todos* los turnos.
   Cada ampliación ("más estilos", "más interiorismo") encarece cada petición y compite con el
   contexto de la tarea. En un modelo local o `:free` eso es exactamente el recurso escaso.
3. **No hay forma de medir.** Sin evaluación, ampliar prompts es adivinar y las regresiones
   pasan desapercibidas.

El orden de las fases se deriva de aquí: primero medir, luego cerrar el hueco más grande
(programas sin kit), luego hacer que el criterio pueda crecer, y por último afinar el resultado
visual.

## 1 · Fase 1 — Banco de evaluación

Sin números, las fases 2–4 son fe. Esta fase convierte cada mejora en una medida y detecta
regresiones al tocar prompts o kits.

**Ubicación**: `evaluacion/` en la raíz, fuera de `buildai/`. No se empaqueta:
[`empaquetado/buildai.spec`](../empaquetado/buildai.spec) solo incluye recursos del paquete.

**Formato de un encargo** — un JSON por encargo en `evaluacion/encargos/`:

```json
{
  "id": "casa-mediterranea-2p",
  "programa": "blender",
  "prompt": "Casa mediterránea de dos plantas de 12×9 m con porche y piscina",
  "checks": ["sin_errores", "estancias_iluminadas", "huecos_alineados", "materiales_variados"]
}
```

**Ejecución headless**, reutilizando dos patrones que ya existen:

- `blender -b --factory-startup --python <script>` — el modo ya validado para probar el kit.
- El script antepone `blender_kit.py` al código del modelo **igual que hace**
  `ConectorBlender.ejecutar()` en [`blender.py`](../buildai/connectors/blender.py), incluido el
  `compile(..., '<codigo>', ...)` que hace que los errores apunten al código del modelo y no al
  kit. Así el banco ejercita el mismo camino que la aplicación real, no una simulación.

**Checks** — funciones Python sobre la escena resultante, sin comparar píxeles (comparar
imágenes es frágil y caro; comprobar geometría es determinista y gratis):

| Check | Qué comprueba |
|---|---|
| `sin_errores` | Ningún resultado de herramienta empieza por `ERROR` |
| `pasos_consumidos` | Llamadas hasta terminar, frente al límite `MAX_PASOS = 100` de `agent.py` |
| `estancias_iluminadas` | Toda colección con forjado y cubierta tiene ≥1 luz |
| `huecos_alineados` | Ventanas de plantas superiores alineadas en X/Y con las inferiores |
| `pasos_libres` | ≥0,7 m entre muebles y muros (regla ya escrita en `SISTEMA_BASE`) |
| `materiales_variados` | ≥4 materiales distintos; no todo `blanco` |
| `camara_y_cielo` | Existe cámara activa y cielo o sol antes de renderizar |
| `revisar_escena_limpia` | `revisar_escena()` del kit no devuelve avisos |

**Modelos del banco — y por qué esto importa para el coste**: se ejecuta contra los dos caminos
gratuitos, que además son el escenario real del usuario final:

1. **Ollama local** (`llama3.1` instalado). Ilimitado, sin cuota, sin clave. Es el patrón de
   referencia para "¿funciona con un modelo modesto?".
2. **OpenRouter `:free`**. `modelos.py` ya consulta en vivo los modelos gratuitos con soporte de
   herramientas.

Los `:free` tienen **cuota diaria por cuenta**, así que el banco debe ser **reanudable por
diseño**: un archivo de resultado por encargo, y al relanzar se saltan los ya hechos. Sin eso,
agotar la cuota a mitad obliga a repetir todo. Es un requisito, no un detalle.

**Salida**: `evaluacion/resultados/<fecha>-<modelo>.json` y una tabla resumen por consola.

**Criterio de éxito**: línea base publicada con el porcentaje de checks superados por programa,
por categoría y por modelo.

**Coste**: cero. Blender headless y Ollama son locales; OpenRouter `:free` no cobra.

## 2 · Fase 2 — Paridad de kits entre programas

Un **contrato único de API arquitectónica**: mismos nombres, mismos parámetros, metros y eje Z
hacia arriba en los cuatro programas. El modelo aprende un solo lenguaje y `REFERENCIA_KIT` pasa
a ser un documento común con apéndices por programa, en vez de cuatro textos que divergen.

**Fuente del contrato**: el vocabulario ya probado de `blender_kit.py`.

| Nivel | Funciones | Blender | SketchUp | AutoCAD | Revit |
|---|---|---|---|---|---|
| Núcleo constructivo | `muro`, `ventanal`, `forjado`, `cubierta_plana`, `cubierta_dos_aguas`, `escalera`, `barandilla`, `rejilla_pilares`, `caja`, `terreno`, `material`, `coleccion` | ✔ | A implementar | Equivalente 2D | Parcial |
| Interiorismo | `dormitorio`, `salon`, `bano`, `cocina`, `comedor` + mobiliario suelto | ✔ | A implementar | Bloques en planta | Familias cargadas |
| Exterior | `piscina`, `arbol`, `arbusto`, `seto`, `celosia`, `pergola`, `valla`, `camino` | ✔ | A implementar | Simplificado | Componentes |
| Presentación | `cielo`, `camara`, `render`, `revisar_escena` | ✔ | Sombras y cámara | No aplica | No aplica |

**Implementación por programa.** El patrón de anteponer el kit al código del modelo ya existe en
`blender.py` y `revit.py`, y se reutiliza tal cual:

- **SketchUp** — `buildai/connectors/sketchup_kit.rb`, antepuesto en `ConectorSketchUp.ejecutar()`.
  Encapsula las trampas que hoy se le explican al modelo en prosa y que por tanto olvida:
  sufijos métricos `.m`/`.cm`, comprobar `cara.normal` antes del `pushpull`,
  `start_operation`/`commit_operation` para un deshacer limpio, grupos con nombre, y
  `ComponentDefinition` + `add_instance` para geometría repetida.
- **AutoCAD** — `buildai/connectors/autocad_kit.py`. Traducción 2D del contrato: `muro` → dos
  polilíneas en la capa `MUROS`, `forjado` → contorno, huecos → bloques de puerta y ventana, más
  `acotar()` y `capa()`. Es donde el criterio de `SISTEMA_BASE` ("cotas generales por fachada más
  cotas parciales de huecos", "1:50 o 1:100") deja de ser un consejo y pasa a ser ejecutable.
- **Revit** — ampliar `revit_kit.py` con lo que su propia descripción ya reconoce que falta:
  cubiertas, habitaciones, vistas y escaleras.

### Cómo se desarrolla y prueba esto sin licencias de pago

Este es el punto donde la restricción de coste cero muerde de verdad. SketchUp Pro, AutoCAD y
Revit son de pago y no están instalados. Además, **SketchUp Free es la versión web y no admite
extensiones Ruby**, así que no sirve como banco de pruebas ni siquiera para probar el puente.

La solución es de arquitectura, no de licencias: **cada kit se parte en dos capas**.

| Capa | Qué contiene | Se prueba… |
|---|---|---|
| **Lógica pura** | Cálculo de geometría: coordenadas de un muro con sus huecos, contorno de un forjado, peldañeado de una escalera, reparto de mobiliario en una estancia | Gratis, con pytest, sin abrir ningún programa |
| **Adaptador** | Las 20-40 líneas que traducen esa geometría a llamadas de la API nativa | Solo con el programa instalado |

La lógica pura es donde vive el criterio arquitectónico y donde están casi todos los errores; el
adaptador es mecánico. Con esto se puede escribir y verificar el 80 % de cada kit sin gastar un
euro. El adaptador queda marcado como **no verificado** en la documentación hasta que alguien lo
ejecute con el programa real — declararlo es preferible a fingir cobertura.

Complementos gratuitos para el 20 % restante:

- **Ruby** (RubyInstaller, libre) para comprobar sintaxis y ejecutar la lógica pura de
  `sketchup_kit.rb` contra un **stub** de la API de SketchUp (`Sketchup`, `Geom`, `entities`)
  escrito en el propio banco. No valida el comportamiento real, sí que el código corre y produce
  las coordenadas correctas. Ruby no está instalado hoy: instalarlo es gratis.
- **`ezdxf`** (librería Python libre) para volcar la salida del kit de AutoCAD a un DXF y
  comprobar capas, polilíneas y cotas sin AutoCAD. No cubre la capa COM, sí todo el dibujo.
- **Pruebas de un solo día**: si en algún momento hace falta validar los adaptadores, las pruebas
  gratuitas de 30 días de Autodesk y Trimble, o las **licencias educativas gratuitas** de
  Autodesk si el usuario cumple los requisitos, bastan para una sesión de verificación.
- **FreeCAD** (libre, con workbench BIM e IFC) queda anotado como posible destino adicional del
  contrato: sería el único programa BIM verificable al 100 % sin coste. No es un compromiso de
  este plan, sino una puerta abierta si Revit se vuelve un obstáculo.

**Criterio de éxito**: la lógica pura de los tres kits pasa sus pruebas, y los encargos de
SketchUp, AutoCAD y Revit del banco alcanzan un porcentaje de checks comparable al de Blender
cuando se ejecutan en una máquina con esos programas.

**Coste**: cero para desarrollar y para probar la lógica pura. La verificación de los adaptadores
depende de software de pago; el plan la aísla para que no bloquee nada más.

## 3 · Fase 3 — Conocimiento consultable en vez de prompt monolítico

Sacar el criterio arquitectónico del prompt fijo para que pueda crecer sin encarecer cada turno.
Es la fase que hace posible "perfeccionar ambientación, interiores y tipologías" sin límite.

**Estructura**: `buildai/conocimiento/*.md`, un archivo por dominio.

| Archivo | Contenido |
|---|---|
| `estilos.md` | Los diez lenguajes arquitectónicos, ampliados con materiales, proporciones y ejemplos |
| `interiorismo.md` | Ergonomía, regla 60-30-10, tres capas de luz, distribución por estancia |
| `ambientacion.md` | Hora del día, dirección y dureza de la luz, materiales, encuadre, escala |
| `tipologias.md` | Vivienda, edificio, local comercial, reforma, equipamiento |
| `normativa.md` | Valores del CTE y equivalentes, con el aviso de verificación local |
| `practicas-<programa>.md` | Convenciones de capas, unidades y flujo propias de cada programa |

**Acceso**: herramienta nueva `consultar_guia(tema)`. No es un conector, así que se registra
aparte en `agent.py`, junto a las que vienen de
[`connectors/__init__.py`](../buildai/connectors/__init__.py).

**En el prompt fijo queda** un índice de ~20 líneas (tema → una frase) y la regla de cuándo
consultar. `SISTEMA_BASE` baja de ~4.300 a ~800 tokens, y esos ~3.500 tokens liberados quedan
para la tarea — que en un modelo local es la diferencia entre terminar un edificio y quedarse a
medias.

**Recuperación**: por palabras clave sobre los títulos de sección. Sin dependencias nuevas y sin
servicios externos. Si algún día la base crece hasta que las palabras clave fallen, la
alternativa gratuita es generar embeddings **en local** con el Ollama ya instalado
(`nomic-embed-text`), nunca una API de pago.

**Riesgo declarado**: un modelo flojo puede no llamar nunca a `consultar_guia`. Mitigación: las
skills de `skills_data/` indican explícitamente qué guía consultar, y el índice del prompt lo
ordena para tareas de proyecto. El banco de la fase 1 mide si ocurre de verdad.

**Criterio de éxito**: tokens fijos por turno reducidos ≥50 % **sin** caída de checks en el banco.

**Coste**: cero. Archivos Markdown y búsqueda por palabras clave, sin dependencias.

## 4 · Fase 4 — Bucle de perfeccionamiento visual y lecciones aprendidas

Aquí mejora la ambientación de verdad: no basta con ejecutar las funciones correctas, el
resultado tiene que verse bien.

**Autocrítica visual.** Las dos piezas ya existen: `revisar_escena()` en `blender_kit.py` y
`render()`, que devuelve la imagen al chat mediante la marca `RENDER_GUARDADO:` que lee
`renders_en_resultado()` en `agent.py`. Falta cerrar el bucle:

1. Render en borrador.
2. El modelo **mira su propio render** y se autocritica contra una lista de ambientación: luz,
   materiales, vegetación, escala, encuadre, estancias apagadas.
3. Corrige lo que falle.
4. Render final.

Implementación: reinyectar la imagen del render como contenido del resultado de la herramienta.
**Verificar antes** si los proveedores admiten imagen en el rol `tool`
([`anthropic_provider.py`](../buildai/providers/anthropic_provider.py),
[`openai_compat.py`](../buildai/providers/openai_compat.py)); si no, va como mensaje de usuario
sintético.

**Aviso de coste**: `llama3.1`, el modelo local instalado, **no es multimodal**: no puede ver el
render. Caminos gratuitos, a comprobar en el momento y no dar por supuestos:

- Descargar un modelo de visión en Ollama (`llava`, `qwen2.5-vl`): descarga y uso gratis, solo
  cuesta espacio en disco y GPU propia.
- Usar un modelo `:free` multimodal de OpenRouter, si la lista en vivo que ya consulta
  `modelos.py` ofrece alguno con visión y herramientas.

Si ninguno está disponible, el bucle degrada limpiamente: `revisar_escena()` sigue dando la
crítica geométrica sin necesidad de ver la imagen. La fase no depende de que haya visión gratis.

**Memoria de lecciones.** [`memoria.py`](../buildai/memoria.py) ya destila un perfil de
preferencias (materiales, categorías de trabajo, temas recurrentes), cacheado por firma de la
carpeta de sesiones. Ampliarlo de "gustos" a "reglas": cuando el usuario corrige algo ("las
ventanas demasiado pequeñas", "no me pongas cubierta plana"), guardar la corrección como regla
persistente que se inyecta junto al perfil. Es aprendizaje real entre sesiones, a coste cero.

**Piezas de kit que faltan y que las skills ya prometen** — hueco barato y muy visible:
mostrador y expositores (`19-local-comercial.json`), cortinas y textiles
(`13-interior-llave-en-mano.json`), figuras humanas para dar escala, y entorno HDRI.

**Criterio de éxito**: mejora medible en los checks de ambientación del banco
(`estancias_iluminadas`, `materiales_variados`, `revisar_escena_limpia`).

**Coste**: cero. Los renders usan la GPU propia; los modelos de visión, gratuitos.

## 5 · Fase 5 (opcional) — Fine-tune real para el modo local

Solo tiene sentido después de las fases 1–4: con el banco funcionando, las trazas de los
encargos superados son el conjunto de entrenamiento para un **LoRA** sobre un modelo abierto,
que haría al modo local mucho más fiable usando las herramientas.

Todo el camino es gratuito:

- **Datos**: las propias trazas del banco, generadas en local.
- **Entrenamiento**: Unsloth o LLaMA-Factory, ambos libres, en el nivel gratuito de Google Colab
  o directamente en la GPU NVIDIA del equipo (la misma que Cycles usa vía OPTIX).
- **Despliegue**: exportar a GGUF y servirlo con un `Modelfile` del Ollama ya instalado.

No es un compromiso de este plan: sin las fases anteriores no hay datos ni forma de medir si
mejora algo.

## 6 · Orden y dependencias

| Fase | Depende de | Criterio de éxito medible | Coste |
|---|---|---|---|
| 1 · Banco de evaluación | — | Línea base publicada por programa y modelo | Cero |
| 2 · Paridad de kits | 1 (para saber si mejora) | Lógica pura en verde; SketchUp/AutoCAD/Revit comparables a Blender | Cero salvo verificación de adaptadores |
| 3 · Conocimiento consultable | 1 (para detectar regresión) | −50 % de tokens fijos sin perder checks | Cero |
| 4 · Bucle visual y lecciones | 1 y 3 | Mejora en los checks de ambientación | Cero |
| 5 · Fine-tune local | 1–4 | Modelo local por encima de su línea base | Cero |

La fase 1 va primero aunque no produzca nada visible: es lo que convierte las otras cuatro en
trabajo medible en vez de intuición.
