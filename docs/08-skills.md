# 08 · Skills

Una skill es una tarea arquitectónica predefinida que aporta al agente un
prompt especializado. No es código ejecutable por sí mismo: el agente la
recibe desde la UI y decide cuándo utilizarla.

## Formato JSON

Los archivos se cargan exclusivamente desde
[`buildai/skills_data/`](../buildai/skills_data). Cada objeto debe tener:

| Campo | Obligatorio | Significado |
|---|---|---|
| `id` | Sí | Identificador usado por la UI. |
| `nombre` | Sí | Título visible. |
| `prompt` | Sí | Instrucciones que se añaden al mensaje. |
| `icono` | No | Icono; por defecto `tarea`. |
| `descripcion` | No | Texto auxiliar; por defecto vacío. |

[`cargar_skills()`](../buildai/skills.py) ignora JSON inválido, elementos que
no son objetos y archivos con campos obligatorios ausentes. No normaliza
duplicados ni valida un esquema más estricto. La carpeta raíz
[`skills/`](../skills) es una copia distribuida/histórica y no es la ruta que
lee esta función.

## Skills incluidas

| Id | Nombre | Uso |
|---|---|---|
| `casa-basica` | Casa básica 3D | Crear una casa sencilla en 3D. |
| `resumen-modelo` | Resumen del proyecto | Obtener un resumen del modelo abierto. |
| `limpiar-capas` | Organizar capas | Ordenar y limpiar capas. |
| `planta-acotada` | Dibujar planta en AutoCAD | Generar una planta acotada. |
| `luces-render` | Iluminar la escena | Preparar iluminación de render. |
| `muros-revit` | Muros en Revit | Crear muros con el kit. |
| `casa-moderna` | Casa moderna completa | Generar una vivienda moderna. |
| `edificio-viviendas` | Edificio de viviendas | Crear un conjunto residencial. |
| `interiorismo` | Diseño de interiores | Proponer un interior completo. |
| `render-fotorrealista` | Render fotorrealista | Ajustar cámara, materiales y luces. |
| `diseno-fachada` | Diseño de fachada | Diseñar una envolvente. |
| `fachada-propuestas` | Fachada: 3 propuestas | Producir alternativas de fachada. |
| `interior-llave-en-mano` | Interior llave en mano | Resolver un interior integral. |
| `cocina-diseno` | Cocina de diseño | Crear una cocina. |
| `bano-diseno` | Baño tipo spa | Crear un baño tipo spa. |
| `iluminacion-interior` | Iluminación interior pro | Diseñar iluminación interior. |
| `paisajismo-jardin` | Jardín y paisajismo | Crear jardín y vegetación. |
| `reforma-redistribucion` | Reforma y redistribución | Redistribuir un espacio existente. |
| `local-comercial` | Local comercial / tienda | Diseñar una tienda o local. |
| `vivienda-accesible` | Vivienda accesible | Considerar accesibilidad. |
| `diseno-bioclimatico` | Diseño bioclimático | Incorporar criterios bioclimáticos. |

Los textos completos y sus iconos son la fuente exacta de cada prompt; esta
tabla resume su intención visible.

## Crear una skill nueva

1. Crear `buildai/skills_data/<id>.json` con `id`, `nombre` y `prompt`.
2. Mantener el prompt orientado a decisiones verificables y a las
   herramientas realmente disponibles.
3. Añadir opcionalmente `icono` y `descripcion`.
4. Validar que el JSON sea UTF-8 y no tenga comentarios.
5. Reiniciar o volver a cargar la aplicación para que `GET /api/skills`
   devuelva la skill.
6. Si el proceso de distribución exige mantener la copia raíz, sincronizar
   `skills/` conscientemente; no asumir que esa copia cambia el runtime.

Una skill no añade permisos: las operaciones posibles siguen limitadas por
los conectores disponibles y por el proveedor que soporte tool calling.
