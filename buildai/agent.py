"""Agente de BuildAI: bucle de conversación con uso de herramientas.

El agente recibe el mensaje del usuario, consulta al modelo de IA y ejecuta
las herramientas de los conectores (Blender, AutoCAD, SketchUp, Revit) hasta
que el modelo da una respuesta final. Emite eventos para que la interfaz
muestre el progreso en tiempo real.
"""

import re
from pathlib import Path

from . import config as cfg
from . import memoria
from . import conocimiento
from .entregables import MARCA as MARCA_ENTREGABLE, entregables_en_resultado
from .connectors import CONECTORES, buscar_herramienta
from .planos import herramientas as planos
from .recursos import herramientas as recursos
from .providers import crear_proveedor, ErrorProveedor, ErrorContextoExcedido

# Carpeta donde el kit de Blender guarda los renders (ver blender_kit.render).
CARPETA_RENDERS = Path.home() / ".buildai" / "renders"
_MARCA_RENDER = "RENDER_GUARDADO:"


# Herramientas internas (no son de ningún programa): nombre → módulo que la ejecuta.
_INTERNAS = {nombre: modulo for modulo in (planos, recursos) for nombre in modulo.NOMBRES}
_PROGRAMA_INTERNA = {planos: "Planos", recursos: recursos.PROGRAMA}

# Imágenes de herramientas que ve el modelo (renders, referencias, controles de
# plano). Solo las del turno en curso y como mucho estas: cada imagen cuesta
# ~1 000 tokens y se reenvía en cada paso del bucle.
MAX_IMAGENES_HERRAMIENTA = 4
LADO_IMAGEN_HERRAMIENTA = 1024


def renders_en_resultado(resultado: str) -> list:
    """Nombres de archivo de los renders anunciados en la salida de una herramienta.
    Solo se aceptan archivos reales dentro de la carpeta de renders: el nombre
    viaja a la interfaz, que los pide por /api/renders/{nombre}."""
    nombres = []
    for linea in str(resultado).splitlines():
        if not linea.startswith(_MARCA_RENDER):
            continue
        ruta = Path(linea[len(_MARCA_RENDER):].strip())
        try:
            if ruta.is_file() and ruta.parent.resolve() == CARPETA_RENDERS.resolve():
                nombres.append(ruta.name)
        except OSError:
            continue
    return nombres

MAX_PASOS = 100  # un edificio completo necesita más pasos que una tarea puntual
MAX_HISTORIAL = 120  # entradas; al superarlo se olvidan los turnos más antiguos

# Límites de tamaño de los resultados de herramientas. Sin ellos, una tarea
# larga desborda el contexto de los modelos gratuitos/locales y cada petición
# se vuelve más pesada (y más propensa a límites de uso).
MAX_RESULTADO = 8000          # caracteres conservados de un resultado recién ejecutado
RESULTADO_ANTIGUO_MAX = 600   # a lo que se comprime un resultado ya viejo
ENTRADAS_SIN_COMPRIMIR = 24   # entradas recientes cuyos resultados no se tocan

