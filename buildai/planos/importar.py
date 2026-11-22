"""Entrada de planos que no son una imagen: PDF y DXF.

- PDF: cada página se renderiza dos veces: una vista de 1568 px (lo que ve el
  modelo, el máximo útil para su visión) y una versión de alta resolución que
  se guarda en disco para el detector de muros, que mide mejor con más píxeles.
- DXF: es geometría vectorial exacta, así que no se "escanea": los muros salen
  de emparejar las dos caras paralelas de cada muro y las puertas de los arcos
  de giro. El modelo recibe una vista previa para entender el plano.

Los originales se guardan en ~/.buildai/planos/ con un identificador aleatorio
que viaja con el adjunto; las herramientas solo aceptan identificadores con ese
formato, así que ningún dato del modelo puede apuntar a otra ruta del disco.
"""

import io
import math
import re
import time
import uuid

from .. import rutas

LADO_VISTA = 1568          # coincide con MAX_LADO de la interfaz (ui/app.js)
LADO_ALTA = 3000           # resolución para el detector (y su límite de análisis)
MAX_PAGINAS_PDF = 6
DIAS_CONSERVACION = 30
_ID_VALIDO = re.compile(r"^[0-9a-f]{12}$")


class ErrorImportacion(ValueError):
    pass


# ------------------------------------------------------------ almacenamiento

def carpeta_planos():
    carpeta = rutas.CARPETA_DATOS / "planos"
    carpeta.mkdir(parents=True, exist_ok=True)
    return carpeta


def _limpiar_antiguos():
    """Borra originales de hace más de DIAS_CONSERVACION días (no crecer sin fin)."""
    limite = time.time() - DIAS_CONSERVACION * 86400
    for ruta in carpeta_planos().iterdir():
        try:
            if ruta.is_file() and ruta.stat().st_mtime < limite:
                ruta.unlink()
        except OSError:
            pass


def ruta_guardada(identificador, extension):
    """Ruta de un original guardado, o None si el id no es válido o no existe."""
    if not isinstance(identificador, str) or not _ID_VALIDO.match(identificador):
        return None
    ruta = carpeta_planos() / f"{identificador}.{extension}"
    return ruta if ruta.is_file() else None


def _nuevo_id():
    return uuid.uuid4().hex[:12]


def _png(imagen):
    salida = io.BytesIO()
    imagen.save(salida, "PNG", optimize=True)
    return salida.getvalue()


def _vista(imagen):
    """Versión para el modelo: lado máximo LADO_VISTA, PNG (o JPEG si pesa mucho)."""
    from PIL import Image

    escala = min(1.0, LADO_VISTA / max(imagen.size))
    if escala < 1.0:
        imagen = imagen.resize((round(imagen.width * escala), round(imagen.height * escala)), Image.LANCZOS)
    datos = _png(imagen)
    if len(datos) > 5 * 1024 * 1024:
        salida = io.BytesIO()
        imagen.convert("RGB").save(salida, "JPEG", quality=90)
        return salida.getvalue(), "image/jpeg", imagen.size
    return datos, "image/png", imagen.size


# ----------------------------------------------------------------------- PDF

def importar_pdf(datos: bytes, nombre: str):
    """Páginas del PDF como adjuntos de imagen (con su original en alta resolución)."""
    import pypdfium2 as pdfium

    _limpiar_antiguos()
    try:
        documento = pdfium.PdfDocument(datos)
    except Exception as exc:
        raise ErrorImportacion(f"No pude abrir el PDF «{nombre}»: {exc}")
    paginas = []
    try:
        total = len(documento)
        for indice in range(min(total, MAX_PAGINAS_PDF)):
            pagina = documento[indice]
            ancho, alto = pagina.get_size()
            escala = LADO_ALTA / max(ancho, alto)
            alta = pagina.render(scale=escala).to_pil().convert("RGB")
            identificador = _nuevo_id()
            (carpeta_planos() / f"{identificador}.png").write_bytes(_png(alta))
            vista, tipo, tamano = _vista(alta)
            paginas.append({
                "datos": vista,
                "media_type": tipo,
                "origen": {
                    "tipo": "pdf",
                    "id": identificador,
                    "nombre": nombre,
                    "pagina": indice + 1,
                    "paginas": total,
                    # Px de la vista por px del original: el detector mide en el
                    # original y devuelve coordenadas en la vista que ve el modelo.
                    "escala_vista": tamano[0] / alta.width,
                },
            })
    finally:
        documento.close()
    if not paginas:
        raise ErrorImportacion(f"El PDF «{nombre}» no tiene páginas.")
    return paginas


