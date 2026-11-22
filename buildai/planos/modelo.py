"""Plano neutro: lo que la IA lee de un plano, validado y llevado a metros.

La IA transcribe el plano (muros, huecos, estancias y cotas) a un JSON sencillo,
en las unidades que le resulten naturales (píxeles de la imagen, cm, mm o m).
`normalizar()` lo convierte en un plano limpio y verificable, del que salen
después los constructores de Blender, AutoCAD, SketchUp y Revit:

1. Escala: con varias cotas de calibración se toma la mediana y se avisa de las
   que discrepan (una cota mal leída no deforma todo el edificio).
2. Limpieza: endereza muros casi ortogonales, alinea los que comparten eje,
   funde los colineales que se tocan y une los extremos en esquinas y "T".
3. Huecos: cada puerta o ventana se engancha a su muro. Si su posición cae en
   el hueco que el dibujo deja entre dos tramos de muro, se toma ESE hueco como
   medida (es más fiable que el ancho estimado a ojo) y los tramos se unen.
4. Comprobación: la superficie útil de cada estancia se calcula con los muros
   reconstruidos y se compara con la que indica el plano.

Formato de entrada (todas las claves en español; solo `plantas` y `muros` son
obligatorias):

    {
      "unidades": "px" | "cm" | "mm" | "m",
      "calibracion": [                       # obligatoria con "px"
        {"muro": "M3", "medida": 9.40, "referencia": "exterior" | "eje"},
        {"p1": [x, y], "p2": [x, y], "medida": 3.25}
      ],
      "plantas": [{
        "nombre": "Planta baja", "nivel": 0.0, "altura": 2.7,
        "muros": [{"id": "M1", "inicio": [x, y], "fin": [x, y], "espesor": e}],
        "huecos": [{"tipo": "puerta" | "ventana" | "ventanal" | "paso",
                    "centro": [x, y], "ancho": 0.8, "alto": 2.05,
                    "antepecho": 0.9, "abre_hacia": [x, y]}],
        "estancias": [{"nombre": "Cocina", "centro": [x, y], "superficie": 9.8}]
      }]
    }

Las medidas de `calibracion.medida`, `ancho`, `alto`, `antepecho`, `altura`,
`nivel` y `superficie` van SIEMPRE en metros (o m²), aunque las coordenadas
vayan en píxeles: son lo que el arquitecto lee en las cotas del plano.
"""

import math
import statistics

from .geometria import Rejilla, area_poligono, punto_en_poligono

UNIDADES = {"m": 1.0, "cm": 0.01, "mm": 0.001, "px": None}
TIPOS_HUECO = ("puerta", "ventana", "ventanal", "paso")

# Tolerancias de limpieza, en metros (o grados). Están pensadas para la
# precisión de un plano escaneado a ~1-2 cm por píxel: más finas dejarían
# esquinas abiertas; más gruesas fundirían muros que de verdad están separados.
TOL_ORTOGONAL_GRADOS = 4.0
TOL_ALINEAR = 0.06
TOL_FUNDIR = 0.03
TOL_DESVIACION_COTAS = 0.02     # 2 % entre cotas ya indica una mal leída
TOL_SUPERFICIE = 0.05           # 5 % entre la superficie del plano y la reconstruida

ESPESOR_DEFECTO = 0.2
ALTURA_DEFECTO = 2.7
FORJADO_DEFECTO = 0.3

_POR_DEFECTO_HUECO = {
    #            alto,  antepecho
    "puerta":   (2.05, 0.0),
    "ventana":  (1.2, 0.9),
    "ventanal": (None, 0.0),   # de suelo a techo: depende de la altura de planta
    "paso":     (2.05, 0.0),
}


class ErrorPlano(ValueError):
    """El plano recibido no se puede interpretar (falta algo imprescindible)."""


# ---------------------------------------------------------------- utilidades

def _numero(valor, campo):
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        raise ErrorPlano(f"«{campo}» debe ser un número (recibido: {valor!r}).")
    if not math.isfinite(numero):
        raise ErrorPlano(f"«{campo}» no es un número válido.")
    return numero


def _punto(valor, campo):
    if not isinstance(valor, (list, tuple)) or len(valor) < 2:
        raise ErrorPlano(f"«{campo}» debe ser un punto [x, y] (recibido: {valor!r}).")
    return (_numero(valor[0], campo), _numero(valor[1], campo))


def _m(valor):
    """Formato de medida para el informe: coma decimal, como en un plano español."""
    return f"{valor:.2f}".replace(".", ",")


def _porcentaje(fraccion):
    return f"{fraccion * 100:+.1f} %".replace(".", ",")


def _distancia(a, b):
    return math.hypot(b[0] - a[0], b[1] - a[1])


# ------------------------------------------------------------------- el muro