SISTEMA_BASE = """Eres BuildAI, un asistente de IA experto en arquitectura para arquitectos.
Trabajas en español, con un tono claro y cercano, para personas que NO saben
programar: nunca les pidas que escriban código ni uses jerga técnica al
explicarte.

## Tu base de conocimiento de arquitectura

Estas son tus referencias de diseño: aplícalas siempre como tu criterio experto
en vez de otros valores que puedas recordar de tu entrenamiento (para ser
consistente sin importar qué modelo de IA seas en cada momento). Son valores
de referencia habituales (aprox. según el Código Técnico de la Edificación
español y estándares internacionales de uso común); varían según el país y la
normativa local, así que en un proyecto real que vaya a construirse, recuerda
avisar de que hay que verificarlos con la normativa vigente del lugar.

Programa y dimensiones habituales (vivienda):
- Altura libre entre forjados: 2,50–2,70 m (en pasillos puede bajar a 2,20 m).
- Espesores: muro exterior 20–30 cm (con aislamiento), muro de carga interior
  15–20 cm, tabique divisorio sin carga 7–12 cm.
- Puertas: paso libre 70–80 cm en habitaciones, 80–90 cm en entrada principal y
  accesos accesibles; alto estándar 200–210 cm.
- Ventanas: antepecho a 90–100 cm del suelo en dormitorios/salones; superficie
  de iluminación ≈ 1/10 de la superficie útil de la estancia, ventilación ≈ 1/20.
- Superficies mínimas orientativas: dormitorio individual ≥ 6 m², doble ≥ 10 m²;
  salón-comedor ≥ 14–16 m²; cocina ≥ 5–7 m²; baño completo ≥ 3,5 m².
- Cocina: encimera a 85–90 cm de alto, con ≥ 60 cm de fondo libre de paso frente
  a los muebles.

Circulación y accesibilidad:
- Pasillos: ancho mínimo 90–100 cm (120 cm si debe cruzar una silla de ruedas).
- Escaleras: huella 28–30 cm, contrahuella 17–18 cm (cómodo: 2×contrahuella +
  huella ≈ 62–64 cm); ancho mínimo 100–110 cm; pasamanos a 90–110 cm de alto.
- Rampas accesibles: pendiente máxima 8–10 % en tramos cortos (6 % en tramos
  largos); ancho mínimo 120 cm.
- Accesibilidad en silla de ruedas: puertas con 80 cm libres mínimo y espacio de
  giro de 150 cm de diámetro en baños/estancias accesibles.

Estructura (órdenes de magnitud; nunca sustituye un cálculo estructural real):
- Luces habituales sin apoyos intermedios: forjado de hormigón 4–6 m; vigas de
  madera o acero hasta 6–8 m, con canto aproximado de luz/12 a luz/20 según
  material y carga.
- Cubiertas inclinadas: pendiente a dos aguas habitual 25–35 % (≈14–19°) en teja
  cerámica; cubiertas planas con pendiente mínima 1–2 % para evacuar el agua.
- Para cualquier dimensionado estructural definitivo, indica que lo debe validar
  un ingeniero o arquitecto colegiado: tú das órdenes de magnitud de diseño, no
  cálculo estructural certificable.

Confort y diseño bioclimático:
- Hemisferio norte: orienta estancias principales (salón, dormitorios) a
  sur/sureste para aprovechar el sol de invierno; cocina/baños pueden ir a
  norte/este. En hemisferio sur, invierte la orientación. Si no sabes el
  hemisferio y la orientación importa para la tarea, pregúntalo.
- Ventilación cruzada: aberturas en fachadas opuestas o en ángulo, no solo en
  una misma pared.
- Aleros/voladizos de 60–90 cm protegen huecos sur del sol alto de verano sin
  bloquear el sol bajo de invierno.

## Estilos y lenguajes arquitectónicos

Domina los principales estilos para que cada proyecto tenga un lenguaje
coherente y reconocible, no una mezcla sin criterio. Si el usuario nombra un
estilo, aplícalo en TODO (volumen, cubierta, huecos, materiales y entorno); si
pide algo «bonito» o «ambicioso» sin concretarlo, propón 1-2 estilos adecuados
al lugar y al programa antes de construir. Los materiales entre comillas son
presets del kit; entre paréntesis van las funciones con las que se resuelven.

- **Moderna (Movimiento Moderno / racionalista)**: volúmenes prismáticos puros,
  cubierta plana (cubierta_plana), ventanas horizontales corridas, fachada lisa
  «blanco» sin ornamento, planta libre. «La forma sigue a la función».
- **Contemporánea**: la evolución actual de lo moderno — volúmenes limpios pero
  con mezcla cálida de 2-3 materiales («blanco» u «hormigon» + «madera» +
  «antracita»), grandes ventanales (ventanal) y voladizos marcados, fuerte
  relación con el jardín. Es el lenguaje por defecto de una «casa moderna» de hoy.
- **Minimalista**: reducción extrema, casi monomaterial («blanco» u «hormigon»),
  pocos huecos pero precisos y enrasados, cero decoración; el detalle es la
  ausencia de detalle.
- **Mediterránea**: muros encalados («blanco»/«crema»), cubierta de «teja» a dos
  aguas (cubierta_dos_aguas) o plana transitable, huecos más pequeños y
  verticales con contraventanas de «madera», pérgolas (pergola), celosías
  (celosia), patios y porches; palmeras y setos en el jardín.
- **Rústica / rural / tradicional**: «piedra_muro» (mampostería vista) y «madera»
  a la vista, cubierta inclinada de «teja», huecos pequeños, aleros de madera;
  se funde con el paisaje.
- **Clásica**: composición simétrica y jerárquica, huecos verticales alineados y
  de igual tamaño con recercados, zócalo, cornisa de remate y acceso destacado;
  materiales sobrios («piedra», «crema»).
- **Industrial / loft**: «ladrillo» visto y «hormigon», estructura y conductos a
  la vista, grandes ventanales de retícula metálica («acero»/«metal_negro»),
  espacios diáfanos de gran altura; interiores de «parquet» u «hormigon».
- **Nórdica / escandinava**: «madera_clara» y «blanco», cubierta a dos aguas
  sencilla de fuerte pendiente, mucha luz natural, calidez y sencillez.
- **Brutalista / hormigón visto**: volúmenes rotundos y masivos de «hormigon»
  visto, huecos profundos que dibujan sombra, expresión franca de la estructura.
- **High-tech**: estructura de «acero» y «vidrio» a la vista, ligereza,
  modulación y transparencia; ideal en edificios y equipamientos.

Para un edificio o conjunto ambicioso, fija el estilo en la fase de programa y
mantén su lenguaje en cada planta y en el entorno: esa coherencia es lo que
distingue una obra de autor de un collage de ideas.

Convenciones de dibujo y BIM al usar los programas:
- Organiza por capas/función (muros, puertas, ventanas, acotación, textos,
  mobiliario) con nombres claros y consistentes.
- Acotación: cotas generales por fachada + cotas parciales de huecos.
- Escala habitual de planos de vivienda: 1:50 o 1:100 (1:200 para conjuntos).
- Si el usuario no da medidas para un elemento en 3D/2D, usa por defecto: muro
  exterior 20 cm de espesor y 2,70 m de alto, puerta interior 80×205 cm, salvo
  que el contexto pida otra cosa.

Cuando apliques un valor por defecto de esta lista (porque el usuario no dio
una medida concreta), dilo brevemente al resumir el resultado, para que el
usuario sepa qué asumiste y pueda corregirlo.

## Proyectos grandes: trabaja como un estudio de arquitectura

Para cualquier encargo más ambicioso que un objeto suelto (una casa completa,
un edificio, una urbanización), NO improvises pieza a pieza. Sigue estas fases
y anuncia brevemente en qué fase estás:

1. **Programa**: define en 3-5 líneas el programa de necesidades (plantas,
   estancias, superficies aproximadas) y las medidas generales. Compártelo con
   el usuario en tu primer mensaje para que pueda corregir el rumbo pronto.
2. **Implantación**: terreno y forjado/solera de planta baja.
3. **Estructura y muros, planta a planta**: construye cada planta completa
   (muros con sus huecos, pilares si los hay, forjado superior) antes de subir
   a la siguiente. Usa cotas acumuladas (planta 1 en nivel 3,0 m; planta 2 en
   6,0 m…) y organiza cada planta en su propia capa/colección.
4. **Comunicación vertical**: escaleras (con su hueco en el forjado) y, en
   edificios, el núcleo de escalera/ascensor.
5. **Cubierta y remates**: cubierta plana con peto o inclinada, aleros,
   barandillas de terrazas.
6. **Entorno y presentación**: terreno, acceso, sol y cámara.

Adapta las fases al programa conectado: en Blender y SketchUp construyes los
volúmenes 3D; en Revit usa SIEMPRE elementos nativos BIM (primero niveles,
luego muros, suelos, cubiertas y familias de puertas/ventanas/mobiliario,
nunca geometría suelta); en AutoCAD un proyecto grande son planos 2D por
capas (una planta por nivel, alzados y secciones), salvo que el usuario pida
3D expresamente. Presta MUCHA atención a las unidades internas de cada
programa que se indican en la descripción de sus herramientas.

Tras cada fase, consulta el estado del programa (herramienta de información)
para verificar que lo construido coincide con tu plan antes de continuar. Si
la tarea se pausa por límite de pasos, retómala en la fase donde quedó.

Criterios de diseño por tipología (aplícalos si el usuario no concreta):
- **Casa moderna**: volúmenes puros con cubierta plana y peto; grandes
  ventanales a sur/jardín y huecos pequeños a norte/calle; voladizos de 1,5-2,5 m
  marcando terrazas o el acceso; combina 2-3 materiales (blanco + madera u
  hormigón + antracita); altura por planta 3,0 m entre forjados.
- **Edificio de viviendas**: retícula de pilares cada 5-6 m; planta baja más
  alta (3,5-4 m) para portal/locales; plantas tipo repetidas de 3,0 m; núcleo
  de escalera de ~3×5 m en posición central; balcones o terrazas en fachada
  principal; ático retranqueado con terraza.
- **Composición**: alinea huecos en vertical entre plantas, mantén proporciones
  de ventana coherentes (más alto que ancho en fachadas clásicas, apaisado o de
  suelo a techo en modernas) y evita fachadas ciegas hacia la calle.
- **Interiorismo**: amuebla estancia por estancia, cada una en su capa
  ("Planta 0 - Salón"…), con la espalda de los muebles pegada a las paredes.
  TODA estancia interior debe quedar dentro del perímetro de los muros: usa las
  funciones de estancia completa (dormitorio, salon, bano y cocina_estancia),
  que adosan solas el mobiliario a las paredes, y nunca calcules a mano la
  posición de la cocina.
  Ergonomía: deja 60-70 cm de paso a cada lado de la cama; en el comedor, 60 cm
  de mesa por comensal y 90 cm libres tras las sillas; sofá a 2,5-3,5 m del
  televisor y con mesa de centro a 40 cm; la alfombra debe abarcar al menos las
  patas delanteras del sofá. Color: regla 60-30-10 (60 % base neutra en paredes
  y suelos, 30 % secundario en muebles grandes, 10 % acento en textiles y
  cuadros); combina madera y tela para dar calidez; suelos de parquet en
  estancias y baldosa/marmol en cocinas y baños. Iluminación en tres capas:
  general (lámparas colgantes), de tarea (mesitas, encimera, lectura) y de
  acento; toda estancia con techo necesita sus lámparas o saldrá oscura en los
  renders. Para enseñar un interior, coloca la cámara en una esquina a 1,5 m de
  altura mirando hacia la zona principal. En Revit el mobiliario son familias
  cargadas y en AutoCAD bloques en planta; las luces y cámaras de render solo
  aplican a Blender y SketchUp.

## Fotorrealismo y presentación (Blender)

Cuando el usuario pida un render, una imagen «realista» o enseñar el proyecto,
sigue esta receta en Blender (es la diferencia entre una maqueta y una foto):
0. **Si hay referencia, búscala**: con referencias_buscar (consulta en inglés)
   tú y el usuario veis fotos reales del estilo pedido; elige una con él y úsala
   como objetivo de materiales, luz y encuadre.
1. **Viste la escena**: materiales variados con textura (nunca todo blanco),
   suelos interiores con parquet/mármol, mobiliario visible tras los vidrios,
   y entorno: terreno, árboles, arbustos, setos y, si encaja, piscina.
2. **Enciende la casa**: focos empotrados en retícula (cada 1,2-1,5 m) en cada
   estancia con techo, lámparas de pie y colgantes, focos de jardín ante los
   arbustos. Una casa apagada arruina cualquier render de tarde o noche.
   Con recursos_buscar/recursos_descargar usa texturas PBR reales de Poly Haven
   (material="ph:<id>") en fachadas, suelos y cubierta, y modelos reales para
   el mobiliario visible: es lo que más acerca el render a una fotografía.
3. **Elige la luz**: un hdri("<id>") real de Poly Haven da la luz más creíble;
   sin él, cielo("atardecer") es la más espectacular (interiores
   cálidos brillando tras el vidrio, piscina iluminada); cielo("dia") para
   mostrar volúmenes; cielo("noche") para dramatismo.
4. **Encuadra**: camara() a 1,6-2 m de altura desde una esquina para fachadas
   (lente 30-35); en interiores lente 24 desde una esquina a 1,5 m.
5. **Revisa antes de renderizar**: llama a revisar_escena() y corrige lo que
   señale (cámara, luces o materiales que falten) antes de gastar un render.
6. **Renderiza en dos pasos**: render(calidad="borrador") para comprobar el
   encuadre, corrige lo que se vea mal y termina con render(calidad="alta").
   Si tu modelo admite imágenes, VES cada render que generas (y las fotos de
   referencia): compáralos de verdad y di qué has corregido entre uno y otro.
El render aparece automáticamente como imagen en el chat: no pidas al usuario
que abra archivos ni le des rutas. Solo Blender puede renderizar; si trabaja
en otro programa y quiere renders, ofrécele construir el modelo en Blender.

## Entregar el trabajo en formatos reales

Un render es una imagen, no un entregable: con un PNG no se va a obra ni se
coordina con nadie. Cuando el trabajo esté terminado, ofrécele exportarlo con la
herramienta `..._exportar` del programa en el que estéis trabajando, y hazlo
también sin que lo pida si ves que el proyecto ya está listo:
- **IFC** (Revit, SketchUp Pro) para BIM y coordinación con otros técnicos.
- **DWG** para estudios y constructoras; **DXF** cuando no sabes qué programa
  usará quien lo reciba, porque lo abre cualquier CAD.
- **PDF** (Revit, AutoCAD) para imprimir o enviar a cliente.
- **GLB** (Blender) para enseñar el modelo 3D o verlo en el navegador.
Exporta al final, con el modelo ya acabado: el archivo es una copia congelada y
no se actualiza sola. El archivo aparece en el chat con su botón de descarga, así
que no le des rutas ni le pidas que busque carpetas. Si te piden un formato que
el programa abierto no sabe escribir (IFC o DWG desde Blender, por ejemplo),
dilo claramente y explícale en qué programa sí se puede.

## Imágenes que adjunta el usuario

El usuario puede adjuntar fotos o vídeos con el botón de clip junto a la caja de
texto (de un vídeo recibes varios fotogramas repartidos en el tiempo). Puedes
verlos. Úsalos así:
- Si te hace una pregunta sobre una imagen (un plano, una fachada, un boceto, una
  foto de una estancia), analízala y respóndele con tu criterio de arquitecto:
  qué estilo es, qué materiales ves, qué medidas aproximadas, qué mejorarías, etc.
- Si te pide un render «parecido», «igual», «como esta foto» o «inspirado» en la
  imagen, tu objetivo es acercarte lo máximo posible a esa referencia:
  1. Antes de tocar Blender, obsérvala y fíjate en: volumen y tipología del
     edificio, número de plantas y forma de la cubierta; materiales y colores de
     fachada y su textura (liso, madera, piedra, hormigón, ladrillo…); proporción
     y ritmo de ventanas y puertas; iluminación (hora del día, dirección y dureza
     de la luz, cielo despejado o nublado); punto de vista de la cámara (altura,
     distancia, frontal o en escorzo, gran angular o tele); y el entorno
     (vegetación, agua, pavimento, contexto).
  2. Reconstruye esos rasgos con el kit: elige los presets de material más
     parecidos a lo que ves, replica la cubierta y el ritmo de huecos, ajusta
     cielo() a la misma hora del día y coloca la camara() en un encuadre
     equivalente al de la foto.
  3. Con un vídeo aprovecha los distintos fotogramas para entender el volumen
     completo girando alrededor del edificio.
  4. Renderiza en borrador, compáralo con la referencia, corrige lo que más se
     aleje (materiales, hora de luz, encuadre) y termina en alta.
  Di siempre con qué presets y qué hora de luz te has aproximado, y en qué se
  diferenciará del original: no puedes copiar un edificio real exacto, pero sí
  reproducir su lenguaje, materiales, luz y encuadre.

## Herramientas

Puedes controlar programas de arquitectura mediante herramientas. Programas
conectados ahora mismo: {programas}.

Normas de trabajo:
- Antes de modificar un modelo o dibujo, consulta su estado con la herramienta
  de información correspondiente.
- Haz los cambios en pasos pequeños y verifica el resultado tras cada paso.
- Usa unidades métricas (metros o milímetros según el programa) salvo que el
  usuario indique otra cosa.
- Si una herramienta devuelve ERROR, lee el mensaje, corrige el código y
  reintenta (máximo 3 intentos); si no lo consigues, explica el problema en
  lenguaje sencillo.
- Si el usuario pide algo de un programa que no está conectado, dile con qué
  programas puedes trabajar ahora y cómo conectar el que falta (hay un botón
  de ayuda junto a cada programa en la barra lateral).
- Antes de dar por terminado un proyecto en Blender, pasa el control de calidad
  (revisar_escena) y corrige lo que falte; en otros programas, consulta el estado
  y comprueba que lo construido coincide con el plan.
- Al terminar, resume en 2-3 frases qué has hecho, sin tecnicismos.
- Nunca borres trabajo del usuario sin confirmárselo antes."""


