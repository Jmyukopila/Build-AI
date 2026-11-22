# 16 · Recursos de render y fotos de referencia

BuildAI se conecta a dos bancos externos para que los renders se parezcan a una fotografía y no a una maqueta:

- **Poly Haven** (polyhaven.com): cielos HDRI reales, texturas PBR fotografiadas a tamaño real y modelos 3D de mobiliario. Licencia CC0 y API gratuita sin clave.
- **Banco de referencias**: fotos de arquitectura real que el usuario y la IA ven en el chat. Usa **Openverse**, sin clave y con millones de fotos Creative Commons, o **Pexels**, de más calidad media y con una clave gratuita opcional en Ajustes.

Además, la IA **ve** las imágenes que producen sus herramientas (renders, referencias y controles de plano). Sin eso, «compara el render con la referencia» era una instrucción imposible de cumplir.

## Piezas (`buildai/recursos/`)

| Módulo | Qué hace |
|---|---|
| [`polyhaven.py`](../buildai/recursos/polyhaven.py) | **Catálogo:** la API no busca por texto, así que se descarga el de cada tipo, se guarda en caché 24 h y se busca en local por nombre, etiquetas y categorías, con un mini diccionario español → inglés. **Descarga:** a `~/.buildai/recursos/polyhaven/<tipo>/<id>/` con verificación MD5, escritura atómica y un `manifest.json` (rutas locales y tamaño real de la textura). |
| [`referencias.py`](../buildai/recursos/referencias.py) | Busca, descarga y reduce cada foto a 1024 px. Graba la **atribución** (título, autor, licencia y fuente) en una franja inferior de la imagen, de modo que el crédito viaja con ella. Las guarda como `ref-*.jpg` en la carpeta de renders, así que la interfaz, la sesión guardada y la visión del modelo funcionan sin cambios. |
| [`herramientas.py`](../buildai/recursos/herramientas.py) | `recursos_buscar` y `recursos_descargar` (solo con Blender conectado) y `referencias_buscar` (siempre disponible). |

En el kit de Blender ([`blender_kit.py`](../buildai/connectors/blender_kit.py)), que solo lee archivos locales y nunca descarga nada:

- `hdri("<id>", fuerza, rotacion)`: entorno HDRI. En los HDRI «Pure Sky», que solo traen cielo, los rayos bajo el horizonte toman el color del horizonte; así no asoma la mitad negra tras el terreno.
- `material="ph:<id>"` en cualquier función del kit, o `material_pbr("<id>", escala)`: color, rugosidad y mapa normal con **proyección en caja** sobre coordenadas de objeto, a la escala real de la textura. No hace falta UV, porque las mallas del kit no lo tienen.
- `modelo("<id>", posicion, rotacion, nivel)`: importa el glTF y lo agrupa bajo un vacío para colocarlo.

## Visión de las imágenes de herramientas

1. **Registro.** Cuando un resultado anuncia una imagen (`RENDER_GUARDADO:`), el agente guarda solo su **nombre** en el historial (`resultado.imagenes`). La sesión guardada no engorda con base64.
2. **Preparación.** Al preparar cada petición, `_historial_para_modelo` carga las imágenes **del turno en curso**, como mucho `MAX_IMAGENES_HERRAMIENTA = 4` y las más recientes, reducidas a 1024 px en JPEG y cacheadas. Las añade como `imagenes_datos` (se describe en [`providers/base.py`](../buildai/providers/base.py)).
3. **Entrega al modelo.** Depende del adaptador:
   - **Anthropic:** van como bloques de imagen dentro del propio `tool_result`. Los resultados consecutivos se agrupan en un único mensaje de usuario.
   - **Compatibles con OpenAI:** un mensaje `tool` solo admite texto, así que van en un mensaje de usuario **después** de todos los resultados de ese paso.
4. **Modelos sin visión.** Ollama declara las capacidades de cada modelo (`/api/show`). Si no incluye `vision`, `ve_imagenes = False` y no se le envían imágenes. Si no se puede saber, se asume que sí, como antes.

## Licencias y privacidad

- **Poly Haven:** CC0, sin atribución obligatoria.
- **Openverse:** la licencia CC varía por foto; se muestra en el pie y en el texto que recibe la IA, que cita autor y fuente. Las fotos se usan como referencia, no se redistribuyen.
- **Pexels:** su licencia pide enlazar a Pexels y acreditar al fotógrafo; ambas cosas van en el pie y en el texto.
- **Unsplash queda fuera:** sus condiciones exigen mostrar las imágenes desde sus servidores, y aquí hay que descargar una copia para que la IA la vea.
- **Qué se envía:** a los servicios solo viajan las búsquedas, con un `User-Agent` genérico de BuildAI; nunca datos del usuario. La clave de Pexels se guarda en `config.json` (`servicios.pexels`) y la API nunca la devuelve al navegador.

## Límites

- Openverse indexa fotos de Flickr y Wikimedia: la relevancia es irregular y funciona mucho mejor con consultas en inglés. La herramienta pide al modelo que las escriba así.
- Solo Blender usa los recursos de Poly Haven. SketchUp y Revit podrían usar las texturas en el futuro.
- Las descargas se quedan en `~/.buildai/recursos/` sin caducidad. Una textura de 2k ronda los 5–10 MB.

## Pruebas

[`tests/test_recursos.py`](../tests/test_recursos.py) prueba el código con un transporte HTTP falso que imita las respuestas reales de las APIs: búsqueda, caché, MD5, rutas seguras, atribución, el paso a Openverse si falla Pexels, la visión con sus límites, la conversión en los dos adaptadores y que la clave no se filtre. El kit se verificó en Blender 5.3 real, con descargas reales y renders en Cycles.
