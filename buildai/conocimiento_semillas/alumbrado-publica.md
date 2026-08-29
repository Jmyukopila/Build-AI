---
id: alumbrado-publica
nombre: Alumbrado público: niveles y distancias
tipo: norma
icono: iluminacion
descripcion: Normativa de iluminación en espacios públicos y vías
programas: [blender]
tags: iluminación, alumbrado, publica, normativa, espacios-exteriores
mostrar_boton: false
fuente: seed
---
## Alumbrado público: CTE DB-HE 3 / UNE 12464-2

**Iluminancias mínimas (lux) según tipo de vía:**

| Tipo de vía | Iluminancia media (lux) | Uniformidad min |
|---|---|---|
| Autopista, vía rápida | 20-30 | 0,4 |
| Vía principal | 15-20 | 0,4 |
| Vía secundaria | 10-15 | 0,4 |
| Calle residencial | 7,5-10 | 0,4 |
| Zona peatonal | 5-10 | 0,6 |
| Plaza pública | 10-20 | 0,5 |

**Disposición de luminarias:**
- Distancia entre farolas: 25-35 m típicamente (depende de altura y potencia)
- Altura de montaje: 6-10 m (vías principales), 4-8 m (secundarias), 3-5 m (peatonal)
- Separación lateral respecto a la calzada: 0,5-2,0 m

**Tipos de luminarias recomendadas:**
- LED (eficiencia moderna): 30-50 lm/W
- Sodio (tradicional): 100+ lm/W pero cromática fría
- Fluorescencia compacta: 50-70 lm/W

**Ángulo de radiación:**
- Downlight directo: minimiza luz intrusa hacia el cielo (contaminación luminosa)
- Ángulo de corte mínimo: 90° (no irradia hacia arriba)

Para modelado en Blender, usar luces emisoras (emissive planes o esferas de bajo brillo) en los puntos de luminarias; el render con Cycles respetará la intensidad en lux si se calibran correctamente.