# Solo se añade cuando la conversación trae un plano (ver _con_planos): son
# ~2 000 caracteres de receta más ~6 000 de herramientas, un 20 % de cada
# petición que en el resto de conversaciones solo encarecería y saturaría el
# contexto de los modelos gratuitos y locales.
SECCION_PLANOS = """## Reconstruir un plano adjunto (imagen, PDF o DXF)

Cuando el usuario adjunte un plano y pida modelarlo, dibujarlo o «pasarlo» a un
programa (una casa 3D en Blender o SketchUp, la planta en AutoCAD, el modelo BIM
en Revit), el objetivo es la máxima fidelidad: mismas medidas, mismos huecos,
mismas estancias. No lo redibujes a mano con las herramientas del programa:
1. **Lee el plano como arquitecto**: escala gráfica o numérica, cotas generales
   y parciales, espesores de muro, puertas y ventanas (y hacia dónde abren),
   nombre y superficie (m²) de cada estancia, número de plantas y alturas.
2. **Mide la geometría**: plano_detectar_muros en imágenes y PDF (te da los muros
   al píxel), plano_leer_dxf en DXF (geometría exacta en metros). Contrasta lo
   detectado con lo que ves: descarta lo que no sea muro y añade lo que falte.
3. **Escribe el plano neutro** de plano_reconstruir con esos muros, calibrando
   con 2-3 cotas largas que leas en el plano (en px es obligatorio), cada hueco en
   su sitio y cada estancia con el punto de su rótulo y su superficie.
4. **Valida primero** (solo_validar=true) y corrige lo que marque el informe:
   cotas que no cuadran, estancias que no cierran, superficies con ✘ o huecos sin
   declarar. Repite hasta que esté limpio o hasta que solo queden dudas reales.
5. **Construye** en el programa conectado (solo_validar=false) y comprueba el
   resultado con su herramienta de información.
6. **Resume**: qué has reconstruido, la desviación de superficies frente al
   plano, y todo lo que asumiste porque el plano no lo dice (alturas, antepechos,
   alto de puertas, espesores ilegibles). Pregunta solo lo que cambie el
   resultado, como cuántas plantas hay si el plano es ambiguo.
Después puedes completar el modelo con el kit habitual (cubierta, mobiliario,
materiales, render): la reconstrucción deja cada planta en su capa
«Plano - <planta>» y su contorno en el informe para la cubierta."""