class _Muro:
    """Muro de trabajo durante la limpieza.

    Los muros ortogonales se describen por su eje (`orient` "h" con y constante
    o "v" con x constante), la coordenada de ese eje (`eje`) y su tramo [s0, s1]
    a lo largo de él. Los inclinados conservan sus dos puntos.
    """

    def __init__(self, ids, p0, p1, espesor):
        self.ids = list(ids)
        self.p0, self.p1 = p0, p1
        self.espesor = espesor
        self.orient = None
        self.eje = self.s0 = self.s1 = None
        # Ajuste de la cara de cada extremo respecto al eje en una unión: positivo
        # alarga el muro hasta la cara exterior del otro, negativo lo para en su
        # cara cercana. Así ningún par de muros se solapa ni deja la esquina abierta.
        self.extension = [0.0, 0.0]
        self.unido = [False, False]
        self.huecos = []  # {"tipo", "s" (centro a lo largo del eje), "ancho", ...}

    @property
    def ortogonal(self):
        return self.orient is not None

    def enderezar(self):
        dx, dy = self.p1[0] - self.p0[0], self.p1[1] - self.p0[1]
        angulo = math.degrees(math.atan2(dy, dx)) % 180.0
        if min(angulo, 180.0 - angulo) <= TOL_ORTOGONAL_GRADOS:
            self.orient, self.eje = "h", (self.p0[1] + self.p1[1]) / 2.0
            self.s0, self.s1 = sorted((self.p0[0], self.p1[0]))
        elif abs(angulo - 90.0) <= TOL_ORTOGONAL_GRADOS:
            self.orient, self.eje = "v", (self.p0[0] + self.p1[0]) / 2.0
            self.s0, self.s1 = sorted((self.p0[1], self.p1[1]))

    def punto(self, s):
        """Punto del eje en la coordenada `s` (solo muros ortogonales)."""
        return (s, self.eje) if self.orient == "h" else (self.eje, s)

    def extremos_eje(self):
        if self.ortogonal:
            return self.punto(self.s0), self.punto(self.s1)
        return self.p0, self.p1

    def extremos_obra(self):
        """Extremos de construcción: el eje más los ajustes de las uniones."""
        if self.ortogonal:
            return self.punto(self.s0 - self.extension[0]), self.punto(self.s1 + self.extension[1])
        return self.p0, self.p1

    def largo(self):
        a, b = self.extremos_eje()
        return _distancia(a, b)

    def relacion(self, c):
        """(distancia lateral al eje, coordenada a lo largo, ¿cae dentro del tramo?)."""
        if self.ortogonal:
            if self.orient == "h":
                lateral, s = abs(c[1] - self.eje), c[0]
            else:
                lateral, s = abs(c[0] - self.eje), c[1]
            return lateral, s, self.s0 <= s <= self.s1
        (x0, y0), (x1, y1) = self.p0, self.p1
        largo = _distancia(self.p0, self.p1) or 1e-9
        ux, uy = (x1 - x0) / largo, (y1 - y0) / largo
        s = (c[0] - x0) * ux + (c[1] - y0) * uy
        lateral = abs(-(c[0] - x0) * uy + (c[1] - y0) * ux)
        return lateral, s, 0.0 <= s <= largo

    def rectangulo(self, extension=True):
        """(x0, y0, x1, y1) del muro en planta, solo para ortogonales."""
        e2 = self.espesor / 2.0
        a = self.s0 - (self.extension[0] if extension else 0.0)
        b = self.s1 + (self.extension[1] if extension else 0.0)
        if self.orient == "h":
            return (a, self.eje - e2, b, self.eje + e2)
        return (self.eje - e2, a, self.eje + e2, b)


# --------------------------------------------------------------------- escala

def _factor_escala(datos, muros_brutos, avisos):
    """Metros por unidad del plano. Con "px" sale de las cotas de calibración."""
    unidades = str(datos.get("unidades", "m")).strip().lower()
    if unidades not in UNIDADES:
        raise ErrorPlano(f"Unidades «{unidades}» no reconocidas: usa px, cm, mm o m.")
    if UNIDADES[unidades] is not None:
        return UNIDADES[unidades], unidades, None

    calibracion = datos.get("calibracion") or []
    if isinstance(calibracion, dict):
        calibracion = [calibracion]
    if not calibracion:
        raise ErrorPlano(
            "Con unidades «px» hace falta al menos una cota de calibración: "
            'p. ej. {"muro": "M1", "medida": 9.4} con la longitud que indica el plano.'
        )
    por_id = {m["id"]: m for m in muros_brutos if m.get("id")}
    factores = []
    for k, cota in enumerate(calibracion, 1):
        medida = _numero(cota.get("medida"), f"calibracion[{k}].medida")
        if medida <= 0:
            raise ErrorPlano(f"La cota de calibración {k} debe medir más de 0 m.")
        if cota.get("muro") is not None:
            muro = por_id.get(str(cota["muro"]))
            if muro is None:
                raise ErrorPlano(f"La cota de calibración {k} cita el muro «{cota['muro']}», que no existe.")
            largo = _distancia(muro["inicio"], muro["fin"])
            if str(cota.get("referencia", "exterior")).lower() == "exterior":
                # La cota exterior de un muro de esquina a esquina incluye medio
                # espesor de cada muro que le llega: eje + espesor.
                largo += muro["espesor_bruto"] or 0.0
            descripcion = f"muro {cota['muro']}"
        else:
            largo = _distancia(_punto(cota.get("p1"), "p1"), _punto(cota.get("p2"), "p2"))
            descripcion = f"cota {k}"
        if largo <= 0:
            raise ErrorPlano(f"La cota de calibración {k} tiene longitud 0 en el dibujo.")
        factores.append((medida / largo, medida, descripcion))

    factor = statistics.median(f for f, _, _ in factores)
    desviacion = 0.0
    for f, medida, descripcion in factores:
        rel = abs(f - factor) / factor
        desviacion = max(desviacion, rel)
        if rel > TOL_DESVIACION_COTAS:
            avisos.append(
                f"La {descripcion} ({_m(medida)} m) no cuadra con las demás: con la "
                f"escala común mediría {_m(medida * factor / f)} m. Revisa si la leíste bien."
            )
    resumen = (
        f"1 px = {_m(factor * 100)} cm ({len(factores)} cota(s) de calibración, "
        f"desviación máxima {_porcentaje(desviacion)[1:]})"
    )
    return factor, unidades, resumen


