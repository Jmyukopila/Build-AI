"""Planos → modelo: de un plano (imagen, PDF o DXF) a Blender, AutoCAD, SketchUp y Revit.

La promesa de la función es la fidelidad, así que las pruebas comprueban medidas,
no solo que "algo" se construya: con un plano de geometría conocida, la cadena
detector → normalizador debe devolver exactamente las superficies y huecos
dibujados. El código generado para cada programa se ejecuta contra dobles que
registran las llamadas (salvo el Ruby de SketchUp, que se revisa como texto).

    python -m unittest tests.test_planos
"""

import ast
import math
import base64
import io
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

import ezdxf
from PIL import Image, ImageDraw

from buildai import agent, main
from buildai.planos import constructores, detector, herramientas, importar, modelo
from buildai.planos.modelo import ErrorPlano, normalizar
from buildai.providers.base import LlamadaHerramienta, RespuestaLLM
from tests.dobles import ConectorFalso, ProveedorFalso

PX_POR_M = 50

# Casa de 10,2 × 8,2 m a caras exteriores, muros de 20 cm, tabique de 10 cm en
# x = 6,0-6,1 y una puerta de 90 cm en la fachada sur (x = 4,0-4,9). Superficies
# útiles exactas: salón 5,8 × 7,8 = 45,24 m²; dormitorio 3,9 × 7,8 = 30,42 m².
RECTANGULOS_CASA = [
    (0, 0, 10.2, 0.2), (0, 8.0, 4.0, 8.2), (4.9, 8.0, 10.2, 8.2),
    (0, 0, 0.2, 8.2), (10.0, 0, 10.2, 8.2), (6.0, 0.2, 6.1, 8.0),
]
SALON, DORMITORIO = 45.24, 30.42


def imagen_casa(rellenos=True, origen=(100, 80)):
    """PNG de la casa: muros macizos (o solo sus caras), más ruido de cotas y texto."""
    ox, oy = origen
    imagen = Image.new("L", (700, 600), 255)
    lienzo = ImageDraw.Draw(imagen)
    for x0, y0, x1, y1 in RECTANGULOS_CASA:
        caja = (round(ox + x0 * PX_POR_M), round(oy + y0 * PX_POR_M),
                round(ox + x1 * PX_POR_M) - 1, round(oy + y1 * PX_POR_M) - 1)
        if rellenos:
            lienzo.rectangle(caja, fill=0)
        else:
            lienzo.rectangle(caja, outline=0, width=2)
    lienzo.line((ox, oy - 30, ox + 510, oy - 30), fill=0, width=1)   # línea de cota
    lienzo.text((260, 300), "SALON 45,24 m2", fill=0)
    lienzo.rectangle((150, 150, 250, 200), outline=0)                 # mesa
    salida = io.BytesIO()
    imagen.save(salida, "PNG")
    return salida.getvalue()


def foto_vivienda_en_l():
    """Plano "de verdad": vivienda en L con muros grises de 30 cm y tabiques de 10 cm
    alineados por la cara, ventanas dibujadas con tres líneas finas, arcos de puerta,
    mobiliario, cotas, iluminación desigual, ruido, 1,2° de giro y JPEG.

    Superficies útiles exactas: salón 3,7×5,7 = 21,09; cocina y dormitorio
    3,9×5,7 = 22,23; dormitorio 2 4,7×3,8 = 17,86 m².
    """
    import numpy as np

    escala, ox, oy = 60, 120, 100
    imagen = Image.new("L", (1100, 900), 255)
    lienzo = ImageDraw.Draw(imagen)

    def px(x, y):
        return (round(ox + x * escala), round(oy + (10.2 - y) * escala))

    def caja(x0, y0, x1, y1, relleno=110):
        a, b = px(x0, y1), px(x1, y0)
        lienzo.rectangle((a[0], a[1], b[0] - 1, b[1] - 1), fill=relleno)

    for r in [(0, 0, 12.3, 0.3), (0, 0, 0.3, 10.2), (12.0, 0, 12.3, 6.3), (5.3, 6.0, 12.3, 6.3),
              (5.0, 6.0, 5.3, 10.2), (0, 9.9, 5.3, 10.2), (4.0, 0.3, 4.1, 6.0), (8.0, 0.3, 8.1, 6.0),
              (0.3, 6.0, 5.0, 6.1)]:
        caja(*r)
    huecos = [((1.5, 0, 3.0, 0.3), True), ((5.0, 0, 5.9, 0.3), False), ((9.5, 0, 10.7, 0.3), True),
              ((4.0, 2.5, 4.1, 3.3), False), ((8.0, 3.0, 8.1, 3.8), False), ((2.0, 6.0, 2.8, 6.1), False),
              ((1.5, 9.9, 3.5, 10.2), True)]
    for (x0, y0, x1, y1), ventana in huecos:
        caja(x0, y0, x1, y1, relleno=255)
        if ventana:
            a, b = px(x0, y1), px(x1, y0)
            for f in (0.0, 0.5, 1.0):
                yy = round(a[1] + (b[1] - a[1] - 1) * f)
                lienzo.line((a[0], yy, b[0] - 1, yy), fill=60, width=1)
    for cx, cy, r, a0, a1 in [(5.0, 0.3, 0.9, 270, 360), (4.05, 2.5, 0.8, 0, 90), (8.05, 3.0, 0.8, 180, 270)]:
        c = px(cx, cy)
        lienzo.arc((c[0] - r * escala, c[1] - r * escala, c[0] + r * escala, c[1] + r * escala), a0, a1, fill=0)
    lienzo.rectangle((*px(9, 4), *px(10.5, 1.5)), outline=0)
    lienzo.line((px(0, -0.6), px(12.3, -0.6)), fill=0)
    lienzo.text(px(6, -0.5), "12,30", fill=0)
    for nombre, x, y in [("SALON", 2, 3), ("COCINA", 6, 3), ("DORMITORIO", 10, 4), ("DORM. 2", 2.5, 8)]:
        lienzo.text(px(x, y), nombre, fill=0)
    valores = np.asarray(imagen).astype(float) * np.linspace(0.75, 1.0, 1100)[None, :]
    valores += np.random.default_rng(1).normal(0, 6, valores.shape)
    foto = Image.fromarray(np.clip(valores, 0, 255).astype(np.uint8))
    foto = foto.rotate(-1.2, resample=Image.BICUBIC, expand=True, fillcolor=235).convert("RGB")
    salida = io.BytesIO()
    foto.save(salida, "JPEG", quality=75)
    return salida.getvalue()