# ----------------------------------------------------------------------- DXF

# Factor a metros según $INSUNITS (0 = sin definir: se deduce del tamaño).
_UNIDADES_DXF = {1: 0.0254, 2: 0.3048, 4: 0.001, 5: 0.01, 6: 1.0}
_CAPA_MURO = re.compile(r"mur|wall|tabiq|fachad|cerram|partici", re.I)
_CAPA_EXCLUIDA = re.compile(r"cot|dim|text|rotul|mobil|furn|sanit|cocina|ejes?$|axis|grid|hatch|sombr|rayad", re.I)
_CAPA_CARPINTERIA = re.compile(r"puert|door|ventan|window|carpint|vidri|glaz", re.I)
_BLOQUE_PUERTA = re.compile(r"puert|door|^p\d", re.I)
_BLOQUE_VENTANA = re.compile(r"ventan|window|^v\d", re.I)

ESPESOR_MIN, ESPESOR_MAX = 0.05, 0.6


def _factor_dxf(documento, extension):
    codigo = int(documento.header.get("$INSUNITS", 0) or 0)
    if codigo in _UNIDADES_DXF:
        return _UNIDADES_DXF[codigo], f"$INSUNITS={codigo}"
    # Sin unidades declaradas: una vivienda mide decenas de metros, así que el
    # tamaño del dibujo delata si está en mm, cm o m.
    if extension > 2000:
        return 0.001, "sin unidades declaradas: se asumen milímetros por su tamaño"
    if extension > 200:
        return 0.01, "sin unidades declaradas: se asumen centímetros por su tamaño"
    return 1.0, "sin unidades declaradas: se asumen metros por su tamaño"


def _entidades(espacio, profundidad=0, bloque=None):
    """Recorre entidades explotando bloques (los planos a veces viven dentro de uno)."""
    for entidad in espacio:
        tipo = entidad.dxftype()
        if tipo == "INSERT" and profundidad < 4:
            nombre = entidad.dxf.name
            yield entidad, bloque
            try:
                virtuales = list(entidad.virtual_entities())
            except Exception:
                continue
            yield from _entidades(virtuales, profundidad + 1, bloque or nombre)
        else:
            yield entidad, bloque


def importar_dxf(datos: bytes, nombre: str):
    """Guarda el DXF, lo analiza y devuelve el adjunto con su vista previa."""
    _limpiar_antiguos()
    identificador = _nuevo_id()
    ruta = carpeta_planos() / f"{identificador}.dxf"
    ruta.write_bytes(datos)
    try:
        analisis = analizar_dxf(ruta)
    except ErrorImportacion:
        ruta.unlink(missing_ok=True)
        raise
    vista = dibujar_dxf(analisis)
    contenido, tipo, _ = _vista(vista)
    return [{
        "datos": contenido,
        "media_type": tipo,
        "origen": {"tipo": "dxf", "id": identificador, "nombre": nombre},
    }]


