"""Conector con Blender a través del add-on BuildAI (socket TCP local)."""

import json
import socket
from pathlib import Path

from .base import Conector, recortar

PUERTO_BLENDER = 8601

# Kit de construcción paramétrico: se antepone a cada ejecución para que el
# modelo disponga de funciones de arquitectura fiables en vez de escribir
# geometría bpy a mano (clave para que modelos gratuitos hagan proyectos grandes).
KIT_FUENTE = (Path(__file__).parent / "blender_kit.py").read_text(encoding="utf-8")

REFERENCIA_KIT = """Antes de tu código se carga automáticamente un KIT de construcción con estas \
funciones (unidades en metros, eje Z hacia arriba, puntos (x, y) en planta):

- muro(inicio, fin, alto=2.7, espesor=0.2, nivel=0.0, huecos=None, material="blanco", capa=None)
  Muro recto entre dos puntos (x, y). `nivel` es la cota de su base. Cada hueco es
  {"tipo": "ventana"|"puerta"|"ventanal"|"paso", "a": distancia desde el inicio, "ancho": m}
  (opcionales "alto" y "antepecho"); ventanas y puertas añaden solas marco, cristal u hoja.
- ventanal(inicio, fin, alto=2.5, nivel=0.0, division=1.2, capa=None)
  Muro cortina de vidrio de suelo a techo con montantes (fachadas modernas).
- forjado(contorno, nivel=0.0, espesor=0.3, material="hormigon", capa=None)
  Losa horizontal; `contorno` es la lista de (x, y) y `nivel` la cota del suelo terminado.
- cubierta_plana(contorno, nivel, espesor=0.3, peto=0.6, material="hormigon", capa=None)
  Losa de azotea + peto perimetral (casas modernas, edificios).
- cubierta_dos_aguas(origen, ancho, fondo, nivel, pendiente=30, alero=0.5, eje="x", material="teja")
  Cubierta inclinada sobre el rectángulo con esquina `origen`; cumbrera según `eje`.
- escalera(origen, direccion="+x", ancho=1.0, alto_total=2.7, nivel=0.0)
  Tramo recto; calcula peldaños e informa del desarrollo en planta. direccion: "+x","-x","+y","-y".
- barandilla(inicio, fin, nivel=0.0, alto=1.0) — postes, pasamanos y vidrio.
- rejilla_pilares(origen, num_x, num_y, sep_x, sep_y, alto, nivel=0.0, lado=0.3)
  Retícula estructural de pilares (edificios de varias plantas).
- caja(nombre, origen, dimensiones, material, capa) — volumen genérico (jardineras, muebles a medida…).
- terreno(ancho=60, fondo=60, centro=(0,0), material="cesped", ondulacion=0.0) — suelo en
  cota 0; ondulacion (m) le da relieve natural suave (prueba 0.3-0.8) para parcelas con
  desniveles. Suelos de exterior: material="cesped", "tierra", "arena", "gravilla" o "pavimento".
- material(nombre, color=(r,g,b), rugosidad, metalico, transparente, textura, emision) — crea o
  reutiliza materiales. Presets con acabado, textura y relieve listos: blanco, crema, gris_claro,
  hormigon, antracita, negro_mate, madera, madera_clara, parquet, marmol, ladrillo, baldosa,
  ceramica, tela_gris, tela_beige, tela_azul, hoja, teja, piedra, piedra_muro (mampostería vista),
  cesped, tierra, tierra_seca, arena, gravilla, pavimento, acero, metal_negro, espejo, vidrio,
  agua, baldosa_piscina. Para suelos
  interiores usa material="parquet", "marmol" o "baldosa" en el forjado; `emision` (vatios) crea
  superficies que brillan con luz propia.
- coleccion(nombre) y el parámetro capa="..." organizan los objetos por plantas/capas.
- limpiar_todo() — vacía la escena (solo con permiso del usuario).

FOTORREALISMO Y RENDER — así se consiguen imágenes de nivel profesional:
- cielo(momento="dia", azimut=200) — cielo físico realista + sol sincronizado. Momentos:
  "amanecer", "dia", "tarde", "atardecer" (hora dorada/azul: LA más fotogénica con las luces
  interiores encendidas), "anochecer", "noche". Sustituye al cielo anterior sin duplicar.
- sol(elevacion=35, azimut=200, fuerza=3.0) — alternativa rápida con cielo plano.
- camara(objetivo, distancia=20, azimut=225, altura=6, lente=50, apertura=None) — cámara activa
  mirando al objetivo; sustituye a la anterior. Fachadas: altura 1.6-2, lente 30-35, desde una
  esquina (azimut 225-250). Interiores: lente=24, altura=1.5, distancia 3-5, apertura=2.8.
- render(calidad="media") — ¡la herramienta estrella! Prepara Cycles (GPU, denoise, tono AgX,
  halos de luz) y guarda un render fotorrealista QUE EL USUARIO VE EN EL CHAT automáticamente.
  calidad: "borrador" (~30 s, para comprobar encuadre), "media" (~1-2 min), "alta" (~3-5 min).
  Receta para un render espectacular: materiales variados + vegetación + TODAS las luces
  interiores encendidas (focos y lámparas en cada estancia con techo) + cielo("atardecer") +
  camara() + render(). Haz siempre un "borrador" primero, corrige el encuadre y repite en "alta".
- piscina(origen, ancho=8, fondo=4, profundidad=1.5, luces=2) — piscina enterrada completa: vaso
  alicatado, agua realista, borde y luces sumergidas; recorta sola el hueco en el "Terreno".
- arbol(centro, alto=6, tipo="frondoso"|"cipres", semilla=None), arbusto(centro, alto=0.7),
  seto(inicio, fin, alto=1.2) — vegetación; sin ella los exteriores parecen maquetas. Cada
  árbol/arbusto varía solo su forma y su verde, así que reparte varios en posiciones distintas
  para un jardín o bosque creíble.
- foco_empotrado(posicion, altura_techo=2.7, nivel=...) — downlight de techo (en retícula cada
  1,2-1,5 m en salones/cocinas modernos); imprescindibles para renders de atardecer/noche.
- foco_jardin(posicion) — baliza que baña de luz cálida arbustos y fachadas desde abajo.
- tumbona(origen), barbacoa(centro) — exterior (mesas de terraza: comedor(..., material="madera")).
- palmera(centro, alto=7) — árbol tropical/mediterráneo, para variar la vegetación.

FACHADA, PARCELA Y PAISAJISMO — elementos que separan una maqueta de un proyecto acabado:
- celosia(inicio, fin, alto=2.5, orientacion="vertical"|"horizontal") — lamas de parasol delante
  de ventanales, en porches o como pantalla; da sombra, ritmo y textura a la fachada.
- pergola(origen, ancho=4, fondo=3, altura=2.4) — pérgola de vigas sobre 4 pilares (terrazas,
  porches, accesos). caja(...) sirve para voladizos, aleros y jardineras a medida.
- valla(inicio, fin, alto=1.6, tipo="tablas"|"postes") — cierra la parcela; camino(inicio, fin,
  ancho=1.2, material="pavimento") traza accesos y senderos de jardín.
- farola(posicion, alto=4) — farola con luz cálida para accesos y calles (enciende de noche).
- coche(origen, rotacion=0) — coche aparcado para dar escala y realismo al exterior.
- revisar_escena() — CONTROL DE CALIDAD: avisa de cámara/luz/materiales que falten. Llámala antes
  de render() y antes de dar por terminado un proyecto, y corrige lo que señale.

ESTANCIAS COMPLETAS — la forma RECOMENDADA de amueblar: distribuyen una estancia rectangular
entera con reglas de interiorismo (piezas centradas y adosadas a la pared, pasos ≥ 0,7 m,
decoración y luz incluidas). `origen` es la esquina INTERIOR suroeste de la estancia (cara vista
de los muros, no su eje), `ancho` va en X, `fondo` en Y, y las paredes se llaman "S" (la de y
mínima), "N", "E", "O". Elige para la pieza principal una pared sin puertas ni ventanas:
- dormitorio(origen, ancho, fondo, pared_cama="S", ropa="tela_azul") — cama centrada + mesitas +
  armario + alfombra + cuadro + lámpara. Camas: usa ropa distinta en cada dormitorio.
- salon(origen, ancho, fondo, pared_sofa="S") — sofá + alfombra + mesa de centro + mueble con
  televisor enfrente + sillón + lámparas + planta + cuadro.
- bano(origen, ancho, fondo, pared_aparatos="S", con_ducha=True) — ducha en esquina + inodoro +
  lavabo con espejo + foco de techo.
Tras llamarlas puedes añadir o mover piezas sueltas. Para cocinas usa cocina(...) y comedor(...).

MOBILIARIO SUELTO — en todos los muebles `origen`/`posicion` es la esquina izquierda de su parte
TRASERA (la que se apoya en la pared) y `rotacion` gira en grados sobre ese punto. Guía para
adosar un mueble de ancho w a cada pared de una estancia [x0..x1] × [y0..y1] (¡ojo: con 180 y 270
el mueble crece hacia atrás desde su origen!):
- pared SUR  (mira a +Y): rotacion=0,   origen=(x, y0)  → ocupa de x a x+w
- pared ESTE (mira a -X): rotacion=90,  origen=(x1, y)  → ocupa de y a y+w
- pared NORTE(mira a -Y): rotacion=180, origen=(x, y1)  → ocupa de x-w a x
- pared OESTE(mira a +X): rotacion=270, origen=(x0, y)  → ocupa de y-w a y
Reglas de distribución: muebles grandes SIEMPRE adosados a una pared (jamás flotando ni girados
al azar), deja ≥ 0,7 m de paso, no tapes puertas ni ventanas, televisor enfrente del sofá y
alfombra bajo la zona de estar. Todos aceptan nivel=0.0 y capa=None:
- cama(origen, ancho=1.5, largo=2.0, ropa="tela_azul") — con cabecero, colchón, almohadas y colcha.
- mesita_noche(origen), armario(origen, ancho=2.0, alto=2.2), estanteria(origen, baldas=4)
- sofa(origen, plazas=3, tela="tela_gris"), sillon(origen), alfombra(origen, ancho=2.5, fondo=1.8)
- mesa(origen, ancho=1.6, fondo=0.9, alto=0.75; con alto=0.4 es mesa de centro), silla(origen)
- comedor(origen, comensales=6) — mesa CON las sillas ya colocadas alrededor.
- cocina(origen, largo=3.0, con_altos=True) — bancada completa con encimera, placa y fregadero.
- lavabo(origen, ancho=0.8), inodoro(origen), ducha(origen, 0.9, 0.9), banera(origen)
- television(posicion, pulgadas=55, altura=1.0), cuadro(posicion, ancho, alto, color=(r,g,b)),
  espejo_pared(posicion), planta_decorativa(centro, alto=1.3)
Iluminación interior (imprescindible en estancias con techo, si no salen negras en el render):
- lampara_colgante(posicion, altura_techo=2.7, nivel=...) — sobre mesas y zonas de estar.
- lampara_pie(centro, nivel=...) — junto a sofás. luz_interior((x,y,z), fuerza=40) — luz genérica.

Usa SIEMPRE estas funciones para construir; recurre a `bpy` directo solo para lo que el kit
no cubre (modificadores, renders, formas curvas…). Construye cada planta con su
capa="Planta 0", capa="Planta 1"… y niveles acumulados (p. ej. planta 1 en nivel=3.0)."""