# ------------------------------------------------------------- normalización

def normalizar(datos):
    """Valida y limpia un plano neutro. Devuelve (plano, informe_texto).

    Lanza ErrorPlano si falta algo imprescindible; todo lo corregible se
    corrige y queda anotado en los avisos del informe.
    """
    if not isinstance(datos, dict):
        raise ErrorPlano("El plano debe ser un objeto JSON con la clave «plantas».")
    plantas_brutas = datos.get("plantas")
    if not isinstance(plantas_brutas, list) or not plantas_brutas:
        raise ErrorPlano("El plano necesita «plantas»: una lista con al menos una planta.")

    plantas, lineas_informe = [], []
    nivel_siguiente = 0.0
    for numero, bruta in enumerate(plantas_brutas, 1):
        if not isinstance(bruta, dict):
            raise ErrorPlano(f"La planta {numero} debe ser un objeto.")
        # Cada planta puede venir de una imagen distinta (y con otra escala):
        # sus propias "unidades"/"calibracion" mandan sobre las globales.
        contexto = dict(datos)
        contexto.update({k: bruta[k] for k in ("unidades", "calibracion", "giro") if k in bruta})
        planta, texto = _normalizar_planta(bruta, numero, contexto, nivel_siguiente)
        plantas.append(planta)
        lineas_informe.append(texto)
        nivel_siguiente = planta["nivel"] + planta["altura"] + FORJADO_DEFECTO

    plano = {"plantas": plantas}
    return plano, "\n\n".join(lineas_informe)


def _muros_brutos(bruta, numero):
    muros = bruta.get("muros")
    if not isinstance(muros, list) or not muros:
        raise ErrorPlano(f"La planta {numero} no tiene «muros».")
    resultado = []
    for k, m in enumerate(muros, 1):
        if not isinstance(m, dict):
            raise ErrorPlano(f"El muro {k} de la planta {numero} debe ser un objeto.")
        espesor = m.get("espesor")
        resultado.append({
            "id": str(m.get("id") or f"M{k}"),
            "inicio": _punto(m.get("inicio"), f"muros[{k}].inicio"),
            "fin": _punto(m.get("fin"), f"muros[{k}].fin"),
            "espesor_bruto": None if espesor is None else _numero(espesor, f"muros[{k}].espesor"),
        })
    return resultado