def analizar_dxf(ruta):
    import ezdxf
    from ezdxf import recover

    try:
        documento, _ = recover.readfile(str(ruta))
    except Exception as exc:
        raise ErrorImportacion(f"No pude leer el DXF: {exc}")

    crudos = []      # (p0, p1, capa, bloque) en unidades del dibujo
    arcos = []       # (centro, radio, ang0, ang1, capa, bloque)
    textos = []      # (texto, punto)
    bloques = []     # (nombre, punto, rotación)
    for entidad, bloque in _entidades(documento.modelspace()):
        capa = getattr(entidad.dxf, "layer", "0")
        tipo = entidad.dxftype()
        try:
            if tipo == "LINE":
                s, e = entidad.dxf.start, entidad.dxf.end
                crudos.append(((s.x, s.y), (e.x, e.y), capa, bloque))
            elif tipo == "LWPOLYLINE":
                puntos = [(float(p[0]), float(p[1])) for p in entidad.get_points("xy")]
                if entidad.closed and len(puntos) > 2:
                    puntos.append(puntos[0])
                crudos += [(a, b, capa, bloque) for a, b in zip(puntos, puntos[1:])]
            elif tipo == "POLYLINE":
                puntos = [(v.dxf.location.x, v.dxf.location.y) for v in entidad.vertices]
                if entidad.is_closed and len(puntos) > 2:
                    puntos.append(puntos[0])
                crudos += [(a, b, capa, bloque) for a, b in zip(puntos, puntos[1:])]
            elif tipo == "ARC":
                c = entidad.dxf.center
                arcos.append(((c.x, c.y), entidad.dxf.radius, entidad.dxf.start_angle,
                              entidad.dxf.end_angle, capa, bloque))
            elif tipo == "TEXT" and bloque is None:
                textos.append((entidad.dxf.text, (entidad.dxf.insert.x, entidad.dxf.insert.y)))
            elif tipo == "MTEXT" and bloque is None:
                textos.append((entidad.plain_text(), (entidad.dxf.insert.x, entidad.dxf.insert.y)))
            elif tipo == "INSERT" and bloque is None:
                p = entidad.dxf.insert
                bloques.append((entidad.dxf.name, (p.x, p.y), entidad.dxf.rotation))
        except Exception:
            continue  # una entidad corrupta no debe tumbar todo el plano
    if not crudos:
        raise ErrorImportacion("El DXF no contiene líneas ni polilíneas que analizar.")

    xs = [p[0] for a, b, _, _ in crudos for p in (a, b)]
    ys = [p[1] for a, b, _, _ in crudos for p in (a, b)]
    factor, nota_unidades = _factor_dxf(documento, max(max(xs) - min(xs), max(ys) - min(ys)))

    def m(p):
        return (p[0] * factor, p[1] * factor)

    segmentos = [(m(a), m(b), capa, bloque) for a, b, capa, bloque in crudos]
    capas_muro = {capa for _, _, capa, _ in segmentos if _CAPA_MURO.search(capa)}
    candidatos_muro = [
        (a, b) for a, b, capa, bloque in segmentos if _es_cara_de_muro(capa, bloque, capas_muro)
    ]
    muros = _emparejar_caras(candidatos_muro)
    huecos = _huecos_dxf(arcos, bloques, factor, muros)
    return {
        "factor": factor,
        "unidades": nota_unidades,
        "capas_muro": sorted(capas_muro),
        "segmentos": [(a, b) for a, b, _, _ in segmentos],
        "arcos": [(m(c), r * factor, a0, a1) for c, r, a0, a1, _, _ in arcos],
        "muros": muros,
        "huecos": huecos,
        "textos": [(t.strip(), m(p)) for t, p in textos if t and t.strip()],
    }


def _es_cara_de_muro(capa, bloque, capas_muro):
    """¿Puede esta línea ser la cara de un muro?

    Las líneas de bloques de puerta/ventana nunca lo son (sus marcos son pares
    de líneas paralelas que imitarían un muro fino). Si el dibujo tiene capas de
    muros, solo cuentan esas; si no, todas salvo cotas, textos y carpinterías.
    """
    if bloque is not None and (_BLOQUE_PUERTA.search(bloque) or _BLOQUE_VENTANA.search(bloque)):
        return False
    if capas_muro:
        return capa in capas_muro
    return not (_CAPA_EXCLUIDA.search(capa) or _CAPA_CARPINTERIA.search(capa))


