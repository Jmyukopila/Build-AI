"""Detector de muros en planos rasterizados (fotos, escaneos, PDF renderizados).

Un modelo de visión entiende un plano (qué es una puerta, cómo se llama cada
estancia, qué dice cada cota), pero estima mal las coordenadas: se equivoca
fácilmente en decenas de píxeles. Este detector hace lo contrario: no entiende
nada, pero mide al píxel. Juntos dan la reconstrucción fiel.

Idea: en un plano de arquitectura los muros son los trazos más GRUESOS. Tras
binarizar, se estima el espesor dominante de trazo y una apertura morfológica
(erosión + dilatación) borra todo lo que sea más fino (cotas, textos,
mobiliario, rayados), dejando solo los muros. Después se buscan bandas
horizontales y verticales y cada una se convierte en un segmento con espesor.
Los cortes entre tramos colineales son los candidatos a puertas y ventanas.

Solo usa numpy y Pillow (sin OpenCV: 90 MB menos en el instalador).
"""

import io

import numpy as np
from PIL import Image, ImageOps

MAX_LADO_ANALISIS = 3000   # por encima se reduce: más resolución no mejora y tarda mucho


class ErrorDetector(ValueError):
    pass


# ------------------------------------------------------------- morfología

def _suma_ventana(valores, k):
    """Suma de cada ventana k×k centrada (k impar), con imagen integral.

    Con vistas (slices) de la integral: cuatro restas de matrices, sin bucles y
    sin copias intermedias del tamaño de la imagen por cada desplazamiento.
    """
    r = k // 2
    integral = np.pad(valores, ((r + 1, r), (r + 1, r))).cumsum(0).cumsum(1)
    return integral[k:, k:] - integral[:-k, k:] - integral[k:, :-k] + integral[:-k, :-k]


def _apertura(mascara, k):
    """Erosión y dilatación con un cuadrado k×k: elimina trazos más finos que k."""
    erosion = _suma_ventana(mascara.astype(np.int32), k) == k * k
    return _suma_ventana(erosion.astype(np.int32), k) > 0


def _cierre(mascara, k):
    """Dilatación y erosión: rellena huecos de menos de k (muros dibujados a dos líneas)."""
    dilatada = _suma_ventana(mascara.astype(np.int32), k) > 0
    return _suma_ventana(dilatada.astype(np.int32), k) == k * k