def _normalizar_planta(bruta, numero, contexto, nivel_defecto):
    avisos = []
    nombre = str(bruta.get("nombre") or f"Planta {numero - 1}")
    nivel = _numero(bruta.get("nivel", nivel_defecto), "nivel")
    altura = _numero(bruta.get("altura", ALTURA_DEFECTO), "altura")
    if not 1.8 <= altura <= 8.0:
        avisos.append(f"Altura de planta {_m(altura)} m fuera de lo habitual: se usa {_m(ALTURA_DEFECTO)} m.")
        altura = ALTURA_DEFECTO

    brutos = _muros_brutos(bruta, numero)
    factor, unidades, resumen_escala = _factor_escala(contexto, brutos, avisos)
    invertir_y = unidades == "px"  # en una imagen la y crece hacia abajo
    # Giro del dibujo (el que mide plano_detectar_muros), en el mismo sentido en
    # que lo aplica PIL: girar las coordenadas originales lo endereza todo a la vez.
    giro = math.radians(_numero(contexto.get("giro", 0) or 0, "giro"))
    coseno, seno = math.cos(giro), math.sin(giro)

    def a_metros(p):
        x = p[0] * coseno + p[1] * seno
        y = -p[0] * seno + p[1] * coseno
        return (x * factor, (-y if invertir_y else y) * factor)

    def transformar(p):
        x, y = a_metros(p)
        return (round(x, 4), round(y, 4))

    muros = []
    for m in brutos:
        if m["espesor_bruto"] is None:
            espesor = ESPESOR_DEFECTO
        else:
            espesor = m["espesor_bruto"] * factor
        if not 0.04 <= espesor <= 1.0:
            avisos.append(f"Muro {m['id']}: espesor {_m(espesor)} m imposible; se usa {_m(ESPESOR_DEFECTO)} m.")
            espesor = ESPESOR_DEFECTO
        muro = _Muro([m["id"]], transformar(m["inicio"]), transformar(m["fin"]), espesor)
        if muro.largo() < 0.05:
            avisos.append(f"Muro {m['id']}: mide menos de 5 cm, se descarta.")
            continue
        muro.enderezar()
        muros.append(muro)
    if not muros:
        raise ErrorPlano(f"La planta {numero} se ha quedado sin muros válidos.")

    _alinear_ejes(muros)
    muros = _fundir_colineales(muros)

    huecos_brutos = bruta.get("huecos") or []
    for k, h in enumerate(huecos_brutos, 1):
        _asignar_hueco(h, k, muros, transformar, altura, avisos)

    _unir_extremos(muros)
    def a_unidades_plano(p):
        x, y = p[0] / factor, (-p[1] if invertir_y else p[1]) / factor
        return (x * coseno - y * seno, x * seno + y * coseno)

    _avisar_tramos_sueltos(muros, avisos, a_unidades_plano)
    muros_finales = _finalizar_muros(muros, altura, avisos)

    # Los cortes sin declarar se puentean al calcular estancias y huella: casi
    # siempre son un paso o una ventana, y dejarlos abiertos haría que el
    # "exterior" se colara dentro (la estancia no cerraría y la huella encogería).
    rejilla = Rejilla([m.rectangulo() for m in muros if m.ortogonal] + _puentes(muros))
    inclinados = [m for m in muros if not m.ortogonal]
    if inclinados:
        avisos.append(
            f"{len(inclinados)} muro(s) inclinado(s): no cuentan para cerrar estancias "
            "ni la huella; las estancias que toquen se calculan con su contorno declarado."
        )

    estancias = _estancias(bruta.get("estancias") or [], rejilla, transformar, avisos)

    huella = rejilla.contorno_exterior(rejilla.huella()) if len(muros) > len(inclinados) else None
    if huella is None:
        xs = [p[0] for m in muros for p in m.extremos_obra()]
        ys = [p[1] for m in muros for p in m.extremos_obra()]
        huella = [(min(xs), min(ys)), (max(xs), min(ys)), (max(xs), max(ys)), (min(xs), max(ys))]

    # Origen en la esquina exterior inferior izquierda del edificio ya limpio:
    # el modelo nace junto al origen del programa, y "desplazamiento" permite
    # alinear plantas que vienen de imágenes distintas.
    desplazamiento = _punto(bruta.get("desplazamiento", [0, 0]), "desplazamiento")
    dx = desplazamiento[0] - min(x for x, _ in huella)
    dy = desplazamiento[1] - min(y for _, y in huella)

    macizos = _macizos(muros)
    planta = {
        "nombre": nombre,
        "nivel": nivel,
        "altura": altura,
        "muros": muros_finales,
        "estancias": estancias,
        "huella": [(round(x, 4), round(y, 4)) for x, y in huella],
        "macizos": macizos,
        "lineas_planta": _lineas_planta(macizos),
        # Para volver de metros a la imagen original (la superposición de control).
        "transformacion": {"factor": factor, "invertir_y": invertir_y, "desplazamiento": (dx, dy),
                           "giro": math.degrees(giro)},
    }
    _desplazar(planta, dx, dy)
    return planta, _informe_planta(planta, resumen_escala, avisos)


def _desplazar(planta, dx, dy):
    """Traslada en planta todo lo que lleva coordenadas."""
    def mover(p):
        return None if p is None else (round(p[0] + dx, 4), round(p[1] + dy, 4))

    for m in planta["muros"]:
        for clave in ("inicio", "fin", "eje_inicio", "eje_fin"):
            m[clave] = mover(m[clave])
        for h in m["huecos"]:
            h["abre_hacia"] = mover(h["abre_hacia"])
    for e in planta["estancias"]:
        e["contorno"] = [mover(p) for p in e["contorno"]]
        e["centro"] = mover(e["centro"])
    planta["huella"] = [mover(p) for p in planta["huella"]]
    planta["lineas_planta"] = [(mover(a), mover(b)) for a, b in planta["lineas_planta"]]
    planta["macizos"] = [
        (round(x0 + dx, 4), round(y0 + dy, 4), round(x1 + dx, 4), round(y1 + dy, 4))
        for x0, y0, x1, y1 in planta["macizos"]
    ]


def _alinear_ejes(muros):
    """Agrupa los ejes paralelos casi coincidentes y los iguala.

    La media se pondera por longitud: un tabique corto se alinea con la fachada
    larga y no al revés.
    """
    for orient in ("h", "v"):
        grupo = sorted((m for m in muros if m.orient == orient), key=lambda m: m.eje)
        racimo = []
        for muro in grupo + [None]:
            if muro is not None and racimo and muro.eje - racimo[0].eje <= TOL_ALINEAR:
                racimo.append(muro)
                continue
            if racimo:
                peso = sum(m.largo() for m in racimo) or 1.0
                eje = sum(m.eje * m.largo() for m in racimo) / peso
                for m in racimo:
                    m.eje = round(eje, 4)
            racimo = [muro] if muro is not None else []