# Modo ligero: para modelos pequeños que corren en el ordenador del usuario
# (la IA incluida). Las instrucciones completas ocupan ~6 000 tokens: en un
# modelo de 4B con 16k de contexto se comen la conversación y además lo
# confunden. Esto es lo imprescindible, dicho de forma directa.
SISTEMA_LIGERO = """Eres BuildAI, asistente de arquitectura. Responde SIEMPRE en español, claro y
breve, para arquitectos que no programan (no les pidas que escriban código).

Programas conectados ahora: {programas}.

Cómo trabajar:
1. Antes de cambiar un modelo, consulta su estado con la herramienta de información.
2. Haz cambios en pasos pequeños con la herramienta de ejecución del programa y
   comprueba el resultado. Usa SIEMPRE las funciones del kit que describe la
   herramienta (muro, forjado, cubierta_plana…), no geometría escrita a mano.
3. Si una herramienta devuelve ERROR, lee el mensaje, corrige y reintenta (máximo 3 veces).
   NUNCA digas que has hecho algo que no hayas ejecutado con una herramienta y cuyo
   resultado (✔) no hayas visto: primero ejecutas, luego lo cuentas.
4. Al terminar, resume en 2-3 frases lo hecho y las medidas que supusiste.
5. Nunca borres trabajo del usuario sin preguntar.

Medidas por defecto (dilo si las usas): muro exterior 0,20 m de espesor y 2,70 m de
alto; tabique 0,10 m; puerta 0,80 × 2,05 m; ventana 1,20 × 1,20 m con antepecho
0,90 m; altura entre plantas 3,0 m. Unidades: metros en Blender y Revit; en
AutoCAD las del dibujo (normalmente milímetros); en SketchUp con sufijo .m.

Una casa: primero muros con sus huecos, luego forjado y cubierta; amuebla con
dormitorio(), salon(), bano() y cocina_estancia(). Para un render en Blender:
cielo("atardecer"), camara(...) y render(calidad="borrador").
Si el usuario pide algo de un programa que no está conectado, díselo y explícale
que lo abra (hay un botón de ayuda junto a cada programa)."""

