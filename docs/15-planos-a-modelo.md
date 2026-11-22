# 15 · Planos → modelo

El usuario adjunta un plano (foto, escaneo, PDF o DXF) y BuildAI lo reconstruye a escala real en el programa conectado: casa 3D en Blender o SketchUp, planta 2D por capas en AutoCAD o modelo BIM nativo en Revit. Este documento explica cómo se consigue la fidelidad y dónde vive cada pieza.

## La idea: la IA entiende, el código mide

Un modelo de visión **entiende** un plano: sabe qué es una puerta, lee las cotas y el nombre y la superficie de cada estancia. Pero **estima mal las coordenadas**: falla por decenas de píxeles. Por eso la reconstrucción no la dibuja la IA a mano, sino una cadena determinista:

```
adjunto ──► plano_detectar_muros (imagen/PDF)  ─┐
        └─► plano_leer_dxf (DXF, exacto)        ├─► la IA escribe el PLANO NEUTRO (JSON)
                                                │      muros + huecos + estancias + cotas
                                                ▼
            plano_reconstruir ─► normalizar() ─► informe + imagen de control
                                  │
                                  └─► constructores ─► herramienta de ejecución del conector
                                       (Blender · AutoCAD · SketchUp · Revit)
```

## Piezas (`buildai/planos/`)

| Módulo | Qué hace |
|---|---|
| [`detector.py`](../buildai/planos/detector.py) | Mide los muros de una imagen al píxel con numpy + Pillow (sin OpenCV). Primero binariza con un umbral local, que tolera iluminación desigual, y estima el giro del dibujo en ±6° para enderezarlo. Después calcula el espesor dominante de trazo y aplica una apertura morfológica que borra lo fino (cotas, textos, carpintería). Por último forma bandas horizontales y verticales, las parte donde cambia el espesor (tabique alineado por la cara con una fachada) y las recorta a ejes. También devuelve los cortes de los muros que pueden ser puertas o ventanas. |
| [`importar.py`](../buildai/planos/importar.py) | **PDF:** renderiza cada página con pypdfium2 en dos resoluciones, una vista de 1568 px para el modelo y un original de 3000 px para el detector. **DXF:** lee la geometría con ezdxf. Los muros salen de emparejar las dos caras paralelas de cada muro, las puertas de sus arcos de giro y las ventanas de sus bloques; los textos se devuelven con su posición. Los originales se guardan en `~/.buildai/planos/` (30 días) con un id aleatorio. |
| [`modelo.py`](../buildai/planos/modelo.py) | `normalizar()`: unidades y escala, giro, limpieza y huecos. Detalle en la sección siguiente. |
| [`geometria.py`](../buildai/planos/geometria.py) | Rejilla comprimida (sin librerías de geometría): recintos, huella y líneas de la unión de muros. Las superficies son **exactas**, no por píxeles. |
| [`constructores.py`](../buildai/planos/constructores.py) | Código para cada programa a partir del plano normalizado. Detalle en la tabla de programas. |
| [`vista.py`](../buildai/planos/vista.py) | Imagen de control: la reconstrucción encima del original atenuado, o la planta limpia si venía en metros. Se guarda como render y aparece en el chat. |
| [`herramientas.py`](../buildai/planos/herramientas.py) | Las tres herramientas del agente y la numeración de adjuntos que ve el modelo. |

### Qué hace `normalizar()`

- **Escala y giro.** Convierte unidades (px, cm, mm o m). En px calibra con la **mediana** de las cotas que indica la IA y avisa de las que discrepan más de un 2 %. Aplica el giro del dibujo.
- **Limpieza.** Endereza los muros desviados menos de 4°, alinea los ejes casi coincidentes (ponderando por longitud) y funde los tramos colineales, también los que un tabique interrumpe en un DXF.
- **Esquinas sin solapes.** En una L, el muro horizontal llega a la cara exterior del vertical. En una T, el muro que llega se detiene en la cara del que sigue.
- **Huecos medidos en el dibujo.** Si el centro de una puerta cae en el corte entre dos tramos, el ancho es el del corte y los tramos se unen. Si cae sobre un macizo, se usa el ancho leído.
- **Cortes sin declarar.** Se puentean para calcular estancias y huella, y se avisa de cada uno con su posición.
- **Comprobación de superficies.** Compara la superficie útil de cada estancia (el recinto que contiene su rótulo) con la del plano y avisa si difieren más de un 5 %.

### Qué genera cada constructor

| Programa | Resultado |
|---|---|
| Blender | Kit `muro`/`forjado`: solera, acabado por estancia y capa «Plano - <planta>». |
| AutoCAD | Lee `INSUNITS` para escribir en las unidades del dibujo. Unión de muros en una sola línea con relleno sólido, puertas con su arco de giro, ventanas, rótulos con m² y cotas generales. |
| SketchUp | Ruby: la cara de cada muro con sus huecos recortados, extruida su espesor, con vidrio en las ventanas. |
| Revit | Kit BIM. Muros por eje con el tipo de espesor más cercano, puertas y ventanas con la familia de ancho más cercano (o aberturas libres si no hay familias cargadas), suelo y habitaciones con nombre. |

## Integración

- **Agente** ([`agent.py`](../buildai/agent.py)): las tres herramientas y su receta (`SECCION_PLANOS`) solo se envían cuando la conversación trae un plano: hay adjuntos en este turno o en uno anterior, o el mensaje menciona un plano, un DXF, un PDF o un croquis (`_con_planos`). Son unos 8 000 caracteres por petición que en el resto de conversaciones solo encarecerían y saturarían el contexto de los modelos gratuitos y locales. No necesitan programas abiertos: validar funciona sin ellos. La vista del historial que recibe el modelo añade al mensaje una nota que numera los adjuntos e indica cuáles son páginas de PDF o DXF; el texto guardado del usuario no cambia.
- **API** ([`main.py`](../buildai/main.py)): `POST /api/planos/importar` recibe `{nombre, datos (base64)}` de un PDF o DXF y devuelve los adjuntos de imagen con su `origen`. `_sanear_adjuntos` conserva `origen` solo si su id apunta a un original guardado de verdad.
- **Interfaz** ([`ui/app.js`](../buildai/ui/app.js)): el clip acepta `.pdf` y `.dxf` y los envía al importador antes de adjuntarlos. Las imágenes de control (`plano-*.png`) se rotulan «Plano · Reconstrucción sobre el plano original» y no como render, y la actividad de estas herramientas usa el icono de planta.

## Límites conocidos

- **Muros inclinados.** El detector solo mide los horizontales y verticales (tras enderezar); la IA añade los inclinados a mano y no cuentan para cerrar estancias.
- **Perspectiva.** Las fotos con perspectiva fuerte no se rectifican; el detector baja su «cobertura» y lo avisa.
- **Resolución.** Las imágenes adjuntas llegan reducidas a 1568 px por la interfaz. Basta para una vivienda, pero un PDF da más precisión porque el detector mide su original de 3000 px.
- **DWG.** No se lee: hay que abrirlo en AutoCAD o exportarlo a DXF.
- **Sin verificar en programas reales.** El código de SketchUp (Ruby) y de Revit se prueba contra dobles y como texto, no dentro de los programas.

## Pruebas

[`tests/test_planos.py`](../tests/test_planos.py) comprueba medidas, no solo que «algo» se construya. Trabaja con planos sintéticos de geometría conocida: una casa simple y una vivienda en L fotografiada, con muros grises, tabiques, ruido, giro y JPEG. Exige superficies exactas o con un error máximo de 0,1 m², y los huecos con su ancho.
