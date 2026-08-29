---
id: escalera-caracol-tecnica
nombre: Técnica de modelado: escalera de caracol
tipo: tecnica
icono: escalera
descripcion: Cómo construir una escalera de caracol helicoidal con el kit
programas: [blender]
tags: escalera, modelado, caracol, helicoidal, geometría
mostrar_boton: false
fuente: seed
---
## Modelado de escalera de caracol en Blender (usando el kit)

**Parámetros típicos:**
- Radio de la hélice: 0,8-1,5 m (depende del espacio disponible)
- Altura total: 2,8-3,0 m (piso a piso)
- Peldaños: 12-16 peldaños por vuelta (más de 16 hace cada paso muy pequeño)
- Ángulo de la hélice: típicamente 30-40° para comodidad de subida

**Procedimiento general:**
1. Crear la trayectoria helicoidal: plano XY con radio constante, elevación lineal en Z
2. Definir la sección transversal del peldaño (huella + contrahuella, típicamente 0,28m × 0,18m)
3. Barrer (extrude) la sección a lo largo de la hélice
4. Generar barandilla: offset de 0,9-1,0 m de altura desde el borde exterior de la hélice
5. Material y render: el kit permite asignar madera o acero según el estilo

**Dimensionamiento normativo (CTE DB-SUA):**
- Huella mínima en la línea de marcha (radio × ángulo/2): 0,24 m
- Contrahuella máxima: 0,18 m
- Ancho de peldaño: 0,90 m mínimo
- Diámetro interior: típicamente 1,5-2,0 m

**Errores comunes:**
- Hélice demasiado cerrada (radio pequeño) → pasos incómodos
- Peldaños con altura variable → resbalones
- Barandilla tocando la pared interior → obstruye paso

Consulta las funciones `escalera_caracol()` y `barandilla()` del kit de Blender para la implementación exacta.