SECCION_PLANOS_LIGERA = """Si el usuario adjunta un plano y pide modelarlo: 1) plano_detectar_muros (imagen o
PDF) o plano_leer_dxf (DXF); 2) plano_reconstruir con solo_validar=true usando esos muros,
calibrando con una cota del plano; 3) corrige los avisos; 4) plano_reconstruir con
solo_validar=false en el programa conectado."""

# Presupuesto de la conversación en modo ligero (caracteres ≈ 3,5 por token):
# el contexto del motor menos instrucciones, herramientas y la respuesta.
PRESUPUESTO_LIGERO = 26000

_MENCIONA_PLANO = re.compile(r"\bplan[oa]s?\b|\bdxf\b|\bpdf\b|\bcroquis\b|\bdwg\b", re.IGNORECASE)


def _con_planos(historial: list, mensaje: str, adjuntos=None) -> bool:
    """¿Hacen falta las herramientas de planos en este turno?

    Sí si hay adjuntos ahora o en cualquier turno anterior (el usuario puede
    pedir «ahora pásalo a AutoCAD» un turno después de adjuntarlo), o si el
    mensaje habla de planos.
    """
    if adjuntos or any(m.get("tipo") == "usuario" and m.get("adjuntos") for m in historial):
        return True
    return bool(_MENCIONA_PLANO.search(mensaje or ""))


def _sistema(conectados: list, consulta: str = "", con_planos: bool = False, ligero: bool = False) -> str:
    if conectados:
        nombres = ", ".join(c.nombre for c in conectados)
    else:
        nombres = "ninguno (puedes conversar y aconsejar, pero no tocar modelos)"
    if ligero:
        base = SISTEMA_LIGERO.format(programas=nombres)
        if con_planos:
            base += "\n\n" + SECCION_PLANOS_LIGERA
        return base
    base = SISTEMA_BASE.format(programas=nombres)
    if con_planos:
        base += "\n\n" + SECCION_PLANOS
    aprendizajes = memoria.perfil_texto()
    if aprendizajes:
        base += "\n\n" + aprendizajes
    # Recuperación de contexto de conocimiento (normas, técnicas) por consulta.
    programas_ids = [c.id for c in conectados]
    bloque_conocimiento = conocimiento.bloque_para_sistema(consulta, programas_ids)
    if bloque_conocimiento:
        base += "\n\n" + bloque_conocimiento
    return base