def _binarizar(gris):
    """Píxeles de trazo: más oscuros que su entorno, o muy oscuros en absoluto.

    El umbral local tolera fotos con iluminación desigual; el absoluto conserva
    el interior de muros macizos negros más anchos que la ventana local.
    """
    h, w = gris.shape
    k = max(15, (min(h, w) // 20) | 1)
    suma = _suma_ventana(gris.astype(np.int64), k)
    cuenta = _suma_ventana(np.ones((h, w), dtype=np.int32), k)
    media = suma / cuenta
    return (gris < media - 20) | (gris < 60)


# ------------------------------------------------------- espesor de trazo

def _rachas(fila):
    """(inicio, fin_exclusivo) de cada racha de True en un vector booleano."""
    bordes = np.diff(np.concatenate(([0], fila.astype(np.int8), [0])))
    return np.flatnonzero(bordes == 1), np.flatnonzero(bordes == -1)


def _espesor_dominante(mascara):
    """Longitud de racha perpendicular que más "masa" de tinta acumula.

    Un muro horizontal de L píxeles aporta L rachas verticales de su espesor; los
    textos y cotas aportan muchas rachas cortas pero poca masa cada una.
    """
    limite = max(8, min(120, min(mascara.shape) // 6))
    masa = np.zeros(limite + 1)
    for matriz in (mascara, mascara.T):
        for fila in matriz[:: max(1, matriz.shape[0] // 600)]:
            inicios, fines = _rachas(fila)
            largos = fines - inicios
            largos = largos[(largos >= 3) & (largos <= limite)]
            np.add.at(masa, largos, largos)
    if masa.sum() == 0:
        return None
    # Suavizado ligero: el antialiasing reparte un mismo espesor entre t y t±1.
    suave = np.convolve(masa, [0.25, 0.5, 0.25], mode="same")
    return int(np.argmax(suave))


# ---------------------------------------------------------------- bandas

def _bandas(muros, largo_minimo):
    """Agrupa rachas largas de filas consecutivas que se solapan en bandas.

    Devuelve [(x0, x1_exclusivo, y_centro, espesor)] para bandas horizontales
    de `muros` (para las verticales se llama con la matriz transpuesta).
    """
    grupos = []          # cada grupo: lista de rachas (y, x0, x1)
    activos = []         # (x0, x1, índice_grupo) de la fila anterior
    for y in range(muros.shape[0]):
        inicios, fines = _rachas(muros[y])
        nuevos = []
        for x0, x1 in zip(inicios, fines):
            if x1 - x0 < largo_minimo:
                continue
            grupo = None
            for a0, a1, g in activos:
                solape = min(x1, a1) - max(x0, a0)
                if solape >= 0.5 * min(x1 - x0, a1 - a0):
                    grupo = g
                    break
            if grupo is None:
                grupo = len(grupos)
                grupos.append([])
            grupos[grupo].append((y, int(x0), int(x1)))
            nuevos.append((x0, x1, grupo))
        activos = nuevos
    bandas = []
    for rachas in grupos:
        bandas.extend(_partir_por_espesor(rachas, largo_minimo))
    return bandas


def _partir_por_espesor(rachas, largo_minimo):
    """Divide un grupo donde cambia el espesor a lo largo de la banda.

    Un tabique alineado por su cara con un muro más grueso forma con él una
    sola mancha continua; columna a columna, sin embargo, su espesor y su
    centro son otros. Cada tramo de espesor homogéneo es un muro distinto.
    """
    x_min = min(x0 for _, x0, _ in rachas)
    x_max = max(x1 for _, _, x1 in rachas)
    cuenta = np.zeros(x_max - x_min)
    suma_y = np.zeros(x_max - x_min)
    for y, x0, x1 in rachas:
        cuenta[x0 - x_min:x1 - x_min] += 1
        suma_y[x0 - x_min:x1 - x_min] += y
    tramos, inicio = [], 0
    for x in range(1, len(cuenta) + 1):
        if x < len(cuenta):
            referencia = np.median(cuenta[inicio:x])
            if abs(cuenta[x] - referencia) <= max(2.0, 0.3 * referencia):
                continue
        tramos.append((inicio, x))
        inicio = x
    bandas = []
    for a, b in tramos:
        if b - a < largo_minimo or cuenta[a:b].sum() == 0:
            continue
        espesor = float(np.median(cuenta[a:b]))
        centro = float(suma_y[a:b].sum() / cuenta[a:b].sum()) + 0.5
        bandas.append((x_min + a, x_min + b, centro, espesor))
    return bandas


def _segmentos(muros, espesor):
    largo_minimo = max(3 * espesor, 12)
    horizontales = [
        b for b in _bandas(muros, largo_minimo)
        if b[3] >= max(2, 0.25 * espesor) and (b[1] - b[0]) >= 2.5 * b[3]
    ]
    verticales = [
        b for b in _bandas(muros.T, largo_minimo)
        if b[3] >= max(2, 0.25 * espesor) and (b[1] - b[0]) >= 2.5 * b[3]
    ]
    segmentos = []
    for k, (x0, x1, yc, e) in enumerate(sorted(horizontales, key=lambda b: (b[2], b[0])), 1):
        segmentos.append({"id": f"H{k}", "orient": "h", "inicio": (x0, yc), "fin": (x1, yc), "espesor": e})
    for k, (y0, y1, xc, e) in enumerate(sorted(verticales, key=lambda b: (b[2], b[0])), 1):
        segmentos.append({"id": f"V{k}", "orient": "v", "inicio": (xc, y0), "fin": (xc, y1), "espesor": e})
    return segmentos


def _recortar_a_ejes(segmentos):
    """Lleva cada extremo que entra en un muro perpendicular a su eje.

    Las bandas llegan hasta la cara exterior en las esquinas; acotar de eje a
    eje es lo que hace el resto de la cadena (y lo que se entiende por longitud
    de un muro cuando se calibra con una cota "exterior" = eje + espesor).
    """
    for s in segmentos:
        largo = 0 if s["orient"] == "h" else 1
        eje = s["inicio"][largo ^ 1]
        for k in ("inicio", "fin"):
            extremo = s[k][largo]
            mejor = None
            for p in segmentos:
                if p["orient"] == s["orient"]:
                    continue
                a, b = sorted((p["inicio"][largo ^ 1], p["fin"][largo ^ 1]))
                if not a - 1 <= eje <= b + 1:
                    continue
                eje_p = p["inicio"][largo]
                if abs(extremo - eje_p) <= p["espesor"] / 2 + 1.5 and (
                    mejor is None or abs(extremo - eje_p) < abs(extremo - mejor)
                ):
                    mejor = eje_p
            if mejor is not None:
                punto = list(s[k])
                punto[largo] = mejor
                s[k] = tuple(punto)


def _extremo_unido(s, fin, c, cruzados, largo):
    """¿El extremo `fin` del tramo `s` entra en la banda de un muro perpendicular?"""
    for p in cruzados:
        a, b = sorted((p["inicio"][largo ^ 1], p["fin"][largo ^ 1]))
        if not a - s["espesor"] <= c <= b + s["espesor"]:
            continue
        eje_p = p["inicio"][largo]
        if abs(fin - eje_p) <= p["espesor"] / 2 + 2:
            return True
    return False


def _huecos_candidatos(segmentos, espesor):
    """Cortes en una línea de muro que miden lo que mide una puerta o ventana.

    Se buscan entre dos tramos colineales y entre el final de un tramo y la cara
    del muro perpendicular que lo recibe (puertas junto a una esquina).
    """
    candidatos = []
    # Ningún hueco real supera ~15 espesores (4,5 m con muros de 30 cm).
    minimo, maximo = 1.5 * espesor, 15 * espesor
    for orient in ("h", "v"):
        eje = 1 if orient == "h" else 0
        largo = 0 if orient == "h" else 1
        propios = [s for s in segmentos if s["orient"] == orient]
        cruzados = [s for s in segmentos if s["orient"] != orient]
        for s in propios:
            fin = s["fin"][largo]
            c = s["inicio"][eje]
            if _extremo_unido(s, fin, c, cruzados, largo):
                continue  # acaba en una esquina o una T: tras él no hay hueco
            # El obstáculo más cercano tras el final del tramo, en su misma línea.
            mejor = None
            for t in propios:
                if t is s or abs(t["inicio"][eje] - c) > max(s["espesor"], t["espesor"]) / 2:
                    continue
                separacion = t["inicio"][largo] - fin
                if separacion > 0 and (mejor is None or separacion < mejor[0]):
                    mejor = (separacion, t, fin, t["inicio"][largo])
            for p in cruzados:
                a, b = sorted((p["inicio"][largo ^ 1], p["fin"][largo ^ 1]))
                if not a - s["espesor"] <= c <= b + s["espesor"]:
                    continue
                cara = p["inicio"][largo] - p["espesor"] / 2
                separacion = cara - fin
                if separacion > 0 and (mejor is None or separacion < mejor[0]):
                    mejor = (separacion, p, fin, cara)
            if mejor is None or not minimo <= mejor[0] <= maximo:
                continue
            _, otro, desde, hasta = mejor
            medio = (desde + hasta) / 2
            centro = (medio, c) if orient == "h" else (c, medio)
            candidatos.append({"centro": centro, "ancho": hasta - desde, "entre": (s["id"], otro["id"])})
    return candidatos


# ------------------------------------------------------------------ giro

def _nitidez(mascara_img, angulo):
    """Cuánto se concentran los trazos en filas y columnas al girar `angulo` grados.

    Con el plano recto, los muros caen enteros en pocas filas/columnas y la suma
    de cuadrados de las proyecciones es máxima.
    """
    girada = np.asarray(mascara_img.rotate(angulo, resample=Image.NEAREST, expand=True), dtype=np.float64)
    return float((girada.sum(0) ** 2).sum() + (girada.sum(1) ** 2).sum())


def _estimar_giro(trazo):
    """Ángulo (grados, sentido de PIL) que endereza el plano, buscado en ±6°."""
    pequena = Image.fromarray((trazo * 255).astype(np.uint8))
    if max(pequena.size) > 900:
        f = 900 / max(pequena.size)
        pequena = pequena.resize((round(pequena.width * f), round(pequena.height * f)), Image.NEAREST)
    mejor = max(np.arange(-6.0, 6.01, 0.25), key=lambda a: _nitidez(pequena, a))
    fino = max(np.arange(mejor - 0.25, mejor + 0.26, 0.05), key=lambda a: _nitidez(pequena, a))
    return round(float(fino), 2)


# ----------------------------------------------------------------- entrada

def cargar_gris(datos: bytes):
    """Imagen en escala de grises (uint8) y factor imagen_original / analizada."""
    try:
        imagen = Image.open(io.BytesIO(datos))
        imagen = ImageOps.exif_transpose(imagen)
    except Exception as exc:
        raise ErrorDetector(f"No pude abrir la imagen: {exc}")
    if imagen.mode in ("RGBA", "LA", "P"):
        # Un PNG transparente tiene el dibujo sobre "nada": fondo blanco.
        fondo = Image.new("RGBA", imagen.size, (255, 255, 255, 255))
        fondo.alpha_composite(imagen.convert("RGBA"))
        imagen = fondo
    imagen = imagen.convert("L")
    factor = 1.0
    if max(imagen.size) > MAX_LADO_ANALISIS:
        factor = max(imagen.size) / MAX_LADO_ANALISIS
        imagen = imagen.resize(
            (round(imagen.width / factor), round(imagen.height / factor)), Image.LANCZOS
        )
    return np.asarray(imagen, dtype=np.uint8), factor


def detectar_muros(datos: bytes, modo="auto", escala_salida=1.0):
    """Detecta los muros de una imagen de plano.

    `modo`: "macizo" (muros rellenos en negro o gris, lo habitual), "hueco"
    (muros dibujados solo con sus dos caras) o "auto" (prueba macizo y, si apenas
    encuentra muros, hueco). `escala_salida` multiplica las coordenadas
    devueltas (para expresarlas en los píxeles de otra versión de la imagen).
    """
    gris, factor = cargar_gris(datos)
    trazo = _binarizar(gris)
    if trazo.mean() > 0.6:
        raise ErrorDetector("La imagen es casi toda oscura: ¿es un plano en negativo o una foto sin plano?")

    # Un escaneo o una foto rara vez están rectos: con 1° de giro un muro de
    # 500 px se desplaza 9 px de punta a punta y su banda se rompe en escalones.
    # Se mide sobre la imagen enderezada y se devuelve en la original.
    giro = _estimar_giro(trazo) if trazo.any() else 0.0
    alto_original, ancho_original = gris.shape
    if abs(giro) >= 0.15:  # por debajo, el ruido de JPEG falsea más que el giro (≈2 px en 1500)
        enderezada = Image.fromarray(gris).rotate(giro, resample=Image.BICUBIC, expand=True, fillcolor=255)
        gris = np.asarray(enderezada, dtype=np.uint8)
        trazo = _binarizar(gris)
    else:
        giro = 0.0

    intentos = ["macizo", "hueco"] if modo == "auto" else [modo]
    mejor = None
    for intento in intentos:
        mascara = trazo
        if intento == "hueco":
            # Muros a dos líneas: se cierra el espacio entre caras antes de medir.
            mascara = _cierre(trazo, 2 * (max(3, _espesor_dominante(trazo) or 3) * 3 // 2) + 1)
        espesor = _espesor_dominante(mascara)
        if espesor is None:
            continue
        # El núcleo debe ser más fino que el tabique más delgado (un tabique de
        # 10 cm junto a fachadas de 30-35 cm es ≈ 0,3 del espesor dominante) pero
        # más grueso que textos, cotas y líneas de carpintería (1-3 px).
        k = max(3, int(round(espesor * 0.28)) | 1)
        muros = _apertura(mascara, k)
        segmentos = _segmentos(muros, espesor)
        cubiertos = np.zeros_like(muros)
        for s in segmentos:
            (x0, y0), (x1, y1) = s["inicio"], s["fin"]
            e2 = s["espesor"] / 2
            if s["orient"] == "h":
                cubiertos[int(y0 - e2):int(y0 + e2) + 1, int(x0):int(x1)] = True
            else:
                cubiertos[int(y0):int(y1), int(x0 - e2):int(x0 + e2) + 1] = True
        cobertura = float((muros & cubiertos).sum() / max(1, muros.sum()))
        resultado = {"modo": intento, "espesor": espesor, "segmentos": segmentos, "cobertura": cobertura}
        largo_total = sum(abs(s["fin"][0] - s["inicio"][0]) + abs(s["fin"][1] - s["inicio"][1]) for s in segmentos)
        resultado["largo_total"] = largo_total
        if mejor is None or (len(mejor["segmentos"]) < 4 and largo_total > mejor["largo_total"]):
            mejor = resultado
        if len(segmentos) >= 4:
            break
    if mejor is None or not mejor["segmentos"]:
        raise ErrorDetector(
            "No encontré muros: no hay trazos gruesos horizontales o verticales. "
            "Si el plano está girado o fotografiado en perspectiva, pide una imagen recta."
        )

    a_salida = factor * escala_salida
    # PIL gira en sentido antihorario en pantalla (con la y hacia abajo) y
    # `expand` centra el resultado: se deshace girando alrededor de los centros.
    rad = np.radians(giro)
    cx_rot, cy_rot = gris.shape[1] / 2, gris.shape[0] / 2
    cx_ori, cy_ori = ancho_original / 2, alto_original / 2

    def convertir(p):
        x, y = p[0] - cx_rot, p[1] - cy_rot
        xo = x * np.cos(rad) - y * np.sin(rad) + cx_ori
        yo = x * np.sin(rad) + y * np.cos(rad) + cy_ori
        return (round(float(xo) * a_salida, 1), round(float(yo) * a_salida, 1))

    # Cortes y recorte a ejes se calculan en el marco enderezado (donde los
    # muros son horizontales y verticales); un corte se mide entre caras, así
    # que va antes del recorte. Solo al final se pasa todo a la imagen original.
    candidatos = _huecos_candidatos(mejor["segmentos"], mejor["espesor"])
    _recortar_a_ejes(mejor["segmentos"])
    for s in mejor["segmentos"]:
        s["inicio"], s["fin"] = convertir(s["inicio"]), convertir(s["fin"])
        s["espesor"] = round(s["espesor"] * a_salida, 1)
    for c in candidatos:
        c["centro"] = convertir(c["centro"])
        c["ancho"] = round(c["ancho"] * a_salida, 1)
    return {
        "ancho_px": round(ancho_original * a_salida),
        "alto_px": round(alto_original * a_salida),
        "giro": giro,
        "modo": mejor["modo"],
        "espesor_px": round(mejor["espesor"] * a_salida, 1),
        "cobertura": round(mejor["cobertura"], 2),
        "muros": mejor["segmentos"],
        "huecos": candidatos,
    }


def resumen_texto(deteccion):
    """Resultado compacto para el modelo (una línea por muro: cabe en su contexto)."""
    lineas = [
        f"Imagen de {deteccion['ancho_px']}×{deteccion['alto_px']} px (origen arriba a la izquierda, "
        f"y hacia abajo). Muros dibujados {deteccion['modo']}s, espesor típico "
        f"{deteccion['espesor_px']} px. {len(deteccion['muros'])} muros detectados "
        f"(cubren el {round(deteccion['cobertura'] * 100)} % del trazo grueso).",
    ]
    if deteccion.get("giro"):
        lineas.append(
            f"El plano está girado {deteccion['giro']}°: las coordenadas son las de la imagen "
            f"original, así que pon \"giro\": {deteccion['giro']} en plano_reconstruir para "
            "enderezarlo (afecta igual a muros, huecos y estancias)."
        )
    if deteccion["cobertura"] < 0.6:
        lineas.append(
            "AVISO: parte del trazo grueso no es horizontal ni vertical (muros inclinados, "
            "plano girado o mobiliario macizo): añade a mano los muros que falten."
        )
    lineas.append("Muros (id: inicio → fin, espesor; coordenadas del EJE en px):")
    for s in deteccion["muros"]:
        lineas.append(f"  {s['id']}: {list(s['inicio'])} → {list(s['fin'])}, e={s['espesor']}")
    if deteccion["huecos"]:
        lineas.append("Cortes en los muros (candidatos a puerta/ventana: centro, ancho en px):")
        for h in deteccion["huecos"]:
            lineas.append(f"  {list(h['centro'])} ancho {h['ancho']} (entre {h['entre'][0]} y {h['entre'][1]})")
    return "\n".join(lineas)