def _emparejar_caras(segmentos):
    """Muros a partir de pares de líneas paralelas cercanas (las dos caras).

    Para cada línea se busca la paralela más próxima a una distancia de espesor
    de muro con la que se solape; el eje es la línea media sobre el tramo común.
    """
    lineas = []
    for (x0, y0), (x1, y1) in segmentos:
        largo = math.hypot(x1 - x0, y1 - y0)
        if largo < 0.2:
            continue
        angulo = math.atan2(y1 - y0, x1 - x0) % math.pi
        ux, uy = math.cos(angulo), math.sin(angulo)
        # Distancia con signo de la recta al origen (sobre su normal) y tramo
        # proyectado sobre su dirección: dos líneas paralelas solo difieren en eso.
        desfase = -x0 * uy + y0 * ux
        t0, t1 = sorted((x0 * ux + y0 * uy, x1 * ux + y1 * uy))
        lineas.append((round(math.degrees(angulo) * 2) / 2 % 180, desfase, t0, t1, ux, uy))

    por_angulo = {}
    for linea in lineas:
        por_angulo.setdefault(linea[0], []).append(linea)
    muros, vistos = [], set()
    for grupo in por_angulo.values():
        grupo.sort(key=lambda l: l[1])
        for i, a in enumerate(grupo):
            mejores = []
            for b in grupo[i + 1:]:
                d = b[1] - a[1]
                if d > ESPESOR_MAX:
                    break
                if d < ESPESOR_MIN:
                    continue
                solape = min(a[3], b[3]) - max(a[2], b[2])
                if solape < max(0.2, 0.3 * min(a[3] - a[2], b[3] - b[2])):
                    continue
                mejores.append((d, b, solape))
            if not mejores:
                continue
            d_min = min(d for d, _, _ in mejores)
            for d, b, _ in mejores:
                if d > d_min + 0.01:
                    continue
                clave = (id(a), id(b))
                if clave in vistos:
                    continue
                vistos.add(clave)
                t0, t1 = max(a[2], b[2]), min(a[3], b[3])
                medio = (a[1] + b[1]) / 2
                ux, uy = a[4], a[5]
                # Punto = t·u + desfase·n, con n = (-uy, ux).
                p0 = (t0 * ux - medio * uy, t0 * uy + medio * ux)
                p1 = (t1 * ux - medio * uy, t1 * uy + medio * ux)
                muros.append({"inicio": p0, "fin": p1, "espesor": round(d, 3)})
    for k, muro in enumerate(muros, 1):
        muro["id"] = f"D{k}"
        muro["inicio"] = (round(float(muro["inicio"][0]), 3), round(float(muro["inicio"][1]), 3))
        muro["fin"] = (round(float(muro["fin"][0]), 3), round(float(muro["fin"][1]), 3))
    return muros


def _distancia_a_muro(p, muro):
    (x0, y0), (x1, y1) = muro["inicio"], muro["fin"]
    largo = math.hypot(x1 - x0, y1 - y0) or 1e-9
    ux, uy = (x1 - x0) / largo, (y1 - y0) / largo
    return abs(-(p[0] - x0) * uy + (p[1] - y0) * ux)


def _huecos_dxf(arcos, bloques, factor, muros):
    """Puertas por su arco de giro y ventanas por sus bloques, en metros."""
    huecos = []
    for (c, r, a0, a1, capa, _bloque) in arcos:
        radio = r * factor
        barrido = (a1 - a0) % 360
        if not (0.5 <= radio <= 1.3 and 60 <= barrido <= 120):
            continue
        bisagra = (c[0] * factor, c[1] * factor)
        extremos = [
            (bisagra[0] + radio * math.cos(math.radians(a)), bisagra[1] + radio * math.sin(math.radians(a)))
            for a in (a0, a1)
        ]
        # Con la puerta cerrada, la hoja va de la bisagra a la otra jamba: el
        # centro del hueco es el punto medio que cae sobre un muro.
        centros = [((bisagra[0] + e[0]) / 2, (bisagra[1] + e[1]) / 2) for e in extremos]
        if muros:
            centro = min(centros, key=lambda p: min(_distancia_a_muro(p, m) for m in muros))
        else:
            centro = centros[0]
        huecos.append({"tipo": "puerta", "centro": (round(centro[0], 3), round(centro[1], 3)),
                       "ancho": round(radio, 3), "fuente": f"arco en capa {capa}"})
    for nombre, p, _rotacion in bloques:
        if _BLOQUE_VENTANA.search(nombre):
            huecos.append({"tipo": "ventana", "centro": (round(p[0] * factor, 3), round(p[1] * factor, 3)),
                           "ancho": None, "fuente": f"bloque {nombre} (punto de inserción)"})
    return huecos