def _cubierto_por_perpendicular(muros, linea, desde, hasta):
    """¿El corte [desde, hasta] de una línea de muro lo tapa un muro perpendicular?

    Pasa en los DXF: la cara interior de una fachada se interrumpe en cada
    tabique, y emparejar caras deja la fachada partida justo bajo el tabique.
    """
    orient, eje = linea
    otra = "v" if orient == "h" else "h"
    for p in muros:
        if p.orient != otra or not p.s0 - 0.3 <= eje <= p.s1 + 0.3:
            continue
        if p.eje - p.espesor / 2 - 0.02 <= desde and hasta <= p.eje + p.espesor / 2 + 0.02:
            return True
    return False


def _fundir_colineales(muros):
    """Une tramos del mismo eje que se tocan, se solapan o los separa solo un tabique."""
    resultado = [m for m in muros if not m.ortogonal]
    lineas = {}
    for m in muros:
        if m.ortogonal:
            lineas.setdefault((m.orient, m.eje), []).append(m)
    for linea, tramos in lineas.items():
        tramos.sort(key=lambda m: m.s0)
        actual = tramos[0]
        for siguiente in tramos[1:]:
            mismo_espesor = abs(siguiente.espesor - actual.espesor) <= TOL_FUNDIR
            contiguos = siguiente.s0 <= actual.s1 + 0.02 or _cubierto_por_perpendicular(
                muros, linea, actual.s1, siguiente.s0
            )
            if contiguos and mismo_espesor:
                actual.s1 = max(actual.s1, siguiente.s1)
                actual.ids += siguiente.ids
                actual.huecos += siguiente.huecos
            else:
                resultado.append(actual)
                actual = siguiente
        resultado.append(actual)
    return resultado


def _perpendiculares(muros, muro):
    """Muros ortogonales perpendiculares a `muro` que cruzan su línea de eje."""
    otra = "v" if muro.orient == "h" else "h"
    return [
        p for p in muros
        if p.orient == otra and p.s0 - muro.espesor <= muro.eje <= p.s1 + muro.espesor
    ]