def plano_desde_deteccion(deteccion, huecos=None, estancias=None):
    return {
        "unidades": "px",
        "calibracion": [{"muro": "H1", "medida": 10.2, "referencia": "exterior"}],
        "plantas": [{
            "nombre": "Planta baja",
            "muros": [
                {"id": s["id"], "inicio": s["inicio"], "fin": s["fin"], "espesor": s["espesor"]}
                for s in deteccion["muros"]
            ],
            "huecos": huecos if huecos is not None else [{"tipo": "puerta", "centro": [322, 486], "ancho": 0.9}],
            "estancias": estancias if estancias is not None else [
                {"nombre": "Salón", "centro": [250, 300], "superficie": SALON},
                {"nombre": "Dormitorio", "centro": [500, 300], "superficie": DORMITORIO},
            ],
        }],
    }


def plano_metros():
    """La misma casa, en metros, tal como la escribiría la IA leyendo cotas."""
    return {
        "unidades": "m",
        "plantas": [{
            "nombre": "Planta baja",
            "muros": [
                {"id": "S1", "inicio": [0.1, 0.1], "fin": [4.0, 0.1], "espesor": 0.2},
                {"id": "S2", "inicio": [4.9, 0.1], "fin": [10.1, 0.1], "espesor": 0.2},
                {"id": "N", "inicio": [0.1, 8.1], "fin": [10.1, 8.1], "espesor": 0.2},
                {"id": "O", "inicio": [0.1, 0.1], "fin": [0.1, 8.1], "espesor": 0.2},
                {"id": "E", "inicio": [10.1, 0.1], "fin": [10.1, 8.1], "espesor": 0.2},
                {"id": "T", "inicio": [6.05, 0.1], "fin": [6.05, 8.1], "espesor": 0.1},
            ],
            "huecos": [
                {"tipo": "puerta", "centro": [4.45, 0.1], "ancho": 0.9, "abre_hacia": [4.45, 2.0]},
                {"tipo": "ventana", "centro": [3.0, 8.1], "ancho": 1.5},
                {"tipo": "puerta", "centro": [6.05, 4.0], "ancho": 0.8},
            ],
            "estancias": [
                {"nombre": "Salón", "centro": [3.0, 4.0], "superficie": SALON},
                {"nombre": "Dormitorio", "centro": [8.0, 4.0], "superficie": DORMITORIO},
            ],
        }],
    }


def superficies(plano):
    return {e["nombre"]: e["superficie"] for e in plano["plantas"][0]["estancias"]}


# ------------------------------------------------------------- normalizador

