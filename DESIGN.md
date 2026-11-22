---
name: BuildAI
description: Interfaz de escritorio sobria para pedir encargos a un agente que actúa sobre Blender, Revit, AutoCAD y SketchUp. Papel translúcido de día, madera quemada de noche.
colors:
  fondo: "#E6E9E2"
  papel: "#F3F4F0"
  hoja: "#FBFBF9"
  hoja-hover: "#EBEEE7"
  tinta: "#1A1F1B"
  tinta-2: "#454D46"
  tinta-3: "#5D655D"
  linea: "#D4D8CF"
  borde-control: "#7C847A"
  accion: "#4B3FB0"
  accion-hover: "#3D3396"
  sobre-accion: "#FFFFFF"
  pino: "#27683A"
  ambar: "#80500A"
  rojo: "#A42838"
  fondo-oscuro: "#0F1110"
  papel-oscuro: "#151716"
  hoja-oscuro: "#1C1F1D"
  hoja-hover-oscuro: "#232725"
  tinta-oscuro: "#E9ECE5"
  tinta-2-oscuro: "#B3BBB2"
  tinta-3-oscuro: "#98A197"
  linea-oscuro: "#2A2F2C"
  borde-control-oscuro: "#6B746C"
  accion-oscuro: "#6E5FE6"
  accion-hover-oscuro: "#5A4BD4"
  acento-oscuro: "#B5ACFF"
  pino-oscuro: "#72CD8D"
  ambar-oscuro: "#EBBB52"
  rojo-oscuro: "#F28D99"
  overlay-modal: "rgba(8, 10, 8, 0.5)"
  overlay-cajon: "rgba(8, 10, 8, 0.45)"
  overlay-visor: "rgba(6, 8, 6, 0.9)"
typography:
  display:
    fontFamily: "'Segoe UI Variable Text', 'Segoe UI', system-ui, -apple-system, 'Helvetica Neue', Arial, sans-serif"
    fontSize: "clamp(1.75rem, 4.5vw, 2.25rem)"
    fontWeight: 650
    lineHeight: 1.15
    letterSpacing: "-0.02em"
  headline:
    fontFamily: "'Segoe UI Variable Text', 'Segoe UI', system-ui, sans-serif"
    fontSize: "1.25rem"
    fontWeight: 650
    lineHeight: 1.55
  title:
    fontFamily: "'Segoe UI Variable Text', 'Segoe UI', system-ui, sans-serif"
    fontSize: "1.0625rem"
    fontWeight: 650
    lineHeight: 1.55
    letterSpacing: "-0.01em"
  body:
    fontFamily: "'Segoe UI Variable Text', 'Segoe UI', system-ui, sans-serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.55
  label:
    fontFamily: "'Segoe UI Variable Text', 'Segoe UI', system-ui, sans-serif"
    fontSize: "0.9375rem"
    fontWeight: 600
    lineHeight: 1.5
  markdown-h1:
    fontFamily: "'Segoe UI Variable Text', 'Segoe UI', system-ui, sans-serif"
    fontSize: "1.375rem"
    fontWeight: 650
    lineHeight: 1.3
  markdown-h2:
    fontFamily: "'Segoe UI Variable Text', 'Segoe UI', system-ui, sans-serif"
    fontSize: "1.1875rem"
    fontWeight: 650
    lineHeight: 1.3
  mono:
    fontFamily: "ui-monospace, 'Cascadia Code', 'SF Mono', Consolas, monospace"
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: 1.6
rounded:
  fino: "4px"
  interno: "6px"
  r: "0.5rem"
  r-l: "0.75rem"
  pleno: "50%"
spacing:
  e1: "0.25rem"
  e2: "0.5rem"
  e3: "0.75rem"
  e4: "1rem"
  e5: "1.5rem"
  e6: "2rem"
  e7: "3rem"
  objetivo: "2.5rem"
  columna: "46rem"