def _asignar_hueco(h, k, muros, transformar, altura, avisos):
    """Engancha un hueco a su muro, midiéndolo con el dibujo si es posible."""
    if not isinstance(h, dict):
        avisos.append(f"Hueco {k}: no es un objeto, se omite.")
        return
    tipo = str(h.get("tipo", "ventana")).lower()
    if tipo not in TIPOS_HUECO:
        avisos.append(f"Hueco {k}: tipo «{tipo}» desconocido, se trata como ventana.")
        tipo = "ventana"
    etiqueta = f"{tipo} {k}"
    try:
        centro = transformar(_punto(h.get("centro"), f"huecos[{k}].centro"))
    except ErrorPlano as exc:
        avisos.append(f"Hueco {etiqueta}: {exc} Se omite.")
        return
    ancho_leido = h.get("ancho")
    ancho_leido = None if ancho_leido is None else _numero(ancho_leido, f"huecos[{k}].ancho")
    extra = {
        "tipo": tipo,
        "alto": h.get("alto"),
        "antepecho": h.get("antepecho"),
        "abre_hacia": transformar(_punto(h["abre_hacia"], "abre_hacia")) if h.get("abre_hacia") else None,
        "etiqueta": etiqueta,
    }

    # 1) ¿Cae sobre un tramo de muro dibujado? Entonces es un hueco que el dibujo
    #    no interrumpe (ventana dibujada en macizo): se usa el ancho leído.
    sobre = []
    for m in muros:
        lateral, s, dentro = m.relacion(centro)
        if dentro and lateral <= max(m.espesor, 0.25):
            sobre.append((lateral, s, m))
    if sobre:
        _, s, muro = min(sobre, key=lambda t: t[0])
        if ancho_leido is None:
            avisos.append(f"Hueco {etiqueta}: sin ancho; se usa el habitual.")
            ancho_leido = 0.8 if tipo in ("puerta", "paso") else 1.2
        muro.huecos.append(dict(extra, s=s, ancho=ancho_leido))
        return

    # 2) ¿Cae en un hueco entre tramos de una misma línea de muro? Se mide el
    #    hueco real entre las caras que lo limitan y los tramos se completan.
    candidatos = []
    for m in muros:
        if not m.ortogonal:
            continue
        lateral, s, _ = m.relacion(centro)
        if lateral <= max(m.espesor, 0.25):
            candidatos.append((lateral, m))
    if not candidatos:
        avisos.append(f"Hueco {etiqueta}: no está sobre ningún muro, se omite.")
        return
    _, referencia = min(candidatos, key=lambda t: t[0])
    linea = [m for m in muros if m.orient == referencia.orient and m.eje == referencia.eje]
    s_c = centro[0] if referencia.orient == "h" else centro[1]

    izquierda = max((m for m in linea if m.s1 < s_c), key=lambda m: m.s1, default=None)
    derecha = min((m for m in linea if m.s0 > s_c), key=lambda m: m.s0, default=None)
    perpendiculares = _perpendiculares(muros, referencia)
    perp_izq = max((p for p in perpendiculares if p.eje < s_c), key=lambda p: p.eje, default=None)
    perp_der = min((p for p in perpendiculares if p.eje > s_c), key=lambda p: p.eje, default=None)

    limite_izq, por_izq = -math.inf, None
    if izquierda is not None:
        limite_izq, por_izq = izquierda.s1, "muro"
    if perp_izq is not None and perp_izq.eje + perp_izq.espesor / 2 > limite_izq:
        limite_izq, por_izq = perp_izq.eje + perp_izq.espesor / 2, "perp"
    limite_der, por_der = math.inf, None
    if derecha is not None:
        limite_der, por_der = derecha.s0, "muro"
    if perp_der is not None and perp_der.eje - perp_der.espesor / 2 < limite_der:
        limite_der, por_der = perp_der.eje - perp_der.espesor / 2, "perp"

    if por_izq is None or por_der is None:
        avisos.append(f"Hueco {etiqueta}: queda al final de un muro sin nada al otro lado, se omite.")
        return
    hueco_dibujo = limite_der - limite_izq
    if hueco_dibujo < 0.3:
        avisos.append(f"Hueco {etiqueta}: el hueco del dibujo mide solo {_m(hueco_dibujo)} m, se omite.")
        return

    if ancho_leido is None or 0.66 * hueco_dibujo <= ancho_leido <= 1.5 * hueco_dibujo:
        ancho, s = hueco_dibujo, (limite_izq + limite_der) / 2.0
        if ancho_leido is not None and abs(ancho_leido - hueco_dibujo) > 0.05:
            avisos.append(
                f"Hueco {etiqueta}: el dibujo mide {_m(hueco_dibujo)} m frente a los "
                f"{_m(ancho_leido)} m leídos; se usa la medida del dibujo."
            )
    else:
        # El hueco del dibujo es mucho mayor que lo leído (p. ej. un paso con
        # una puerta estrecha): se respeta lo leído, centrado y dentro del hueco.
        ancho = min(ancho_leido, hueco_dibujo)
        s = min(max(s_c, limite_izq + ancho / 2), limite_der - ancho / 2)

    # Completar el muro a través del hueco.
    if por_izq == "muro" and por_der == "muro":
        izquierda.s1 = derecha.s1
        izquierda.ids += derecha.ids
        izquierda.huecos += derecha.huecos
        muros.remove(derecha)
        destino = izquierda
    elif por_izq == "muro":
        izquierda.s1 = perp_der.eje
        destino = izquierda
    elif por_der == "muro":
        derecha.s0 = perp_izq.eje
        destino = derecha
    else:
        destino = _Muro([f"{etiqueta} (tramo)"], (0, 0), (0, 0), referencia.espesor)
        destino.orient, destino.eje = referencia.orient, referencia.eje
        destino.s0, destino.s1 = perp_izq.eje, perp_der.eje
        muros.append(destino)
    destino.huecos.append(dict(extra, s=s, ancho=ancho))


def _unir_extremos(muros):
    """Lleva cada extremo libre al eje del muro perpendicular que lo recibe.

    Tras alinear, en una esquina en L el muro horizontal se alarga hasta la cara
    exterior del vertical y el vertical se para en la cara del horizontal; en
    una T el muro que llega se para en la cara del que sigue. Resultado: cajas
    que encajan sin solaparse (sin parpadeos en 3D ni líneas dobles en 2D).
    """
    ortogonales = [m for m in muros if m.ortogonal]
    for _ in range(2):  # una segunda pasada estabiliza las esquinas mutuas
        for muro in ortogonales:
            for k in (0, 1):
                s_extremo = muro.s0 if k == 0 else muro.s1
                mejor = None
                for p in _perpendiculares(ortogonales, muro):
                    tolerancia = max(p.espesor, muro.espesor) * 0.75 + 0.05
                    distancia = abs(s_extremo - p.eje)
                    if distancia <= tolerancia and (mejor is None or distancia < mejor[0]):
                        mejor = (distancia, p)
                if mejor is None:
                    continue
                p = mejor[1]
                if k == 0:
                    muro.s0 = p.eje
                else:
                    muro.s1 = p.eje
                muro.unido[k] = True
                # ¿El otro muro también acaba aquí (esquina) o sigue (T)?
                esquina = min(abs(p.s0 - muro.eje), abs(p.s1 - muro.eje)) <= muro.espesor * 0.75 + 0.05
                if esquina:
                    muro.extension[k] = p.espesor / 2 if muro.orient == "h" else -p.espesor / 2
                else:
                    muro.extension[k] = -p.espesor / 2


def _tramos_por_linea(muros):
    lineas = {}
    for m in muros:
        if m.ortogonal:
            lineas.setdefault((m.orient, m.eje), []).append(m)
    for tramos in lineas.values():
        tramos.sort(key=lambda m: m.s0)
    return lineas