class TestNormalizador(unittest.TestCase):
    def test_superficies_exactas_y_esquinas_cerradas(self):
        plano, informe = normalizar(plano_metros())
        self.assertEqual(superficies(plano), {"Salón": SALON, "Dormitorio": DORMITORIO})
        huella = plano["plantas"][0]["huella"]
        self.assertEqual(sorted(huella), sorted([(0.0, 0.0), (10.2, 0.0), (10.2, 8.2), (0.0, 8.2)]))
        self.assertIn("✔", informe)
        self.assertNotIn("✘", informe)

    def test_la_puerta_entre_dos_tramos_se_mide_en_el_dibujo_y_los_une(self):
        plano, _ = normalizar(plano_metros())
        sur = next(m for m in plano["plantas"][0]["muros"] if "S1" in m["id"])
        self.assertIn("S2", sur["id"], "los dos tramos de la fachada deben fundirse en un muro")
        (puerta,) = sur["huecos"]
        self.assertEqual(puerta["ancho"], 0.9)
        self.assertAlmostEqual(sur["inicio"][0] + puerta["a"], 4.0, places=3)

    def test_ancho_leido_distinto_al_dibujo_avisa_y_manda_el_dibujo(self):
        datos = plano_metros()
        datos["plantas"][0]["huecos"][0]["ancho"] = 0.8
        plano, informe = normalizar(datos)
        sur = next(m for m in plano["plantas"][0]["muros"] if "S1" in m["id"])
        self.assertEqual(sur["huecos"][0]["ancho"], 0.9)
        self.assertIn("se usa la medida del dibujo", informe)

    def test_hueco_sobre_muro_macizo_usa_el_ancho_leido(self):
        plano, _ = normalizar(plano_metros())
        norte = next(m for m in plano["plantas"][0]["muros"] if m["id"] == "N")
        (ventana,) = norte["huecos"]
        self.assertEqual((ventana["tipo"], ventana["ancho"], ventana["antepecho"]), ("ventana", 1.5, 0.9))
        # Centrada en x = 3,0 (en el sistema ya trasladado, +0,0: la cara exterior era 0).
        self.assertAlmostEqual(norte["inicio"][0] + ventana["a"] + 0.75, 3.0, places=3)

    def test_union_en_t_sin_solapes(self):
        plano, _ = normalizar(plano_metros())
        tabique = next(m for m in plano["plantas"][0]["muros"] if m["id"] == "T")
        # Se para en la cara interior de las fachadas (0,2 y 8,0), no en su eje.
        self.assertEqual((tabique["inicio"][1], tabique["fin"][1]), (0.2, 8.0))

    def test_calibracion_en_px_con_una_cota_mal_leida(self):
        datos = {
            "unidades": "px",
            "calibracion": [
                {"p1": [0, 0], "p2": [510, 0], "medida": 10.2},
                {"p1": [0, 0], "p2": [0, 410], "medida": 8.2},
                {"p1": [0, 0], "p2": [100, 0], "medida": 2.6},   # mal leída: son 2,0 m
            ],
            "plantas": [{"muros": [
                {"id": "S", "inicio": [5, 405], "fin": [505, 405], "espesor": 10},
                {"id": "N", "inicio": [5, 5], "fin": [505, 5], "espesor": 10},
                {"id": "O", "inicio": [5, 5], "fin": [5, 405], "espesor": 10},
                {"id": "E", "inicio": [505, 5], "fin": [505, 405], "espesor": 10},
            ]}],
        }
        plano, informe = normalizar(datos)
        self.assertAlmostEqual(plano["plantas"][0]["transformacion"]["factor"], 0.02)
        self.assertIn("La cota 3 (2,60 m) no cuadra", informe)

    def test_la_y_de_la_imagen_se_invierte(self):
        datos = {
            "unidades": "px",
            "calibracion": [{"p1": [0, 0], "p2": [100, 0], "medida": 2.0}],
            "plantas": [{"muros": [{"id": "A", "inicio": [0, 500], "fin": [400, 500], "espesor": 10},
                                   {"id": "B", "inicio": [0, 100], "fin": [400, 100], "espesor": 10}]}],
        }
        plano, _ = normalizar(datos)
        a = next(m for m in plano["plantas"][0]["muros"] if m["id"] == "A")
        b = next(m for m in plano["plantas"][0]["muros"] if m["id"] == "B")
        self.assertLess(a["inicio"][1], b["inicio"][1], "lo de abajo en la imagen queda al sur")

    def test_estancia_sin_cerrar_avisa(self):
        datos = plano_metros()
        datos["plantas"][0]["muros"] = [m for m in datos["plantas"][0]["muros"] if m["id"] != "E"]
        _, informe = normalizar(datos)
        self.assertIn("los muros no la cierran", informe)

    def test_hueco_lejos_de_cualquier_muro_se_omite(self):
        datos = plano_metros()
        datos["plantas"][0]["huecos"].append({"tipo": "ventana", "centro": [3.0, 4.0], "ancho": 1.0})
        _, informe = normalizar(datos)
        self.assertIn("no está sobre ningún muro", informe)

    def test_hueco_sin_declarar_se_avisa_con_su_posicion(self):
        datos = plano_metros()
        datos["plantas"][0]["huecos"] = datos["plantas"][0]["huecos"][1:]
        _, informe = normalizar(datos)
        self.assertIn("sin puerta ni ventana declarada", informe)
        self.assertIn("[4.45, 0.10]", informe)
        self.assertNotIn("no la cierran", informe, "un corte sin declarar no abre la estancia")
        self.assertIn("83,64 m² construidos", informe, "ni encoge la huella")

    def test_errores_claros(self):
        with self.assertRaisesRegex(ErrorPlano, "plantas"):
            normalizar({})
        with self.assertRaisesRegex(ErrorPlano, "calibración"):
            normalizar({"unidades": "px", "plantas": [{"muros": [{"inicio": [0, 0], "fin": [9, 0]}]}]})
        with self.assertRaisesRegex(ErrorPlano, "punto"):
            normalizar({"plantas": [{"muros": [{"inicio": "0,0", "fin": [9, 0]}]}]})

    def test_varias_plantas_apilan_niveles(self):
        datos = plano_metros()
        datos["plantas"].append(dict(datos["plantas"][0], nombre="Planta primera"))
        plano, _ = normalizar(datos)
        self.assertEqual([p["nivel"] for p in plano["plantas"]], [0.0, 3.0])


# ----------------------------------------------------------------- detector