def _herramientas(conectados: list, con_planos: bool = False, ligero: bool = False) -> list:
    # Las de planos no dependen de ningún programa abierto: leer y validar un
    # plano no lo necesita (construirlo sí, y la herramienta lo comprueba).
    lista = planos.herramientas() if con_planos else []
    # Las de recursos de render solo sirven si Blender puede usarlos. En modo
    # ligero se omiten: son flujos de varios pasos que un modelo pequeño
    # aprovecha mal, y ocupan ~650 tokens de un contexto que no sobra.
    if not ligero:
        lista += recursos.herramientas(con_blender=any(c.id == "blender" for c in conectados))
    for conector in conectados:
        # En modo ligero, la versión compacta de las herramientas si el conector
        # la tiene (la del kit de Blender ocupa ~10 000 caracteres completa).
        if ligero and hasattr(conector, "herramientas_ligeras"):
            lista.extend(conector.herramientas_ligeras())
        else:
            lista.extend(conector.herramientas())
    return lista


# Verbos con los que el usuario pide cambiar un modelo (no solo preguntar).
_PIDE_ACCION = re.compile(
    r"\b(crea|cre[aá]me|haz|hazme|construye|dibuja|a[ñn]ade|agrega|pon|coloca|borra|elimina|"
    r"modela|amuebla|levanta|dise[ñn]a|cambia|mueve|exporta|renderiza|reconstruye|genera)\b",
    re.IGNORECASE,
)


def _ejecuto_algo(historial: list) -> bool:
    """¿Se ha usado en el turno actual alguna herramienta que cambie un modelo?"""
    ultimo = max((i for i, m in enumerate(historial) if m["tipo"] == "usuario" and not m.get("interno")),
                 default=-1)
    for m in historial[ultimo + 1:]:
        for llamada in (m.get("llamadas") or []) if m["tipo"] == "asistente" else []:
            nombre = llamada.nombre
            if "ejecutar" in nombre or nombre.endswith(("_comando", "_exportar")) or nombre == "plano_reconstruir":
                return True
    return False


def _ajustar_a_contexto(vista: list, presupuesto: int) -> list:
    """Quita los turnos más antiguos de la vista hasta que quepa en `presupuesto`
    caracteres. Corta siempre al empezar un turno de usuario, como
    _recortar_historial, para no separar una llamada de su resultado."""
    def tamano(m):
        return len(m.get("texto") or "") + len(m.get("contenido") or "") + 200 * len(m.get("llamadas") or [])

    while sum(tamano(m) for m in vista) > presupuesto:
        corte = next((i for i in range(1, len(vista)) if vista[i]["tipo"] == "usuario"), None)
        if corte is None:
            break
        vista = vista[corte:]
    return vista


def _recortar_historial(historial: list) -> None:
    """Olvida los turnos más antiguos cuando la conversación crece demasiado.

    Se corta siempre al inicio de un turno de usuario: partir un turno dejaría
    llamadas a herramientas sin su resultado y el proveedor rechazaría la petición.
    """
    while len(historial) > MAX_HISTORIAL:
        corte = next(
            (i for i in range(1, len(historial)) if historial[i]["tipo"] == "usuario"),
            None,
        )
        if corte is None:
            break
        del historial[:corte]


def _comprimir_resultados(historial: list, recientes: int = ENTRADAS_SIN_COMPRIMIR) -> None:
    """Recorta resultados de herramienta antiguos para no agotar el contexto.

    Se conservan íntegras las últimas entradas (las que el modelo necesita para
    el paso actual); lo demás ya fue procesado y basta con un extracto.
    """
    for m in historial[:-recientes]:
        if m["tipo"] == "resultado" and len(m["contenido"]) > RESULTADO_ANTIGUO_MAX:
            # Las líneas RENDER_GUARDADO se conservan siempre: la interfaz las
            # necesita para volver a mostrar las imágenes al reabrir la sesión.
            lineas = m["contenido"].splitlines()
            marcas = [l for l in lineas if l.startswith(_MARCA_RENDER)]
            cuerpo = "\n".join(l for l in lineas if not l.startswith(_MARCA_RENDER))
            m["contenido"] = (
                cuerpo[:RESULTADO_ANTIGUO_MAX]
                + "\n… (resultado antiguo recortado; consulta de nuevo el programa si necesitas el detalle)"
                + ("\n" + "\n".join(marcas) if marcas else "")
            )


_cache_imagenes: dict = {}


def _imagen_para_modelo(nombre: str):
    """{media_type, datos} de una imagen de la carpeta de renders, reducida a
    LADO_IMAGEN_HERRAMIENTA px en JPEG (un render de 1920 px en PNG pesaría
    varios MB por petición). Se cachea por nombre y fecha del archivo."""
    import base64
    import io

    ruta = CARPETA_RENDERS / nombre
    try:
        clave = (nombre, ruta.stat().st_mtime)
    except OSError:
        return None
    if clave not in _cache_imagenes:
        try:
            from PIL import Image

            imagen = Image.open(ruta).convert("RGB")
            imagen.thumbnail((LADO_IMAGEN_HERRAMIENTA, LADO_IMAGEN_HERRAMIENTA))
            salida = io.BytesIO()
            imagen.save(salida, "JPEG", quality=82)
        except Exception:
            return None
        if len(_cache_imagenes) > 32:
            _cache_imagenes.clear()
        _cache_imagenes[clave] = {"media_type": "image/jpeg", "datos": base64.b64encode(salida.getvalue()).decode("ascii")}
    return _cache_imagenes[clave]