components:
  boton-primario:
    backgroundColor: "{colors.accion}"
    textColor: "{colors.sobre-accion}"
    rounded: "{rounded.r}"
    height: "{spacing.objetivo}"
    padding: "0 1rem"
  boton-primario-hover:
    backgroundColor: "{colors.accion-hover}"
  boton-secundario:
    backgroundColor: "{colors.papel}"
    textColor: "{colors.tinta}"
    rounded: "{rounded.r}"
    height: "{spacing.objetivo}"
    padding: "0 1rem"
  boton-icono:
    textColor: "{colors.tinta-2}"
    rounded: "{rounded.r}"
    size: "{spacing.objetivo}"
  boton-icono-hover:
    backgroundColor: "{colors.hoja-hover}"
    textColor: "{colors.tinta}"
  mensaje-usuario:
    backgroundColor: "{colors.hoja}"
    textColor: "{colors.tinta}"
    rounded: "{rounded.r}"
    padding: "0.75rem 1rem"
  modulo-encargo:
    backgroundColor: "{colors.hoja}"
    textColor: "{colors.tinta}"
    rounded: "{rounded.r-l}"
    padding: "0.75rem 1rem"
  compositor:
    backgroundColor: "{colors.hoja}"
    textColor: "{colors.tinta}"
    rounded: "{rounded.r-l}"
    padding: "0.5rem"
  tira-de-fases:
    backgroundColor: "{colors.hoja}"
    textColor: "{colors.tinta}"
    rounded: "{rounded.r-l}"
    padding: "0.75rem 1rem"
  campo:
    backgroundColor: "{colors.papel}"
    textColor: "{colors.tinta}"
    rounded: "{rounded.r}"
    height: "{spacing.objetivo}"
    padding: "0 0.75rem"
---

# Design System: BuildAI

## Overview

**Creative North Star: "La hoja modular"**

La pantalla es una hoja de papel dividida en módulos. Lo único que ocupa el centro es la conversación, en una columna de lectura de 46 rem; todo lo demás se pliega a un riel de iconos a la izquierda o se abre bajo demanda como panel (17,5 rem) o cajón derecho (24 rem). El mundo es de día un papel gris verdoso con tinta casi negra verdosa, y de noche carbón de madera con tinta marfil frío. Un único índigo violáceo señala lo pulsable, el foco y la tira de fases (la excepción de la firma); verde pino, ámbar y rojo existen solo para estado.

La densidad es baja y regular. Los módulos se separan con hairlines de 1 px, no con sombras; los radios son dos, pequeños y constantes (más dos radios finos de 4 y 6 px para detalles internos). La cuadrícula de encargos de ejemplo comparte hairlines entre celdas, como un shoji. El movimiento vive en un solo sitio: la tira de fases sobre el compositor, que cambia de icono, de animación y de palabra según la fase del agente.

La interfaz sigue la preferencia clara u oscura del sistema, escala todo en rem (texto normal, grande, enorme) y respeta `prefers-reduced-motion`.

**Key Characteristics:**
- Un solo acento (índigo) para lo pulsable, el foco y la tira de fases; el color semántico nunca decora. La marca es neutra.
- Superficies planas con hairline; sin degradados, sin glassmorphism, sin halos de color.
- Columna única de lectura; navegación y actividad bajo demanda.
- Cifras tabulares en tiempos y conteos.
- Objetivos pulsables de 2,5 rem como mínimo.

## Colors

Un ground verdoso de papel con un único acento índigo; los valores se declaran una vez con `light-dark()` y la tabla de frontmatter recoge el valor claro y su par `-oscuro`.

