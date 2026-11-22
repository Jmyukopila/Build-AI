# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Existente: UI en HTML/CSS/JS vanilla sin paso de compilación (`buildai/ui/`), servida por FastAPI y mostrada en una ventana pywebview (WebView2 en Windows). Sin dependencias de frontend.

## Users

Arquitectos y estudios de arquitectura que ya trabajan en Blender, Revit, AutoCAD o SketchUp y piden en lenguaje natural lo que quieren construir, amueblar, iluminar, dibujar o renderizar, sin escribir código. Usan la app durante sesiones largas junto al programa CAD/BIM abierto, tanto de día en oficina como con poca luz en el estudio (decisión confirmada: la interfaz sigue la preferencia clara u oscura del sistema).

## Product Purpose

BuildAI conecta un agente de IA a los programas de arquitectura del usuario para que ejecute acciones reales sobre ellos y devuelva resultados verificables: modelos, planos, renders y archivos exportados (IFC, DWG, DXF, PDF). El éxito es que el usuario pida un encargo, vea qué está haciendo el agente en cada momento y reciba el resultado sin salir de la conversación.

## Positioning

Es un asistente local que actúa dentro de los programas del propio arquitecto (no un chat genérico que describe qué hacer), con datos y claves guardados solo en su ordenador.

## Operating Context

- El flujo es: elegir proveedor de IA en Ajustes, conectar un programa, pedir un encargo, seguir el trabajo en vivo (pensar, planificar, ejecutar acciones sobre el programa) y recibir un resultado (respuesta, render o archivo).
- Conversaciones guardadas en el equipo; el usuario las retoma desde el historial.
- Tareas rápidas predefinidas y encargos de ejemplo.
- Un panel de actividad lista las acciones sobre los programas, los renders y los entregables.

## Capabilities and Constraints

- Contrato de la interfaz con `app.js`: se conservan los identificadores y las clases que usan `app.js` y `tests/test_ui_entregables.py` (por ejemplo `.mensaje.entregable`, `.entregable-formato`, `.btn-entregable`, `#rail-entregables .entregable-archivo`, `.rail-vacio[data-vacio-de]`).
- Todo texto de interfaz, comentarios y código en español.
- Sin paso de compilación ni dependencias externas; debe funcionar sin conexión a internet.
- El navegador es WebView2/Chromium reciente.
- Los recursos viven solo dentro de `buildai/` (no se copian fuera del paquete).

## Brand Commitments

Nombre: BuildAI. Marca provisional sin identidad visual cerrada; el usuario pidió rehacer la interfaz por completo y no vincula la paleta anterior. Anteriormente pidió tonos púrpura y oscuros: queda como preferencia no vinculante, a decidir en la dirección visual de esta superficie.

## Evidence on Hand

Sin capturas de clientes ni métricas. `buildai/ui/assets/` contiene la marca: un módulo 1:2 (columna sólida y dos módulos) en cuadro índigo con nodos de circuito, generada con la imagen de ChatGPT y recortada con esquinas redondeadas. `icono-marca.png` (512 px, con transparencia) es la fuente de la que salen `favicon.png`, `buildai.ico`, `logo.png` y `marca.svg` (SVG con el PNG incrustado, no un trazado vectorial). Hay una copia en `website/assets/` porque esa carpeta se publica aparte. La marca anterior (cubo cian y lima, y después el módulo dibujado a mano) se sustituyó.

## Product Principles

1. Un estado a la vez: el usuario siempre sabe en qué fase está el agente (recibiendo, pensando, actuando, entregando).
2. El resultado es el protagonista: renders y archivos mandan sobre el marco.
3. Poco ruido: cada elemento visible tiene una tarea; lo secundario se muestra bajo demanda.
4. El movimiento informa: la animación expresa una fase o un resultado y vive en un solo lugar de la pantalla.
5. Legible a cualquier hora de uso, con texto ajustable y teclado completo.

## Accessibility & Inclusion

Delegado por el usuario a criterio de diseño: objetivo WCAG 2.2 AA (contraste 4.5:1 en texto, 3:1 en componentes), foco visible, navegación completa con teclado, `prefers-reduced-motion` respetado (la fase de la IA sigue indicándose con texto y un icono estático), tamaño de texto ajustable por el usuario y objetivos táctiles mínimos de 40 px. Texto en español.