def _historial_para_modelo(historial: list, con_imagenes: bool = True) -> list:
    """Vista del historial para enviar al modelo: omite las imágenes de turnos
    ya cerrados.

    El modelo solo necesita ver los adjuntos del turno en curso (mientras
    construye "un render como esta foto"); re-subirlos en cada paso de los turnos
    siguientes solo dispara coste y latencia. Las imágenes siguen intactas en el
    `historial` original, que es lo que consumen la interfaz y la sesión guardada.
    """
    # Los recordatorios internos de BuildAI no cuentan como mensaje del usuario:
    # si contaran, las imágenes adjuntas del turno dejarían de enviarse.
    ultimo_usuario = max(
        (i for i, m in enumerate(historial) if m["tipo"] == "usuario" and not m.get("interno")),
        default=-1,
    )
    vista = []
    for i, m in enumerate(historial):
        if m["tipo"] == "usuario" and m.get("adjuntos"):
            if i != ultimo_usuario:
                m = {k: v for k, v in m.items() if k != "adjuntos"}
            else:
                # Numerar los adjuntos (y decir cuáles son páginas de PDF o DXF)
                # deja al modelo citarlos en las herramientas de planos. Solo en
                # la vista: el texto guardado del usuario no se toca.
                nota = planos.nota_adjuntos(m["adjuntos"])
                m = dict(m, texto=f"{m.get('texto') or ''}\n\n{nota}".strip())
                if not con_imagenes:
                    # Un modelo sin visión rechaza la petición ENTERA si lleva
                    # una imagen (Ollama: 500 "image input is not supported"),
                    # y eso se reintentaba como "saturado". Se quitan las
                    # imágenes y se le dice qué hay: las herramientas de planos
                    # siguen leyendo los adjuntos desde el historial.
                    m = {k: v for k, v in m.items() if k != "adjuntos"}
                    m["texto"] += (
                        "\n[Tu modelo no puede ver imágenes: no describas lo que no ves. Si es un "
                        "plano, usa las herramientas de planos (miden la imagen por ti); si no, "
                        "pide al usuario que lo explique con palabras o que use un modelo con visión.]"
                    )
        vista.append(m)

    # Que el modelo VEA lo que producen sus herramientas (su render, una foto de
    # referencia, el control de un plano) es lo que le permite comparar y
    # corregir. Solo las del turno en curso, las más recientes primero.
    if con_imagenes:
        restantes = MAX_IMAGENES_HERRAMIENTA
        for i in range(len(vista) - 1, ultimo_usuario, -1):
            m = vista[i]
            if restantes <= 0 or m["tipo"] != "resultado" or not m.get("imagenes"):
                continue
            nombres = m["imagenes"][-restantes:]
            datos = [d for d in (_imagen_para_modelo(n) for n in nombres) if d]
            if datos:
                vista[i] = dict(m, imagenes_datos=datos)
                restantes -= len(datos)
    return vista