### Primary
- **Índigo de acción** (#4B3FB0 claro / #6E5FE6 oscuro): fondo de la acción principal (enviar, guardar, conectar, descargar entregable) y campo enfocado. Hover #3D3396 / #5A4BD4 (en oscuro el hover es más profundo que el reposo). El texto sobre él es blanco (#FFFFFF).
- **Índigo de acento** (#4B3FB0 claro / #B5ACFF oscuro): iconos, enlaces, anillo de foco, pestaña activa y paso actual de la tira. Sobre él se apoyan sus tintes translúcidos (`acento-fondo` 9–12 %, `acento-linea` 38–42 %).

### Secondary
- **Verde pino** (#27683A / #72CD8D): solo conectado y entrega completada.
- **Ámbar** (#80500A / #EBBB52): solo atención (clave sin configurar, avisos).
- **Rojo** (#A42838 / #F28D99): solo error y borrado confirmado.

### Neutral
- **Marco** (#E6E9E2 / #0F1110): riel y fondo del cuerpo.
- **Papel** (#F3F4F0 / #151716): superficie de lectura, panel y cajón.
- **Hoja** (#FBFBF9 / #1C1F1D): módulos elevados (compositor, tarjetas, encargos, modales internos).
- **Hoja al pasar** (#EBEEE7 / #232725): hover y rellenos inactivos.
- **Tinta** (#1A1F1B / #E9ECE5), **tinta 2** (#454D46 / #B3BBB2), **tinta 3** (#5D655D / #98A197): texto, texto secundario, texto de apoyo (tinta 3 conserva 4,5:1 sobre papel y hoja).
- **Línea** (#D4D8CF / #2A2F2C): separadores decorativos de 1 px. **Borde de control** (#7C847A / #6B746C): límite de campos y botones, 3:1.
- **Overlays** (`rgba(8, 10, 8, 0.45)` cajón, `rgba(8, 10, 8, 0.5)` modales, `rgba(6, 8, 6, 0.9)` visor de imagen): velos neutros fijos, iguales en ambos temas; no son un color de marca.

### Named Rules
**La regla de la única voz.** El índigo solo marca lo pulsable, lo seleccionado, el foco y la tira de fases (excepción de la firma). Nunca rellena un módulo de contenido ni decora; el emblema de marca es neutro, con borde.
**La regla del estado.** Verde, ámbar y rojo significan conectado, atención y error; no se usan como color de marca ni de énfasis.
**La regla del par.** Todo color se declara una vez con `light-dark()`; no hay valores sueltos por tema.

## Typography

**Display Font:** Segoe UI Variable Text (con Segoe UI, system-ui, Helvetica Neue, Arial)
**Body Font:** la misma familia de sistema
**Label/Mono Font:** ui-monospace, Cascadia Code, SF Mono, Consolas (solo código y ayuda técnica)

**Character:** una sola familia de sistema, sin pareja decorativa. La jerarquía sale del peso (400, 600, 650) y del tamaño, no de otra fuente.

### Hierarchy
- **Display** (650, clamp(1.75rem, 4.5vw, 2.25rem), 1.15, -0.02em): saludo de bienvenida, una vez por pantalla.
- **Headline** (650, 1.25rem): título de modales y de ajustes. Los encabezados del markdown del agente usan 1,375 rem (h1), 1,1875 rem (h2) y 1,0625 rem (h3).
- **Title** (650, 1.0625rem, -0.01em): marca del panel, subtítulo de bienvenida (1,0625 rem regular).
- **Body** (400, 1rem, 1.55; texto largo del agente 1.7): conversación. Columna de 46 rem.
- **Label** (600, 0.9375rem): botones, estados, pie de tarjetas, pasos de la tira, tiempos con `tabular-nums`. 0,9375 rem es también el texto de apoyo (subió de 0,875 rem); 0,875 rem queda solo en bloques de código.

### Named Rules
**La regla de las cifras.** Tiempos y conteos llevan `font-variant-numeric: tabular-nums`.
**La regla de la rampa.** La rampa en uso es 0,875 (código) / 0,9375 (apoyo y etiquetas) / 1 / 1,0625 / 1,1875 / 1,25 / 1,375 / clamp 1,75–2,25 rem. El detector la marca como fuera de rampa en 0,9375, 1,1875 y 1,375 rem: son pasos deliberados (legibilidad del apoyo y jerarquía del markdown), no deriva.
**La regla del rem.** Todo tamaño de texto está en rem para obedecer el ajuste del usuario (100 / 112,5 / 125 %).

## Layout

Cuerpo en flex de dos zonas: riel (3,75 rem; 60 px) más panel opcional (17,5 rem) y zona principal. La zona principal es una columna: barra superior de 3,5 rem (menú, título de la conversación, lectura de estado, acciones), banner opcional, conversación y compositor. Conversación y compositor se centran en una columna de 46 rem con relleno mínimo de 1 rem. El cajón de actividad se superpone a la derecha (24 rem, máximo 92 vw) con fondo atenuado.

Escala de espaciado fija en rem: 0,25 / 0,5 / 0,75 / 1 / 1,5 / 2 / 3. La cuadrícula de encargos es de tres columnas con hairline compartida de 1 px; la primera y la cuarta celda ocupan dos columnas, de modo que las filas son 2:1 y 1:2. Pasa a una columna bajo 720 px.

Bajo 860 px el riel se convierte en una fila de pestañas con etiqueta dentro de un cajón izquierdo (máx. 20 rem, 88 vw). Bajo 720 px se oculta la lectura de estado y la pista del compositor.

### Named Rules
**La regla del módulo fijo.** La tira de fases ocupa siempre el mismo módulo sobre el compositor; no empuja ni salta el contenido.
**La regla del pliegue.** Lo que no es conversación vive en riel, panel o cajón, nunca en una tercera columna fija.

## Elevation & Depth

Plano en reposo; la profundidad se da por capas tonales (marco, papel, hoja) y hairlines de 1 px. Solo flotan los elementos desplazados sobre el contenido (cajón derecho, cajón móvil, modales, avisos, botón de ir abajo) con una única sombra neutra.

### Shadow Vocabulary
- **Flotante** (`box-shadow: 0 8px 28px rgba(8, 10, 8, 0.16)`): cajones, modales, avisos y botón de ir abajo.
- **Velo** (`background: rgba(8, 10, 8, 0.45)` cajón, `0.5` modal, `rgba(6, 8, 6, 0.9)` visor): atenúa lo que queda debajo; es un overlay, no una sombra.
- **Foco de campo** (`box-shadow: 0 0 0 1px var(--accion)`): refuerzo del borde en campo enfocado; no es elevación.

### Named Rules
**La regla de lo plano.** Un módulo en reposo no lleva sombra. La sombra señala que algo flota sobre la lectura.
**La regla del halo.** Nunca una sombra de color ni un resplandor.

## Shapes

Dos radios: 0,5 rem para controles, filas, imágenes y mensajes del usuario; 0,75 rem para módulos, tarjetas, compositor y modales. Dos radios finos para detalle interno: 4 px (anillo de foco, código en línea, marca de adjunto) y 6 px (realce del interruptor segmentado, concéntrico con su contenedor de 0,5 rem). Círculo completo solo para puntos de estado, el botón de ir abajo y el quitar-adjunto. Todo módulo lleva borde hairline de 1 px (línea) y los controles interactivos un borde de control más oscuro. Las celdas de encargos se recortan en un contenedor redondeado compartido. Los iconos son SVG de trazo propio (icons.js), a 1,25 rem en botones.

## Components

### Buttons
- **Shape:** radio pequeño (0,5 rem), altura mínima 2,5 rem, padding horizontal 1 rem.
- **Primary:** fondo índigo de acción, texto blanco, peso 600 (0,9375 rem). Hover pasa a acción-hover (#3D3396 claro, #5A4BD4 oscuro). Cobertura: guardar, conectar, descargar entregable, enviar.
- **Secondary:** transparente con borde de control, texto tinta; hover rellena con hoja al pasar.
- **Icon button:** 2,5 rem cuadrado, también en la variante chica (solo el icono baja a 1 rem), tinta 2; hover hoja al pasar y tinta; active tinte índigo.
- **Disabled:** opacidad 0,55 en botones en general. El enviar vacío no usa opacidad: lleva fondo hoja al pasar, texto tinta 3 y borde de control, legible y distinguible del enviar activo; el detener usa el mismo reposo y pasa a rojo al hover.

### Cards / Containers
- **Encargo de ejemplo (chip):** celda de la cuadrícula de tres columnas (filas 2:1 y 1:2), hoja, icono índigo, mínimo 4 rem de alto, hover hoja al pasar.
- **Mensaje del usuario:** módulo de ancho completo de columna, hoja con hairline de 1 px, radio 0,5 rem, padding 0,75 / 1 rem y cabecera «Tú» (650, 0,9375 rem, tinta 3). El agente responde sin módulo, a ancho de columna.
- **Entregable:** hoja con hairline, chip de formato neutro (borde de control, relleno hoja al pasar, peso 700) más botón primario.
- **Render:** hoja con hairline y marco de 0,5 rem alrededor de la imagen, máximo 36 rem.
- **Remate de llegada:** respuestas, renders y entregables recién llegados en vivo se despliegan con `.despliega` (recorte de izquierda a derecha, 760 ms); el historial guardado no.
- **Carga:** el esqueleto es un pulso de opacidad (0,55 a 1, 1,6 s), sin barrido.

### Inputs / Fields
- **Style:** campos de ajustes con fondo papel, borde de control, radio 0,5 rem, altura 2,5 rem. Compositor sobre hoja con borde de control y radio 0,75 rem; área de texto sin borde propio.
- **Focus:** borde índigo de acción más anillo de 1 px; el foco general es contorno de 2 px de acento con desfase de 2 px.
- **Error / Disabled:** error en rojo con tinte; el aviso de clave ausente en ámbar.

### Navigation
Riel de iconos de 3,75 rem: emblema de marca neutro (borde de control, tinta, sin relleno), pestañas de 2,5 rem; la activa lleva tinte índigo e icono índigo. El panel de 17,5 rem muestra el cuerpo de la pestaña (historial, tareas, programas) y, al pie, el manual y el modelo activo. En pantallas estrechas el riel pasa a fila con etiquetas visibles.

### Tira de fases (firma)
Módulo fijo sobre el compositor: icono de 2 rem con animación propia por fase (radar, órbita, rueda de pasos, cuadro que pulsa), palabra de estado con entrada propia, detalle truncado, tiempo con cifras tabulares y una fila de pasos con raya superior de 3 px (hecho en tinte índigo, actual en índigo pleno; esta tira es la excepción de la firma donde el índigo no marca algo pulsable). Al entregar, el módulo pasa a verde pino, el aro se traza, el visto se dibuja y un aro se expande una vez. Con movimiento reducido el icono queda quieto y los trazos aparecen completos.

### Named Rules
**La regla de la tarea.** Cada elemento visible tiene una tarea; lo secundario se muestra bajo demanda.
**La regla del movimiento único.** La animación continua vive solo en la tira de fases; el resto se limita a entradas de 140–420 ms.

## Do's and Don'ts

### Do:
- **Do** usar índigo solo para acción principal, selección, foco y la tira de fases; la marca queda neutra.
- **Do** separar módulos con hairlines de 1 px y radios de 0,5 / 0,75 rem.
- **Do** declarar cada color con `light-dark()` y comprobar 4,5:1 en texto y 3:1 en bordes de control.
- **Do** mantener los objetivos pulsables en 2,5 rem o más y todo tamaño en rem.
- **Do** expresar la fase con texto, icono y pasos además de movimiento, para que se lea con movimiento reducido.
- **Do** animar con las tres duraciones (140, 240, 420 ms) y las tres curvas del sistema.

### Don't:
- **Don't** usar degradados, glassmorphism ni sombras o halos de color.
- **Don't** dar un segundo acento ni colorear con verde, ámbar o rojo fuera de su estado.
- **Don't** añadir una tercera columna fija ni tarjetas anidadas en reposo.
- **Don't** introducir animación continua fuera de la tira de fases.
- **Don't** meter una fuente decorativa o de pantalla distinta de la familia de sistema.
- **Don't** volver a la identidad anterior (cubo cian y lima): la marca es el módulo 1:2 con nodos de circuito en cuadro índigo (`buildai/ui/assets/icono-marca.png`).