def _puentes(muros):
    """Rectángulos que cierran los cortes de hasta 4 m entre tramos colineales."""
    puentes = []
    for (orient, eje), tramos in _tramos_por_linea(muros).items():
        for a, b in zip(tramos, tramos[1:]):
            if 0 < b.s0 - a.s1 <= 4.0:
                e2 = min(a.espesor, b.espesor) / 2
                if orient == "h":
                    puentes.append((a.s1, eje - e2, b.s0, eje + e2))
                else:
                    puentes.append((eje - e2, a.s1, eje + e2, b.s0))
    return puentes


def _avisar_tramos_sueltos(muros, avisos, a_unidades_plano):
    """Huecos del dibujo entre tramos colineales que nadie declaró como hueco.

    El centro se da en las unidades del plano recibido (píxeles si venía en px)
    para que la IA pueda declararlo tal cual en un segundo intento.
    """
    for (orient, eje), tramos in _tramos_por_linea(muros).items():
        for a, b in zip(tramos, tramos[1:]):
            separacion = b.s0 - a.s1
            if 0.3 <= separacion <= 4.0:
                medio = (a.s1 + b.s0) / 2
                centro = (medio, eje) if orient == "h" else (eje, medio)
                x, y = a_unidades_plano(centro)
                avisos.append(
                    f"Entre los muros {a.ids[0]} y {b.ids[0]} queda un hueco de "
                    f"{_m(separacion)} m sin puerta ni ventana declarada (queda abierto); "
                    f"su centro está en [{x:.2f}, {y:.2f}] (unidades del plano)."
                )


def _finalizar_muros(muros, altura, avisos):
    """Pasa cada muro al formato de salida, con sus huecos en coordenadas de obra."""
    salida = []
    for muro in muros:
        inicio, fin = muro.extremos_obra()
        eje_inicio, eje_fin = muro.extremos_eje()
        largo_obra = _distancia(inicio, fin)
        huecos = []
        for h in sorted(muro.huecos, key=lambda h: h["s"]):
            alto_defecto, ante_defecto = _POR_DEFECTO_HUECO[h["tipo"]]
            alto = h.get("alto")
            ante = h.get("antepecho")
            ante = ante_defecto if ante is None else _numero(ante, "antepecho")
            if alto is None:
                alto = alto_defecto if alto_defecto is not None else altura - 0.25 - ante
            alto = _numero(alto, "alto")
            if ante + alto > altura - 0.05:
                alto = max(0.3, altura - 0.05 - ante)
                avisos.append(f"Hueco {h['etiqueta']}: más alto que la planta, se recorta a {_m(alto)} m.")
            if muro.ortogonal:
                a = h["s"] - h["ancho"] / 2 - (muro.s0 - muro.extension[0])
            else:
                a = h["s"] - h["ancho"] / 2
            a_max = largo_obra - h["ancho"] - 0.05
            if a_max < 0.05:
                avisos.append(f"Hueco {h['etiqueta']}: no cabe en su muro ({_m(largo_obra)} m), se omite.")
                continue
            if not 0.05 <= a <= a_max:
                a = min(max(a, 0.05), a_max)
            if huecos and a < huecos[-1]["a"] + huecos[-1]["ancho"] + 0.05:
                avisos.append(f"Hueco {h['etiqueta']}: se solapa con otro hueco del mismo muro, se omite.")
                continue
            huecos.append({
                "tipo": h["tipo"],
                "a": round(a, 4),
                "ancho": round(h["ancho"], 4),
                "alto": round(alto, 4),
                "antepecho": round(ante, 4),
                # Revit coloca la familia por su centro, medido desde el eje.
                "centro_eje": round(a + h["ancho"] / 2 - _retranqueo_inicio(muro), 4),
                "abre_hacia": h.get("abre_hacia"),
            })
        salida.append({
            "id": "+".join(muro.ids),
            "inicio": inicio,
            "fin": fin,
            "eje_inicio": eje_inicio,
            "eje_fin": eje_fin,
            "espesor": round(muro.espesor, 4),
            "ortogonal": muro.ortogonal,
            "huecos": huecos,
        })
    return salida


def _retranqueo_inicio(muro):
    """Distancia del arranque de obra al arranque del eje (0 en muros inclinados)."""
    return muro.extension[0] if muro.ortogonal else 0.0