class TestDetector(unittest.TestCase):
    def test_mide_la_casa_al_pixel_y_las_superficies_salen_exactas(self):
        deteccion = detector.detectar_muros(imagen_casa())
        self.assertEqual(len(deteccion["muros"]), 6, detector.resumen_texto(deteccion))
        self.assertEqual(deteccion["espesor_px"], 10)
        h1 = next(s for s in deteccion["muros"] if s["id"] == "H1")
        self.assertEqual((h1["inicio"], h1["fin"]), ((105.0, 85.0), (605.0, 85.0)), "eje a eje")
        plano, informe = normalizar(plano_desde_deteccion(deteccion))
        self.assertEqual(superficies(plano), {"Salón": SALON, "Dormitorio": DORMITORIO}, informe)

    def test_conserva_el_tabique_fino_y_borra_textos_y_cotas(self):
        deteccion = detector.detectar_muros(imagen_casa())
        espesores = sorted(s["espesor"] for s in deteccion["muros"])
        self.assertEqual(espesores[0], 5.0, "el tabique de 10 cm (5 px) debe sobrevivir")

    def test_encuentra_el_corte_de_la_puerta(self):
        deteccion = detector.detectar_muros(imagen_casa())
        (corte,) = deteccion["huecos"]
        self.assertEqual((corte["centro"], corte["ancho"]), ((322.5, 485.0), 45.0))

    def test_muros_dibujados_solo_con_sus_caras(self):
        deteccion = detector.detectar_muros(imagen_casa(rellenos=False), modo="hueco")
        plano, informe = normalizar(plano_desde_deteccion(deteccion))
        for nombre, esperada in (("Salón", SALON), ("Dormitorio", DORMITORIO)):
            self.assertAlmostEqual(superficies(plano)[nombre], esperada, delta=esperada * 0.03, msg=informe)

    def test_plano_escaneado_torcido_y_en_jpeg(self):
        """Un escaneo real nunca está recto: 2,5° rompen las bandas si no se endereza."""
        angulo = 2.5
        girada = Image.open(io.BytesIO(imagen_casa())).rotate(
            angulo, resample=Image.BICUBIC, expand=True, fillcolor=255).convert("RGB")
        jpeg = io.BytesIO()
        girada.save(jpeg, "JPEG", quality=80)
        deteccion = detector.detectar_muros(jpeg.getvalue())
        self.assertAlmostEqual(deteccion["giro"], -angulo, delta=0.1)
        self.assertIn("girado", detector.resumen_texto(deteccion))

        # Los centros que vería el modelo, en la imagen girada.
        r = math.radians(angulo)

        def en_girada(p):
            x, y = p[0] - 350, p[1] - 300
            return [x * math.cos(r) + y * math.sin(r) + girada.width / 2,
                    -x * math.sin(r) + y * math.cos(r) + girada.height / 2]

        plano = plano_desde_deteccion(
            deteccion,
            huecos=[{"tipo": "puerta", "centro": en_girada((322, 486)), "ancho": 0.9}],
            estancias=[{"nombre": "Salón", "centro": en_girada((250, 300)), "superficie": SALON},
                       {"nombre": "Dormitorio", "centro": en_girada((500, 300)), "superficie": DORMITORIO}],
        )
        plano["giro"] = deteccion["giro"]
        normalizado, informe = normalizar(plano)
        for nombre, esperada in (("Salón", SALON), ("Dormitorio", DORMITORIO)):
            self.assertAlmostEqual(superficies(normalizado)[nombre], esperada, delta=0.1, msg=informe)
        (puerta,) = [h for m in normalizado["plantas"][0]["muros"] for h in m["huecos"]]
        self.assertAlmostEqual(puerta["ancho"], 0.9, delta=0.03)

    def test_vivienda_realista_en_l(self):
        deteccion = detector.detectar_muros(foto_vivienda_en_l())
        self.assertEqual(len(deteccion["muros"]), 16, "fachadas, tabiques y tramos entre huecos")
        anchos = sorted(round(h["ancho"]) for h in deteccion["huecos"])
        self.assertEqual(anchos, [48, 48, 48, 54, 72, 90, 120], "3 puertas de 0,8, una de 0,9 y 3 ventanas")
        tipos = ["ventana", "puerta", "ventana", "puerta", "ventana", "puerta", "puerta"]
        plano = {
            "unidades": "px", "giro": deteccion["giro"],
            "calibracion": [{"muro": "V1", "medida": 10.2, "referencia": "exterior"}],
            "plantas": [{
                "muros": [{"id": s["id"], "inicio": s["inicio"], "fin": s["fin"], "espesor": s["espesor"]}
                          for s in deteccion["muros"]],
                "huecos": [{"tipo": t, "centro": h["centro"]} for t, h in zip(tipos, deteccion["huecos"])],
                "estancias": [
                    {"nombre": "Salón", "centro": [255, 530], "superficie": 21.09},
                    {"nombre": "Cocina", "centro": [490, 540], "superficie": 22.23},
                    {"nombre": "Dormitorio", "centro": [735, 540], "superficie": 22.23},
                    {"nombre": "Dormitorio 2", "centro": [290, 235], "superficie": 17.86},
                ],
            }],
        }
        normalizado, informe = normalizar(plano)
        self.assertNotIn("✘", informe, informe)
        self.assertEqual(sum(len(m["huecos"]) for m in normalizado["plantas"][0]["muros"]), 7, informe)
        for estancia in normalizado["plantas"][0]["estancias"]:
            self.assertLessEqual(abs(estancia["superficie"] - estancia["superficie_plano"]), 0.1, informe)

    def test_escala_de_salida(self):
        deteccion = detector.detectar_muros(imagen_casa(), escala_salida=0.5)
        h1 = next(s for s in deteccion["muros"] if s["id"] == "H1")
        self.assertEqual(h1["inicio"], (52.5, 42.5))

    def test_imagen_sin_plano(self):
        vacia = io.BytesIO()
        Image.new("L", (300, 300), 255).save(vacia, "PNG")
        with self.assertRaises(detector.ErrorDetector):
            detector.detectar_muros(vacia.getvalue())
        with self.assertRaises(detector.ErrorDetector):
            detector.detectar_muros(b"no soy una imagen")


# --------------------------------------------------------------- PDF y DXF