def ejecutar_turno(historial: list, mensaje_usuario: str, emitir, cancelado=None, adjuntos=None) -> None:
    """Procesa un turno completo del usuario.

    `emitir(evento: dict)` recibe eventos:
      {"tipo": "estado", "texto"}         — qué está haciendo el agente
      {"tipo": "herramienta", "programa", "nombre", "detalle"}
      {"tipo": "respuesta", "texto"}      — texto final del asistente
      {"tipo": "error", "texto"}
    `cancelado()` (opcional) devuelve True si el usuario pidió detener la tarea;
    se comprueba entre pasos para no dejar herramientas sin resultado.
    El historial se modifica in situ (formato neutro de providers.base).
    """
    configuracion = cfg.cargar()
    try:
        proveedor = crear_proveedor(configuracion)
    except ErrorProveedor as exc:
        emitir({"tipo": "error", "texto": str(exc)})
        return
    # El proveedor avisa por aquí de esperas y reintentos (429, cortes…)
    proveedor.notificar = lambda texto: emitir({"tipo": "estado", "texto": texto})

    conectados = [c for c in CONECTORES if c.disponible()]
    con_planos = _con_planos(historial, mensaje_usuario, adjuntos)
    ligero = getattr(proveedor, "ligero", False)
    sistema = _sistema(conectados, mensaje_usuario, con_planos=con_planos, ligero=ligero)
    herramientas = _herramientas(conectados, con_planos=con_planos, ligero=ligero)

    entrada = {"tipo": "usuario", "texto": mensaje_usuario}
    if adjuntos:
        entrada["adjuntos"] = adjuntos
    historial.append(entrada)
    _recortar_historial(historial)

    recordatorios = 0
    for _ in range(MAX_PASOS):
        if cancelado and cancelado():
            emitir({"tipo": "respuesta", "texto": "He detenido la tarea donde me lo pediste. Los pasos ya completados se mantienen."})
            return
        # En modo ligero se comprime antes: 16k de contexto no dan para 24 entradas enteras.
        _comprimir_resultados(historial, 8 if ligero else ENTRADAS_SIN_COMPRIMIR)
        emitir({"tipo": "estado", "texto": "Pensando…"})
        try:
            vista = _historial_para_modelo(historial, getattr(proveedor, "ve_imagenes", True))
            presupuesto = getattr(proveedor, "presupuesto", PRESUPUESTO_LIGERO)
            for _intento in range(3):
                if ligero:
                    vista = _ajustar_a_contexto(vista, presupuesto)
                try:
                    respuesta = proveedor.conversar(sistema, vista, herramientas)
                    break
                except ErrorContextoExcedido:
                    # Un modelo local con poco contexto: se reintenta con la
                    # mitad de conversación antes de rendirse.
                    if not ligero or presupuesto < 1500:
                        raise
                    presupuesto //= 2
                    emitir({"tipo": "estado", "texto": "Resumiendo la conversación para que quepa en la IA local…"})
            else:
                raise ErrorContextoExcedido("La petición no cabe en la memoria del modelo local ni recortada.")
        except ErrorProveedor as exc:
            emitir({"tipo": "error", "texto": str(exc)})
            return
        except Exception as exc:  # error inesperado: no tumbar el servidor
            emitir({"tipo": "error", "texto": f"Error inesperado del proveedor: {exc}"})
            return

        historial.append(
            {
                "tipo": "asistente",
                "texto": respuesta.texto,
                "llamadas": respuesta.llamadas,
                "_raw": respuesta.raw,
            }
        )

        if not respuesta.llamadas:
            # Salvaguarda para modelos pequeños: a veces "cuentan" que han
            # construido algo sin haber llamado a ninguna herramienta. Si el
            # usuario pidió un cambio y no se ejecutó nada, no se da por buena:
            # se le recuerda que lo haga de verdad (como mucho dos veces).
            if (ligero and conectados and recordatorios < 2 and _PIDE_ACCION.search(mensaje_usuario)
                    and not _ejecuto_algo(historial)):
                recordatorios += 1
                historial.append({
                    "tipo": "usuario",
                    "interno": True,  # no es del usuario: la interfaz no lo pinta
                    "texto": ("[BuildAI] Todavía no has ejecutado nada: no lo des por hecho. Usa ahora "
                              "la herramienta de ejecución del programa para hacerlo de verdad, paso a "
                              "paso, y después resume lo que salió bien."),
                })
                emitir({"tipo": "estado", "texto": "Comprobando que la IA local lo haga de verdad…"})
                continue
            emitir({"tipo": "respuesta", "texto": respuesta.texto or "(sin respuesta)"})
            return

        if respuesta.texto:
            # Comentario intermedio del modelo mientras trabaja
            emitir({"tipo": "respuesta", "texto": respuesta.texto})

        for llamada in respuesta.llamadas:
            interna = _INTERNAS.get(llamada.nombre)
            encontrada = None if interna else buscar_herramienta(llamada.nombre)
            if interna:
                programa = _PROGRAMA_INTERNA[interna]
                argumentos = llamada.argumentos
                emitir({
                    "tipo": "herramienta",
                    "programa": programa,
                    "nombre": llamada.nombre,
                    "detalle": str(argumentos.get("programa") or argumentos.get("consulta")
                                   or argumentos.get("id") or "")[:400],
                })
                try:
                    resultado = interna.ejecutar(llamada.nombre, argumentos, historial, CONECTORES)
                except Exception as exc:
                    resultado = f"ERROR inesperado en {llamada.nombre}: {exc}"
                for archivo in renders_en_resultado(resultado):
                    emitir({"tipo": "render", "archivo": archivo})
            elif encontrada is None:
                resultado = f"ERROR: la herramienta '{llamada.nombre}' no existe."
                programa = "?"
            else:
                conector, _ = encontrada
                programa = conector.nombre
                emitir(
                    {
                        "tipo": "herramienta",
                        "programa": programa,
                        "nombre": llamada.nombre,
                        "detalle": str(llamada.argumentos.get("codigo") or llamada.argumentos.get("orden") or "")[:400],
                    }
                )
                try:
                    resultado = conector.ejecutar(llamada.nombre, llamada.argumentos)
                except Exception as exc:
                    resultado = f"ERROR inesperado ejecutando la herramienta: {exc}"
                for archivo in renders_en_resultado(resultado):
                    emitir({"tipo": "render", "archivo": archivo})
                for entregable in entregables_en_resultado(resultado):
                    emitir(dict(entregable, tipo="entregable"))
            limite = 3000 if ligero else MAX_RESULTADO
            if len(resultado) > limite:
                marcas = [
                    l for l in resultado.splitlines()
                    if l.startswith((_MARCA_RENDER, MARCA_ENTREGABLE))
                ]
                resultado = (
                    resultado[:limite]
                    + "\n… (salida recortada por ser demasiado larga)"
                )
                for marca in marcas:
                    if marca not in resultado:
                        resultado += "\n" + marca
            entrada_resultado = {
                "tipo": "resultado",
                "id": llamada.id,
                "nombre": llamada.nombre,
                "contenido": resultado,
            }
            # Solo el nombre del archivo: la sesión guardada no engorda con
            # base64 y la imagen se carga (reducida) al preparar la petición.
            imagenes = renders_en_resultado(resultado)
            if imagenes:
                entrada_resultado["imagenes"] = imagenes
            historial.append(entrada_resultado)

    # Límite de pasos alcanzado: no es un fallo, es una pausa de seguridad.
    # El historial queda completo (cada herramienta con su resultado), así que
    # el usuario puede reanudar la tarea exactamente donde quedó.
    aviso = (
        f"He completado {MAX_PASOS} pasos y la tarea aún no ha terminado, "
        "así que hago una pausa de seguridad. Todo lo avanzado se conserva: "
        "escribe «continúa» y sigo justo donde lo dejé."
    )
    historial.append({"tipo": "asistente", "texto": aviso, "llamadas": [], "_raw": None})
    emitir({"tipo": "respuesta", "texto": aviso})
