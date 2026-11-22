---
version: 1
slug: "buildai-ui-index-html"
primary_target: "buildai/ui/index.html"
related_targets: []
---

# Superficie: interfaz principal de BuildAI

Modo: Operate. Visitante: arquitecto en sesiones largas con un programa CAD/BIM abierto, de día y de noche. Tarea: pedir un encargo, seguir al agente en vivo, recibir el resultado.
Restricciones: HTML/CSS/JS vanilla sin build, español, contrato de ids/clases con app.js y tests; tema claro y oscuro según el sistema; AA, texto ajustable, teclado completo, movimiento reducible.
Pendiente: nada sin decidir.

## Direction contract

THESIS: Calma modular. La pantalla es una hoja de papel dividida en módulos de proporción 1:2 y todo lo que no es la conversación se pliega a un riel o se abre bajo demanda. Rehúsa el chat de tres columnas con resplandores.

OWN-WORLD: Papel translúcido y madera quemada. Claro: ground gris-verdoso de papel (#F3F4F0, riel #E6E9E2), tinta casi negra verdosa, hairlines de 1 px; oscuro: carbón de madera (#151716) con tinta marfil frío. Un único acento índigo violáceo, reservado a lo pulsable, al foco y a la tira de fases (la firma, única excepción). Verde pino solo para conectado, ámbar para atención, rojo para error. Sin degradados, sin sombras de color, sin glassmorphism. Radios pequeños y constantes; módulos con borde hairline. Tipografía de sistema (Segoe UI Variable) con cifras tabulares para tiempos y conteos.

STORY: El usuario entiende en un vistazo en qué fase está el agente, confía en que actúa sobre su programa y recibe el resultado como protagonista. Cree que la herramienta es sobria y fiable. Pide, sigue y recibe.

FIRST VIEWPORT: Riel de iconos a la izquierda (60 px: marca, historial, tareas, programas) que se abre como panel de 280 px al pulsar; nueva conversación, exportar, ajustes y actividad están en la barra superior. Centro: columna de lectura de 46 rem con titular a la izquierda, cuatro encargos de ejemplo en una cuadrícula de hairlines con filas 2:1 y 1:2, y el compositor anclado abajo con acción principal índigo. La actividad y los entregables viven en un cajón derecho bajo demanda. La tira de fases ocupa un módulo sobre el compositor (no en la barra superior) y aparece mientras la IA trabaja.

FORM: Candidata 5 de mi lista ordenada (tatami/shoji como módulo y papel); seed:d9927896483a810f. Firma: la tira de fases ocupa un módulo fijo sobre el compositor y su animación cambia por fase, con icono giratorio propio y una palabra de estado propia, y un remate especial al entregar el resultado.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