class BaseCarpetaPlanos(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        parche = mock.patch.object(importar.rutas, "CARPETA_DATOS", Path(self.tmp.name))
        parche.start()
        self.addCleanup(parche.stop)


def dxf_casa():
    documento = ezdxf.new(units=4)  # milímetros
    msp = documento.modelspace()
    muros = {"layer": "MUROS"}
    msp.add_lwpolyline([(0, 0), (10200, 0), (10200, 8200), (0, 8200)], close=True, dxfattribs=muros)
    for a, b in [((200, 200), (4000, 200)), ((4900, 200), (6000, 200)), ((6100, 200), (10000, 200)),
                 ((200, 8000), (6000, 8000)), ((6100, 8000), (10000, 8000)), ((200, 200), (200, 8000)),
                 ((10000, 200), (10000, 8000)), ((6000, 200), (6000, 8000)), ((6100, 200), (6100, 8000))]:
        msp.add_line(a, b, dxfattribs=muros)
    msp.add_arc((4000, 200), 900, 0, 90, dxfattribs={"layer": "PUERTAS"})
    msp.add_text("SALON", dxfattribs={"insert": (2500, 4000)})
    msp.add_text("45,24 m2", dxfattribs={"insert": (2500, 3700)})
    msp.add_line((0, -1000), (10200, -1000), dxfattribs={"layer": "COTAS"})
    salida = io.StringIO()
    documento.write(salida)
    return salida.getvalue().encode("utf-8")


class TestDXF(BaseCarpetaPlanos):
    def test_geometria_exacta_en_metros(self):
        (adjunto,) = importar.importar_dxf(dxf_casa(), "casa.dxf")
        ruta = importar.ruta_guardada(adjunto["origen"]["id"], "dxf")
        analisis = importar.analizar_dxf(ruta)
        self.assertEqual(analisis["capas_muro"], ["MUROS"])
        (puerta,) = analisis["huecos"]
        self.assertEqual((puerta["centro"], puerta["ancho"]), ((4.45, 0.2), 0.9))
        self.assertIn(("SALON", (2.5, 4.0)), analisis["textos"])
        plano, informe = normalizar({
            "unidades": "m",
            "plantas": [{
                "muros": analisis["muros"],
                "huecos": [{"tipo": "puerta", "centro": puerta["centro"], "ancho": 0.9}],
                "estancias": [{"nombre": "Salón", "centro": [2.5, 4.0], "superficie": SALON},
                              {"nombre": "Dormitorio", "centro": [7.5, 4.0], "superficie": DORMITORIO}],
            }],
        })
        self.assertEqual(superficies(plano), {"Salón": SALON, "Dormitorio": DORMITORIO}, informe)
        # La fachada norte, partida por el tabique al emparejar caras, vuelve a ser un muro.
        self.assertEqual(len(plano["plantas"][0]["muros"]), 5)

    def test_vista_previa_es_una_imagen(self):
        (adjunto,) = importar.importar_dxf(dxf_casa(), "casa.dxf")
        imagen = Image.open(io.BytesIO(adjunto["datos"]))
        self.assertLessEqual(max(imagen.size), importar.LADO_VISTA)

    def test_dxf_roto(self):
        with self.assertRaises(importar.ErrorImportacion):
            importar.importar_dxf(b"esto no es un dxf", "roto.dxf")
        self.assertEqual(list(importar.carpeta_planos().glob("*.dxf")), [], "no deja basura")

    def test_ids_que_no_genera_el_importador_se_rechazan(self):
        for malo in ("../config", "abc", None, "0123456789ab/../x"):
            self.assertIsNone(importar.ruta_guardada(malo, "dxf"))


class TestPDF(BaseCarpetaPlanos):
    def test_paginas_a_imagen_con_original_en_alta(self):
        pdf = io.BytesIO()
        Image.open(io.BytesIO(imagen_casa())).convert("RGB").save(pdf, "PDF")
        paginas = importar.importar_pdf(pdf.getvalue(), "casa.pdf")
        self.assertEqual(len(paginas), 1)
        origen = paginas[0]["origen"]
        alta = Image.open(importar.ruta_guardada(origen["id"], "png"))
        vista = Image.open(io.BytesIO(paginas[0]["datos"]))
        self.assertEqual(max(alta.size), importar.LADO_ALTA)
        self.assertAlmostEqual(origen["escala_vista"], vista.width / alta.width)

    def test_el_detector_mide_en_alta_y_responde_en_px_de_la_vista(self):
        pdf = io.BytesIO()
        Image.open(io.BytesIO(imagen_casa())).convert("RGB").save(pdf, "PDF")
        (pagina,) = importar.importar_pdf(pdf.getvalue(), "casa.pdf")
        adjunto = {"media_type": pagina["media_type"], "datos": base64.b64encode(pagina["datos"]).decode(),
                   "origen": pagina["origen"]}
        historial = [{"tipo": "usuario", "texto": "", "adjuntos": [adjunto]}]
        texto = herramientas.ejecutar(herramientas.DETECTAR, {"imagen": 1}, historial, [])
        vista = Image.open(io.BytesIO(pagina["datos"]))
        self.assertIn(f"Imagen de {vista.width}×{vista.height} px", texto)

    def test_pdf_roto(self):
        with self.assertRaises(importar.ErrorImportacion):
            importar.importar_pdf(b"%PDF-roto", "roto.pdf")


# ------------------------------------------------------------- constructores

class _Grabadora:
    """Objeto COM/API genérico: cualquier atributo o llamada se registra."""

    def __init__(self, registro, nombre="raiz"):
        object.__setattr__(self, "_registro", registro)
        object.__setattr__(self, "_nombre", nombre)

    def __getattr__(self, nombre):
        return _Grabadora(self._registro, nombre)

    def __call__(self, *args, **kwargs):
        self._registro.append((self._nombre, args))
        return _Grabadora(self._registro, self._nombre + "()")

    def __setattr__(self, clave, valor):
        self._registro.append(("=" + clave, (valor,)))


def llamadas(registro, nombre):
    return [r[1] for r in registro if r[0] == nombre]


class TestConstructores(unittest.TestCase):
    def setUp(self):
        self.plano, _ = normalizar(plano_metros())

    def test_blender_usa_el_kit_con_los_huecos_normalizados(self):
        registro = []

        def grabar(nombre):
            return lambda *a, **k: registro.append((nombre, a, k))

        entorno = {
            "bpy": types.SimpleNamespace(data=types.SimpleNamespace(collections=types.SimpleNamespace(get=lambda n: None))),
            "muro": grabar("muro"), "forjado": grabar("forjado"), "coleccion": grabar("coleccion"),
        }
        exec(constructores.a_blender(self.plano), entorno)
        muros = [r for r in registro if r[0] == "muro"]
        self.assertEqual(len(muros), 5)
        sur = next(r for r in muros if "S1" in r[2]["nombre"])
        self.assertEqual(sur[2]["huecos"][0]["tipo"], "puerta")
        self.assertEqual(sur[2]["capa"], "Plano - Planta baja")
        suelos = [r for r in registro if r[0] == "forjado"]
        self.assertEqual([r[2]["nombre"] for r in suelos], ["Solera", "Suelo Salón", "Suelo Dormitorio"])
        self.assertEqual(suelos[1][2]["material"], "parquet")

    def test_autocad_dibuja_en_las_unidades_del_dibujo(self):
        registro = []
        doc = types.SimpleNamespace(
            GetVariable=lambda n: 4, SetVariable=lambda n, v: registro.append(("SetVariable", (n, v))),
            Layers=_Grabadora(registro, "Layers"),
        )
        entorno = {
            "acad": _Grabadora(registro, "acad"), "doc": doc, "ms": _Grabadora(registro, "ms"),
            "punto": lambda x, y, z=0: (x, y, z), "puntos": lambda lista: list(lista),
        }
        with mock.patch.dict("sys.modules", {"pythoncom": None, "win32com": None, "win32com.client": None}):
            exec(constructores.a_autocad(self.plano), entorno)
        self.assertEqual(len(llamadas(registro, "AddArc")), 2, "dos puertas, dos arcos de giro")
        lineas = llamadas(registro, "AddLine")
        self.assertTrue(any(a == (10200.0, 0.0, 0) or b == (10200.0, 0.0, 0) for a, b in lineas),
                        "la esquina exterior de 10,2 m debe salir en 10200 mm")
        rotulos = [a[0] for a in llamadas(registro, "AddText")]
        self.assertIn("SALÓN", rotulos)
        self.assertIn("45,24 m²", rotulos)
        self.assertIn(("DIMSCALE", 50.0), llamadas(registro, "SetVariable"))

    def test_sketchup_genera_ruby_coherente(self):
        ruby = constructores.a_sketchup(self.plano)
        self.assertEqual(ruby.count("g = ba_muro(ents,"), 5)
        self.assertEqual(ruby.count("\ndef "), ruby.count("\nend"))
        self.assertIn("Geom::Point3d.new(0.0.m, 0.0.m, 0.0.m)", ruby)
        self.assertNotIn("None", ruby)
        self.assertIn("'Muro N'", ruby)

    def test_sketchup_no_interpola_nombres_venidos_del_plano(self):
        """Un texto de un DXF ajeno acaba en el Ruby: entre comillas dobles se ejecutaría."""
        datos = plano_metros()
        datos["plantas"][0]["estancias"][0]["nombre"] = "#{system('calc')} O'Brien"
        plano, _ = normalizar(datos)
        ruby = constructores.a_sketchup(plano)
        self.assertIn("'Suelo #{system(\\'calc\\')} O\\'Brien'", ruby)
        self.assertNotIn('"#{', ruby)

    def test_revit_codigo_compatible_con_ironpython(self):
        codigo = constructores.a_revit(self.plano)
        arbol = ast.parse(codigo)
        self.assertFalse(any(isinstance(n, ast.JoinedStr) for n in ast.walk(arbol)), "sin f-strings")

    def test_revit_crea_muros_por_eje_huecos_y_habitaciones(self):
        registro = []

        class Vec:
            def __init__(self, x, y, z=0.0):
                self.X, self.Y, self.Z = x, y, z

            def __sub__(self, o):
                return Vec(self.X - o.X, self.Y - o.Y, self.Z - o.Z)

            def __add__(self, o):
                return Vec(self.X + o.X, self.Y + o.Y, self.Z + o.Z)

            def __mul__(self, k):
                return Vec(self.X * k, self.Y * k, self.Z * k)

            def Normalize(self):
                largo = (self.X ** 2 + self.Y ** 2) ** 0.5
                return Vec(self.X / largo, self.Y / largo)

        pies = lambda m: m / 0.3048

        def muro(inicio, fin, nivel_base, altura=2.7, tipo=None):
            registro.append(("muro", inicio, fin))
            curva = types.SimpleNamespace(
                GetEndPoint=lambda i: Vec(pies(inicio[0]), pies(inicio[1])) if i == 0 else Vec(pies(fin[0]), pies(fin[1])),
                Length=pies(((fin[0] - inicio[0]) ** 2 + (fin[1] - inicio[1]) ** 2) ** 0.5),
                Evaluate=lambda t, normalizado: Vec(0, 0),
            )
            return types.SimpleNamespace(Location=types.SimpleNamespace(Curve=curva))

        crear = types.SimpleNamespace(
            NewOpening=lambda w, a, b: registro.append(("abertura", a.X, b.X)),
            NewRoom=lambda nivel, uv: _Grabadora(registro, "habitacion"),
        )
        entorno = {
            "nivel": lambda altura, nombre=None: types.SimpleNamespace(Elevation=0.0),
            "muro": muro, "suelo": lambda contorno, nivel: registro.append(("suelo", contorno)),
            "imprimir": lambda t: registro.append(("imprimir", t)),
            "_elementos": lambda clase=None: [], "_simbolos": lambda categoria: [],
            "_activar": lambda s: s, "_a_pies": pies, "_a_metros": lambda p: p * 0.3048,
            "DB": types.SimpleNamespace(XYZ=Vec, UV=lambda u, v: (u, v), BuiltInParameter=_Grabadora([], "BIP"),
                                        WallType=object, WallKind=types.SimpleNamespace(Basic=1)),
            "doc": types.SimpleNamespace(Create=crear, Regenerate=lambda: None),
        }
        exec(constructores.a_revit(self.plano), entorno)
        muros = [r for r in registro if r[0] == "muro"]
        self.assertEqual(len(muros), 5)
        sur = next(r for r in muros if r[1][1] == 0.1)
        self.assertEqual((list(sur[1]), list(sur[2])), ([0.1, 0.1], [10.1, 0.1]), "Revit recibe el eje, no el extremo de obra")
        self.assertEqual(len([r for r in registro if r[0] == "abertura"]), 3, "sin familias: aberturas libres")
        self.assertTrue(any("No hay familias de puertas" in str(r) for r in registro))
        self.assertEqual(llamadas(registro, "Set"), [("Salón",), ("Dormitorio",)], "habitaciones con nombre")
        self.assertTrue(any(r[0] == "imprimir" and "2 habitaciones" in r[1] for r in registro))


# -------------------------------------------------------- herramientas y agente

class ConectorDestino(ConectorFalso):
    def __init__(self, id_programa, nombre, salida="✔ hecho"):
        super().__init__(salida=salida, nombre_herramienta=f"{id_programa}_ejecutar_python")
        self.id = id_programa
        self.nombre = nombre


class TestHerramientas(BaseCarpetaPlanos):
    def setUp(self):
        super().setUp()
        parche = mock.patch.object(agent, "CARPETA_RENDERS", Path(self.tmp.name) / "renders")
        parche.start()
        self.addCleanup(parche.stop)

    def test_validar_no_construye_pero_muestra_la_imagen_de_control(self):
        blender = ConectorDestino("blender", "Blender")
        texto = herramientas.ejecutar(
            herramientas.RECONSTRUIR, {"programa": "blender", "plano": plano_metros(), "solo_validar": True},
            [], [blender],
        )
        self.assertIn("VALIDACIÓN", texto)
        self.assertEqual(blender.ejecuciones, [])
        (archivo,) = agent.renders_en_resultado(texto)
        self.assertTrue(Image.open(Path(self.tmp.name) / "renders" / archivo).size[0] > 100)

    def test_construye_con_la_herramienta_del_programa(self):
        blender = ConectorDestino("blender", "Blender")
        texto = herramientas.ejecutar(herramientas.RECONSTRUIR, {"programa": "blender", "plano": plano_metros()},
                                      [], [blender])
        self.assertIn("Reconstrucción en Blender completada", texto)
        ((nombre, argumentos),) = blender.ejecuciones
        self.assertEqual(nombre, "blender_ejecutar_python")
        self.assertIn("muro(", argumentos["codigo"])

    def test_programa_no_conectado(self):
        texto = herramientas.ejecutar(herramientas.RECONSTRUIR, {"programa": "revit", "plano": plano_metros()}, [], [])
        self.assertTrue(texto.startswith("ERROR: revit no está conectado"))

    def test_plano_invalido_es_error_legible(self):
        texto = herramientas.ejecutar(herramientas.RECONSTRUIR, {"programa": "blender", "plano": {}}, [], [])
        self.assertTrue(texto.startswith("ERROR: El plano necesita"))

    def test_superposicion_sobre_la_imagen_original(self):
        adjunto = {"media_type": "image/png", "datos": base64.b64encode(imagen_casa()).decode()}
        historial = [{"tipo": "usuario", "texto": "", "adjuntos": [adjunto]}]
        deteccion = detector.detectar_muros(imagen_casa())
        texto = herramientas.ejecutar(
            herramientas.RECONSTRUIR,
            {"programa": "autocad", "plano": plano_desde_deteccion(deteccion), "solo_validar": True},
            historial, [],
        )
        (archivo,) = agent.renders_en_resultado(texto)
        self.assertEqual(Image.open(Path(self.tmp.name) / "renders" / archivo).size, (700, 600))

    def test_sin_adjuntos(self):
        texto = herramientas.ejecutar(herramientas.DETECTAR, {}, [], [])
        self.assertIn("No hay ningún plano adjunto", texto)

    def test_detectar_sobre_un_dxf_redirige(self):
        historial = [{"tipo": "usuario", "adjuntos": [{"datos": "", "origen": {"tipo": "dxf"}}]}]
        self.assertIn(herramientas.LEER_DXF, herramientas.ejecutar(herramientas.DETECTAR, {}, historial, []))


class TestAgente(unittest.TestCase):
    CONFIG = {"proveedor": "anthropic", "claves": {"anthropic": "k"}, "modelos": {"anthropic": "m"}}

    def test_herramientas_de_planos_solo_cuando_hay_un_plano(self):
        """Son ~8 000 caracteres por petición: no se pagan en conversaciones sin plano."""
        sin_plano = {h["nombre"] for h in agent._herramientas([])}
        self.assertFalse(sin_plano & set(herramientas.NOMBRES))
        con_plano = {h["nombre"] for h in agent._herramientas([], con_planos=True)}
        self.assertTrue(set(herramientas.NOMBRES) <= con_plano)
        self.assertNotIn("Reconstruir un plano", agent.SISTEMA_BASE)
        self.assertIn("Reconstruir un plano", agent._sistema([], "", con_planos=True))

    def test_cuando_hace_falta_un_plano(self):
        self.assertFalse(agent._con_planos([], "Hazme una casa moderna con la planta baja abierta"))
        self.assertTrue(agent._con_planos([], "Pásame este plano a AutoCAD"))
        self.assertTrue(agent._con_planos([], "te mando el DXF"))
        self.assertTrue(agent._con_planos([], "mira", adjuntos=[{"datos": "x"}]))
        anterior = [{"tipo": "usuario", "texto": "esta casa", "adjuntos": [{"datos": "x"}]}]
        self.assertTrue(agent._con_planos(anterior, "ahora en Revit"), "el plano sigue en la conversación")

    def test_los_adjuntos_se_numeran_solo_en_la_vista_del_modelo(self):
        historial = [{"tipo": "usuario", "texto": "Haz esta casa", "adjuntos": [
            {"media_type": "image/png", "datos": "x"},
            {"media_type": "image/png", "datos": "y", "origen": {"tipo": "pdf", "pagina": 2, "paginas": 3, "nombre": "p.pdf"}},
        ]}]
        vista = agent._historial_para_modelo(historial)
        self.assertIn("1) imagen; 2) página 2/3 del PDF «p.pdf»", vista[0]["texto"])
        self.assertEqual(historial[0]["texto"], "Haz esta casa")

    def test_un_turno_reconstruye_en_el_programa_conectado(self):
        blender = ConectorDestino("blender", "Blender")
        proveedor = ProveedorFalso([
            RespuestaLLM(llamadas=[LlamadaHerramienta("1", herramientas.RECONSTRUIR,
                                                      {"programa": "blender", "plano": plano_metros()})]),
            RespuestaLLM(texto="Casa reconstruida."),
        ])
        historial, eventos = [], []
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(agent, "CONECTORES", [blender]), \
                mock.patch.object(agent, "CARPETA_RENDERS", Path(tmp)), \
                mock.patch.object(agent, "crear_proveedor", return_value=proveedor), \
                mock.patch.object(agent, "_sistema", return_value="sistema"), \
                mock.patch.object(agent.cfg, "cargar", return_value=self.CONFIG):
            agent.ejecutar_turno(historial, "Reconstruye el plano", eventos.append)
        self.assertEqual(len(blender.ejecuciones), 1)
        tipos = [e["tipo"] for e in eventos]
        self.assertIn("render", tipos, "la imagen de control llega a la interfaz")
        herramienta = next(e for e in eventos if e["tipo"] == "herramienta")
        self.assertEqual((herramienta["programa"], herramienta["detalle"]), ("Planos", "blender"))
        resultado = next(m for m in historial if m["tipo"] == "resultado")
        self.assertIn("Salón: 45,24 m² / 45,24 m²", resultado["contenido"])


# ------------------------------------------------------------------ servidor

class TestServidor(BaseCarpetaPlanos):
    def test_importar_dxf_y_conservar_su_origen_al_enviarlo(self):
        from fastapi.testclient import TestClient

        cliente = TestClient(main.app)
        r = cliente.post("/api/planos/importar", json={
            "nombre": "casa.dxf", "datos": base64.b64encode(dxf_casa()).decode(),
        }).json()
        self.assertTrue(r["ok"], r)
        (adjunto,) = r["adjuntos"]
        self.assertEqual(adjunto["origen"]["tipo"], "dxf")
        (limpio,) = main._sanear_adjuntos([adjunto])
        self.assertEqual(limpio["origen"]["id"], adjunto["origen"]["id"])

    def test_origen_inventado_se_descarta(self):
        datos = base64.b64encode(imagen_casa()).decode()
        (limpio,) = main._sanear_adjuntos([{"media_type": "image/png", "datos": datos,
                                            "origen": {"tipo": "dxf", "id": "../../config"}}])
        self.assertNotIn("origen", limpio)

    def test_un_fallo_inesperado_del_turno_llega_a_la_interfaz(self):
        """Antes el turno moría en silencio y la interfaz se quedaba esperando."""
        from fastapi.testclient import TestClient

        with mock.patch.object(main, "ejecutar_turno", side_effect=RuntimeError("se rompió")):
            r = TestClient(main.app).post("/api/chat", json={"mensaje": "hola"})
        self.assertIn("Error inesperado al procesar el mensaje: se rompió", r.text)

    def test_formato_no_soportado(self):
        from fastapi.testclient import TestClient

        r = TestClient(main.app).post("/api/planos/importar", json={
            "nombre": "casa.dwg", "datos": base64.b64encode(b"AC1032").decode(),
        }).json()
        self.assertFalse(r["ok"])
        self.assertIn("DWG", r["error"])


if __name__ == "__main__":
    unittest.main()