def dibujar_dxf(analisis, lado=LADO_ALTA):
    """Vista previa del DXF: todo en gris y los muros detectados en negro."""
    from PIL import Image, ImageDraw

    puntos = [p for a, b in analisis["segmentos"] for p in (a, b)]
    x0, x1 = min(p[0] for p in puntos), max(p[0] for p in puntos)
    y0, y1 = min(p[1] for p in puntos), max(p[1] for p in puntos)
    margen = 40
    escala = (lado - 2 * margen) / max(x1 - x0, y1 - y0, 1e-6)
    ancho = int((x1 - x0) * escala) + 2 * margen
    alto = int((y1 - y0) * escala) + 2 * margen
    imagen = Image.new("RGB", (ancho, alto), "white")
    lienzo = ImageDraw.Draw(imagen)

    def px(p):
        return (margen + (p[0] - x0) * escala, alto - margen - (p[1] - y0) * escala)

    for a, b in analisis["segmentos"]:
        lienzo.line([px(a), px(b)], fill=(150, 150, 150), width=1)
    for c, r, a0, a1 in analisis["arcos"]:
        cx, cy = px(c)
        rr = r * escala
        # La y de la imagen va hacia abajo: los ángulos se reflejan.
        lienzo.arc([cx - rr, cy - rr, cx + rr, cy + rr], -a1, -a0, fill=(150, 150, 150))
    for m in analisis["muros"]:
        lienzo.line([px(m["inicio"]), px(m["fin"])], fill=(0, 0, 0), width=max(2, int(m["espesor"] * escala)))
    return imagen


def resumen_dxf(analisis, max_textos=80):
    """Texto para el modelo: muros, huecos y textos del DXF, ya en metros."""
    lineas = [
        f"DXF analizado ({analisis['unidades']}). Coordenadas en METROS del propio dibujo "
        "(usa \"unidades\": \"m\" en plano_reconstruir; no hace falta calibrar).",
    ]
    if analisis["capas_muro"]:
        lineas.append(f"Capas de muros: {', '.join(analisis['capas_muro'])}.")
    else:
        lineas.append("No hay capas con nombre de muro: se han emparejado las líneas de todas las capas "
                      "salvo cotas, textos y mobiliario. Revisa que no haya muros falsos.")
    lineas.append(f"Muros por pares de caras ({len(analisis['muros'])}: id, eje inicio → fin, espesor):")
    for mu in analisis["muros"]:
        lineas.append(f"  {mu['id']}: {list(mu['inicio'])} → {list(mu['fin'])}, e={mu['espesor']}")
    if analisis["huecos"]:
        lineas.append("Huecos encontrados (tipo, centro, ancho):")
        for h in analisis["huecos"]:
            ancho = "?" if h["ancho"] is None else h["ancho"]
            lineas.append(f"  {h['tipo']} {list(h['centro'])} ancho {ancho} — {h['fuente']}")
    if analisis["textos"]:
        lineas.append("Textos (nombres de estancia, superficies, cotas) y su posición:")
        for t, p in analisis["textos"][:max_textos]:
            lineas.append(f"  «{t[:60]}» en {[round(p[0], 2), round(p[1], 2)]}")
        if len(analisis["textos"]) > max_textos:
            lineas.append(f"  … y {len(analisis['textos']) - max_textos} textos más.")
    return "\n".join(lineas)
