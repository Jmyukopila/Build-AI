"""Imagen de control de una reconstrucción.

Si el plano venía de una imagen (coordenadas en píxeles), la reconstrucción se
dibuja ENCIMA del original atenuado: cualquier desajuste (un muro desplazado,
una puerta que falta, una estancia mal cerrada) salta a la vista. Si venía en
metros (DXF o medidas leídas), se dibuja la planta limpia a escala.

La imagen se guarda como un render, así que la interfaz la muestra en el chat
sin más cambios.
"""

import io
import math

from PIL import Image, ImageDraw, ImageFont

from .modelo import TOL_SUPERFICIE

_LADO = 1400
_MARGEN = 50
_MACIZO = (220, 40, 40, 150)
_PUERTA = (30, 90, 220, 255)
_VENTANA = (0, 170, 200, 255)
_BIEN = (20, 130, 60, 255)
_MAL = (200, 30, 30, 255)


# Fuentes del sistema con acentos y "²" (la de Pillow por defecto no los tiene):
# Windows primero, que es donde corre la app; DejaVu/Liberation en Linux.
_FUENTES = ("segoeui.ttf", "arial.ttf", "DejaVuSans.ttf", "LiberationSans-Regular.ttf", "Arial.ttf")


def fuente(tamano):
    for nombre in _FUENTES:
        try:
            return ImageFont.truetype(nombre, tamano)
        except OSError:
            continue
    try:
        return ImageFont.load_default(size=tamano)
    except TypeError:  # Pillow < 10.1 no admite tamaño en la fuente por defecto
        return ImageFont.load_default()


def _a_imagen(planta, fondo):
    """Función metros → píxeles del lienzo, y el lienzo (RGBA) ya preparado."""
    t = planta["transformacion"]
    if fondo is not None and t["invertir_y"]:
        base = Image.open(io.BytesIO(fondo)).convert("RGB")
        # Original atenuado al 45 %: se ve de fondo sin competir con lo dibujado.
        base = Image.blend(base, Image.new("RGB", base.size, "white"), 0.55).convert("RGBA")
        f = t["factor"]
        dx, dy = t["desplazamiento"]
        giro = math.radians(t.get("giro", 0.0))
        coseno, seno = math.cos(giro), math.sin(giro)

        def px(p):
            # Inversa exacta de modelo.a_metros: escala, y invertida y giro.
            x, y = (p[0] - dx) / f, -(p[1] - dy) / f
            return (x * coseno - y * seno, x * seno + y * coseno)

        return px, base

    xs = [p[0] for p in planta["huella"]]
    ys = [p[1] for p in planta["huella"]]
    x0, y0 = min(xs), min(ys)
    escala = (_LADO - 2 * _MARGEN) / max(max(xs) - x0, max(ys) - y0, 1e-6)
    ancho = int((max(xs) - x0) * escala) + 2 * _MARGEN
    alto = int((max(ys) - y0) * escala) + 2 * _MARGEN
    lienzo = Image.new("RGBA", (ancho, alto), (255, 255, 255, 255))

    def px(p):
        return (_MARGEN + (p[0] - x0) * escala, alto - _MARGEN - (p[1] - y0) * escala)

    return px, lienzo


def dibujar(planta, fondo=None):
    """PNG de control de una planta normalizada. `fondo`: bytes de la imagen original."""
    px, base = _a_imagen(planta, fondo)
    capa = Image.new("RGBA", base.size, (0, 0, 0, 0))
    lienzo = ImageDraw.Draw(capa)
    escala = math.dist(px((0, 0)), px((1, 0)))  # píxeles por metro

    for x0, y0, x1, y1 in planta["macizos"]:
        # Las cuatro esquinas: si el original estaba girado, el muro también.
        lienzo.polygon([px((x0, y0)), px((x1, y0)), px((x1, y1)), px((x0, y1))], fill=_MACIZO)
    for m in planta["muros"]:
        if not m["ortogonal"]:
            lienzo.line([px(m["inicio"]), px(m["fin"])], fill=_MACIZO, width=max(2, int(m["espesor"] * escala)))

    grosor = max(2, int(escala * 0.03))
    for m in planta["muros"]:
        (x0, y0), (x1, y1) = m["inicio"], m["fin"]
        largo = math.hypot(x1 - x0, y1 - y0) or 1e-9
        ux, uy = (x1 - x0) / largo, (y1 - y0) / largo
        for h in m["huecos"]:
            a = (x0 + ux * h["a"], y0 + uy * h["a"])
            b = (a[0] + ux * h["ancho"], a[1] + uy * h["ancho"])
            color = _PUERTA if h["tipo"] in ("puerta", "paso") else _VENTANA
            lienzo.line([px(a), px(b)], fill=color, width=grosor * 2)
            # Marcas en las jambas, a todo el espesor: dejan ver de un vistazo si
            # el hueco reconstruido coincide con el corte del dibujo original.
            e2 = m["espesor"] / 2
            for p in (a, b):
                lienzo.line([px((p[0] - uy * e2, p[1] + ux * e2)), px((p[0] + uy * e2, p[1] - ux * e2))],
                            fill=color, width=grosor)

    fuente_rotulos = fuente(max(12, int(escala * 0.28)))
    for e in planta["estancias"]:
        plano = e["superficie_plano"]
        bien = plano is None or abs(e["superficie"] - plano) / plano <= TOL_SUPERFICIE
        texto = f"{e['nombre']}\n{e['superficie']:.2f} m²".replace(".", ",")
        if plano:
            texto += f"\n(plano {plano:.2f})".replace(".", ",")
        lienzo.multiline_text(px(e["centro"]), texto, fill=_BIEN if bien else _MAL, font=fuente_rotulos,
                              anchor="mm", align="center")

    resultado = Image.alpha_composite(base, capa).convert("RGB")
    if max(resultado.size) > 2000:
        factor = 2000 / max(resultado.size)
        resultado = resultado.resize((round(resultado.width * factor), round(resultado.height * factor)))
    salida = io.BytesIO()
    resultado.save(salida, "PNG", optimize=True)
    return salida.getvalue()
