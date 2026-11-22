"""Geometría en planta sobre una rejilla comprimida.

Los planos de vivienda son casi siempre ortogonales, y eso permite resolver con
exactitud (sin librerías de geometría) tres preguntas que la reconstrucción
necesita: qué recinto cerrado contiene un punto (las estancias y su superficie
útil), cuál es la huella del edificio (para la solera y los forjados) y qué
contorno dibuja la unión de muros en planta (las líneas de un plano de AutoCAD).

La rejilla se construye con las coordenadas de todas las caras de los muros
("compresión de coordenadas"): cada celda está entera dentro o entera fuera de
cada rectángulo, así que las superficies que salen de sumar celdas son exactas,
no una aproximación por píxeles.
"""

import bisect
from collections import deque

# Las coordenadas se redondean a la décima de milímetro para que dos caras que
# coinciden "a ojo" (0.1 y 0.1000000002) caigan en la misma línea de rejilla.
_DECIMALES = 4


def area_poligono(puntos) -> float:
    """Superficie con signo (positiva si el contorno va en sentido antihorario)."""
    n = len(puntos)
    return sum(
        puntos[i][0] * puntos[(i + 1) % n][1] - puntos[(i + 1) % n][0] * puntos[i][1]
        for i in range(n)
    ) / 2.0


def punto_en_poligono(punto, poligono) -> bool:
    """Prueba del rayo: cuenta cuántas aristas cruza una semirrecta horizontal."""
    x, y = punto
    dentro = False
    n = len(poligono)
    for i in range(n):
        x0, y0 = poligono[i]
        x1, y1 = poligono[(i + 1) % n]
        if (y0 > y) != (y1 > y):
            x_corte = x0 + (y - y0) * (x1 - x0) / (y1 - y0)
            if x < x_corte:
                dentro = not dentro
    return dentro