def _enviar(peticion: dict, timeout: float = 60.0) -> dict:
    with socket.create_connection(("127.0.0.1", PUERTO_BLENDER), timeout=timeout) as s:
        s.sendall((json.dumps(peticion) + "\n").encode("utf-8"))
        datos = b""
        while not datos.endswith(b"\n"):
            trozo = s.recv(65536)
            if not trozo:
                break
            datos += trozo
    return json.loads(datos.decode("utf-8"))


class ConectorBlender(Conector):
    id = "blender"
    nombre = "Blender"
    icono = "blender"
    ayuda = (
        "1. Pulsa «Conectar automáticamente» aquí abajo: BuildAI instala el "
        "puente en todas tus versiones de Blender (2.80 o superior).\n"
        "2. Abre (o reinicia) Blender. No hay que activar nada: el puente "
        "arranca solo y el punto se pondrá verde en unos segundos.\n"
        "\n"
        "Manual (alternativa): Edit → Preferences → Add-ons → Install… → elige "
        "addons\\blender\\buildai_blender.py y activa la casilla 'BuildAI Bridge'."
    )

    def disponible(self) -> bool:
        try:
            return _enviar({"comando": "ping"}, timeout=2.0).get("ok", False)
        except (OSError, ValueError):
            return False

    def herramientas(self) -> list:
        return [
            {
                "nombre": "blender_informacion",
                "descripcion": (
                    "Devuelve un resumen de la escena actual de Blender: objetos, "
                    "colecciones, cámaras y luces. Úsala antes de modificar nada."
                ),
                "parametros": {"type": "object", "properties": {}, "required": []},
            },
            {
                "nombre": "blender_ejecutar_python",
                "descripcion": (
                    "Ejecuta código Python dentro de Blender con el módulo `bpy` "
                    "disponible. Úsala para crear o modificar geometría, materiales, "
                    "luces, cámaras, etc. Haz cambios en pasos pequeños y usa print() "
                    "para devolver información.\n\n" + REFERENCIA_KIT
                ),
                "parametros": {
                    "type": "object",
                    "properties": {
                        "codigo": {
                            "type": "string",
                            "description": "Código Python a ejecutar en Blender (bpy disponible).",
                        }
                    },
                    "required": ["codigo"],
                },
            },
        ]

    def ejecutar(self, nombre: str, argumentos: dict) -> str:
        try:
            if nombre == "blender_informacion":
                r = _enviar({"comando": "info"})
            else:
                # El código del modelo se compila aparte con nombre '<codigo>' para
                # que los números de línea de un error apunten a SU código, no al kit.
                codigo = (
                    KIT_FUENTE
                    + "\n_buildai_codigo = " + repr(argumentos.get("codigo", ""))
                    + "\nexec(compile(_buildai_codigo, '<codigo>', 'exec'), globals())\n"
                )
                # Timeout amplio: un render de calidad "alta" puede tardar minutos.
                # Los puentes antiguos (add-on < 1.2) ignoran el campo y cortan a los ~125 s.
                r = _enviar({"comando": "ejecutar", "codigo": codigo, "timeout": 570}, timeout=600.0)
        except OSError as exc:
            return f"ERROR: no se pudo hablar con Blender ({exc}). ¿Está abierto con el add-on activado?"
        if not r.get("ok"):
            return f"ERROR en Blender: {recortar(r.get('error', 'desconocido'))}"
        return recortar(r.get("resultado", "(sin salida)"))