def _estancias(brutas, rejilla, transformar, avisos):
    """Superficie útil de cada estancia, calculada con los muros reconstruidos."""
    estancias = []
    for k, e in enumerate(brutas, 1):
        if not isinstance(e, dict):
            continue
        nombre = str(e.get("nombre") or f"Estancia {k}")
        superficie_plano = e.get("superficie")
        superficie_plano = None if superficie_plano is None else _numero(superficie_plano, "superficie")
        contorno, superficie, cerrada = None, None, False
        if e.get("centro") is not None:
            centro = transformar(_punto(e["centro"], f"estancias[{k}].centro"))
            celdas, cerrada = rejilla.recinto(centro)
            if celdas and cerrada:
                contorno = rejilla.contorno_exterior(celdas)
                superficie = rejilla.area(celdas)
            elif not celdas:
                avisos.append(f"Estancia «{nombre}»: su punto cae dentro de un muro; muévelo al interior.")
            else:
                avisos.append(f"Estancia «{nombre}»: los muros no la cierran (¿falta un muro o una puerta?).")
        if contorno is None and e.get("contorno"):
            contorno = [transformar(_punto(p, "contorno")) for p in e["contorno"]]
            superficie = abs(area_poligono(contorno))
            cerrada = True
        if contorno is None:
            continue
        estancias.append({
            "nombre": nombre,
            "contorno": [(round(x, 4), round(y, 4)) for x, y in contorno],
            "superficie": round(superficie, 2),
            "superficie_plano": superficie_plano,
            "centro": _centro_rotulo(contorno),
        })
    return estancias


def _centro_rotulo(contorno):
    """Punto donde rotular la estancia: el centroide si cae dentro (si no, un vértice)."""
    area = area_poligono(contorno)
    if abs(area) < 1e-9:
        return contorno[0]
    n = len(contorno)
    cx = cy = 0.0
    for i in range(n):
        x0, y0 = contorno[i]
        x1, y1 = contorno[(i + 1) % n]
        cruz = x0 * y1 - x1 * y0
        cx += (x0 + x1) * cruz
        cy += (y0 + y1) * cruz
    centro = (cx / (6 * area), cy / (6 * area))
    if punto_en_poligono(centro, contorno):
        return (round(centro[0], 4), round(centro[1], 4))
    x0, y0 = contorno[0]
    return (x0 + 0.5, y0 + 0.5)


def _macizos(muros):
    """Rectángulos de muro macizo en el plano de corte (los huecos, abiertos)."""
    rects = []
    for m in muros:
        if not m.ortogonal:
            continue
        x0, y0, x1, y1 = m.rectangulo()
        inicio = m.s0 - m.extension[0]
        cortes = sorted(
            (h["s"] - h["ancho"] / 2, h["s"] + h["ancho"] / 2) for h in m.huecos
        )
        cursor = inicio
        fin = m.s1 + m.extension[1]
        for a, b in cortes + [(fin, fin)]:
            if a > cursor + 1e-6:
                if m.orient == "h":
                    rects.append((cursor, y0, a, y1))
                else:
                    rects.append((x0, cursor, x1, a))
            cursor = max(cursor, b)
    return [tuple(round(v, 4) for v in r) for r in rects]


def _lineas_planta(rects):
    """Líneas de la planta 2D: el borde de la unión de los macizos."""
    if not rects:
        return []
    rejilla = Rejilla(rects)
    ocupadas = {
        (i, j) for i in range(rejilla.nx) for j in range(rejilla.ny) if rejilla.ocupada[i][j]
    }
    return [
        ((round(a[0], 4), round(a[1], 4)), (round(b[0], 4), round(b[1], 4)))
        for a, b in rejilla.lineas_borde(ocupadas)
    ]


def _informe_planta(planta, resumen_escala, avisos):
    muros = planta["muros"]
    huecos = [h for m in muros for h in m["huecos"]]
    cuenta = {t: sum(1 for h in huecos if h["tipo"] == t) for t in TIPOS_HUECO}
    xs = [p[0] for p in planta["huella"]]
    ys = [p[1] for p in planta["huella"]]
    lineas = [
        f"{planta['nombre']} (nivel {_m(planta['nivel'])} m, altura {_m(planta['altura'])} m)",
    ]
    if resumen_escala:
        lineas.append(f"Escala: {resumen_escala}.")
    lineas.append(
        f"{len(muros)} muros, {len(huecos)} huecos ("
        + ", ".join(f"{n} {t}" for t, n in cuenta.items() if n)
        + f"), {len(planta['estancias'])} estancias."
    )
    lineas.append(
        f"Huella: {_m(max(xs) - min(xs))} × {_m(max(ys) - min(ys))} m, "
        f"{_m(abs(area_poligono(planta['huella'])))} m² construidos. "
        f"Contorno: {[(round(x, 2), round(y, 2)) for x, y in planta['huella']]}"
    )
    if planta["estancias"]:
        lineas.append("Estancias (superficie útil reconstruida / la del plano):")
        for e in planta["estancias"]:
            if e["superficie_plano"]:
                diferencia = (e["superficie"] - e["superficie_plano"]) / e["superficie_plano"]
                marca = "✔" if abs(diferencia) <= TOL_SUPERFICIE else "✘ REVISA"
                lineas.append(
                    f"  · {e['nombre']}: {_m(e['superficie'])} m² / {_m(e['superficie_plano'])} m² "
                    f"({_porcentaje(diferencia)}) {marca}"
                )
            else:
                lineas.append(f"  · {e['nombre']}: {_m(e['superficie'])} m² (el plano no indica superficie)")
    if avisos:
        lineas.append("Avisos:")
        lineas.extend(f"  - {a}" for a in avisos)
    return "\n".join(lineas)