class Rejilla:
    """Rejilla comprimida a partir de rectángulos alineados con los ejes.

    `rectangulos` es una lista de (x0, y0, x1, y1). Se añade un margen alrededor
    para que exista siempre un "exterior" desde el que inundar.
    """

    def __init__(self, rectangulos, margen=1.0):
        rects = [tuple(round(v, _DECIMALES) for v in r) for r in rectangulos]
        xs = {r[0] for r in rects} | {r[2] for r in rects}
        ys = {r[1] for r in rects} | {r[3] for r in rects}
        if not xs:
            xs, ys = {0.0, 1.0}, {0.0, 1.0}
        xs |= {min(xs) - margen, max(xs) + margen}
        ys |= {min(ys) - margen, max(ys) + margen}
        self.xs = sorted(xs)
        self.ys = sorted(ys)
        self.nx = len(self.xs) - 1
        self.ny = len(self.ys) - 1
        self.ocupada = [[False] * self.ny for _ in range(self.nx)]
        for r in rects:
            self.marcar(r)

    def marcar(self, rect, valor=True):
        """Marca las celdas cubiertas por `rect` (cuyas caras ya son líneas de rejilla)."""
        x0, y0, x1, y1 = (round(v, _DECIMALES) for v in rect)
        i0 = bisect.bisect_left(self.xs, x0)
        i1 = bisect.bisect_left(self.xs, x1)
        j0 = bisect.bisect_left(self.ys, y0)
        j1 = bisect.bisect_left(self.ys, y1)
        for i in range(i0, i1):
            columna = self.ocupada[i]
            for j in range(j0, j1):
                columna[j] = valor

    def celda_de(self, punto):
        """Índices (i, j) de la celda que contiene el punto, o None si cae fuera."""
        x, y = punto
        i = bisect.bisect_right(self.xs, x) - 1
        j = bisect.bisect_right(self.ys, y) - 1
        if 0 <= i < self.nx and 0 <= j < self.ny:
            return i, j
        return None

    def area_celda(self, i, j) -> float:
        return (self.xs[i + 1] - self.xs[i]) * (self.ys[j + 1] - self.ys[j])

    def _inundar(self, inicio, libre):
        """Celdas conectadas (4-vecindad) a `inicio` que cumplen `libre(i, j)`."""
        visto = {inicio}
        cola = deque([inicio])
        while cola:
            i, j = cola.popleft()
            for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                v = (i + di, j + dj)
                if v in visto or not (0 <= v[0] < self.nx and 0 <= v[1] < self.ny):
                    continue
                if libre(*v):
                    visto.add(v)
                    cola.append(v)
        return visto

    def recinto(self, punto):
        """Recinto libre que contiene `punto`.

        Devuelve (celdas, cerrado). `cerrado` es False si el recinto llega al
        borde de la rejilla, es decir, si los muros no lo encierran.
        """
        celda = self.celda_de(punto)
        if celda is None or self.ocupada[celda[0]][celda[1]]:
            return set(), False
        celdas = self._inundar(celda, lambda i, j: not self.ocupada[i][j])
        cerrado = not any(
            i in (0, self.nx - 1) or j in (0, self.ny - 1) for i, j in celdas
        )
        return celdas, cerrado

    def huella(self):
        """Todo lo que no es exterior: muros + recintos encerrados por ellos."""
        exterior = self._inundar((0, 0), lambda i, j: not self.ocupada[i][j])
        return {
            (i, j) for i in range(self.nx) for j in range(self.ny) if (i, j) not in exterior
        }

    def contornos(self, celdas):
        """Contornos cerrados de un conjunto de celdas, simplificados.

        Devuelve una lista de polígonos [(x, y), …]; el exterior va en sentido
        antihorario (área positiva) y los patios interiores en horario.
        """
        # Aristas dirigidas con la región a la izquierda, en índices de rejilla
        # (enteros) para no depender de comparar coordenadas en coma flotante.
        siguientes = {}
        for i, j in celdas:
            if (i, j - 1) not in celdas:
                siguientes.setdefault((i, j), []).append((i + 1, j))
            if (i + 1, j) not in celdas:
                siguientes.setdefault((i + 1, j), []).append((i + 1, j + 1))
            if (i, j + 1) not in celdas:
                siguientes.setdefault((i + 1, j + 1), []).append((i, j + 1))
            if (i - 1, j) not in celdas:
                siguientes.setdefault((i, j + 1), []).append((i, j))

        poligonos = []
        while siguientes:
            inicio = next(iter(siguientes))
            vertices = [inicio]
            actual = inicio
            while True:
                destinos = siguientes.get(actual)
                if not destinos:
                    break
                siguiente = destinos.pop()
                if not destinos:
                    del siguientes[actual]
                if siguiente == inicio:
                    break
                vertices.append(siguiente)
                actual = siguiente
            puntos = _sin_colineales([(self.xs[i], self.ys[j]) for i, j in vertices])
            if len(puntos) >= 3:
                poligonos.append(puntos)
        return poligonos

    def contorno_exterior(self, celdas):
        """El contorno de mayor superficie de `celdas` (sin patios), o None."""
        poligonos = [p for p in self.contornos(celdas) if area_poligono(p) > 0]
        return max(poligonos, key=area_poligono) if poligonos else None

    def area(self, celdas) -> float:
        return sum(self.area_celda(i, j) for i, j in celdas)

    def lineas_borde(self, celdas):
        """Segmentos del borde de la región, fusionados en tramos rectos largos.

        Es el "dibujo en planta" de la unión de muros: una sola línea donde dos
        muros se tocan, en vez de los contornos solapados de cada rectángulo.
        """
        horizontales = {}  # j → lista de (i0, i1)
        verticales = {}    # i → lista de (j0, j1)
        for i, j in celdas:
            if (i, j - 1) not in celdas:
                horizontales.setdefault(j, []).append((i, i + 1))
            if (i, j + 1) not in celdas:
                horizontales.setdefault(j + 1, []).append((i, i + 1))
            if (i - 1, j) not in celdas:
                verticales.setdefault(i, []).append((j, j + 1))
            if (i + 1, j) not in celdas:
                verticales.setdefault(i + 1, []).append((j, j + 1))
        segmentos = []
        for j, tramos in horizontales.items():
            for a, b in _fusionar_tramos(tramos):
                segmentos.append(((self.xs[a], self.ys[j]), (self.xs[b], self.ys[j])))
        for i, tramos in verticales.items():
            for a, b in _fusionar_tramos(tramos):
                segmentos.append(((self.xs[i], self.ys[a]), (self.xs[i], self.ys[b])))
        return segmentos


def _fusionar_tramos(tramos):
    """Une intervalos enteros contiguos: [(0,1), (1,2), (4,5)] → [(0,2), (4,5)]."""
    fusionados = []
    for a, b in sorted(tramos):
        if fusionados and a <= fusionados[-1][1]:
            fusionados[-1] = (fusionados[-1][0], max(b, fusionados[-1][1]))
        else:
            fusionados.append((a, b))
    return fusionados


def _sin_colineales(puntos):
    """Quita los vértices intermedios de tramos rectos (la rejilla los deja en cada celda)."""
    resultado = []
    n = len(puntos)
    for k in range(n):
        previo, actual, siguiente = puntos[k - 1], puntos[k], puntos[(k + 1) % n]
        cruz = (actual[0] - previo[0]) * (siguiente[1] - actual[1]) - (
            actual[1] - previo[1]
        ) * (siguiente[0] - actual[0])
        if abs(cruz) > 1e-12:
            resultado.append(actual)
    return resultado
