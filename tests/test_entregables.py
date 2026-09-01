"""El canal de entregables solo deja pasar archivos reales de la carpeta propia.

El nombre de un entregable viaja del modelo a la interfaz y vuelve como una
petición HTTP, así que estas pruebas fijan el límite: nada fuera de
~/.buildai/entregables y ninguna extensión que no sea de dibujo.

    python -m unittest tests.test_entregables
"""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from fastapi.testclient import TestClient

from buildai import entregables
from buildai.connectors import sketchup
from buildai.main import app


class TestRutaPara(unittest.TestCase):
    def test_sanea_nombre_y_normaliza_extension(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(entregables, "CARPETA_ENTREGABLES", Path(tmp)):
                ruta = entregables.ruta_para("Planta baja / acción", ".DXF")
        self.assertEqual(ruta.suffix, ".dxf")
        self.assertNotIn("/", ruta.name)
        self.assertTrue(ruta.name.startswith("Planta-baja-acci-n-"))

    def test_nombre_vacio_no_deja_el_archivo_sin_nombre(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(entregables, "CARPETA_ENTREGABLES", Path(tmp)):
                ruta = entregables.ruta_para("../../..", "ifc")
        self.assertTrue(ruta.name.startswith("entregable-"))

    def test_formato_no_exportable_falla(self):
        with self.assertRaises(ValueError):
            entregables.ruta_para("plano", "exe")


class TestEntregablesEnResultado(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.carpeta = Path(self.tmp.name)
        parche = mock.patch.object(entregables, "CARPETA_ENTREGABLES", self.carpeta)
        parche.start()
        self.addCleanup(parche.stop)

    def _crear(self, nombre, contenido=b"datos"):
        ruta = self.carpeta / nombre
        ruta.write_bytes(contenido)
        return ruta

    def test_detecta_archivo_legitimo(self):
        ruta = self._crear("casa.ifc", b"ISO-10303-21;")
        salida = f"Exportado.\n{entregables.MARCA} {ruta}\nFin."
        self.assertEqual(
            entregables.entregables_en_resultado(salida),
            [{"archivo": "casa.ifc", "formato": "IFC", "bytes": 13}],
        )

    def test_rechaza_archivo_fuera_de_la_carpeta(self):
        fuera = Path(self.tmp.name).parent / "config.dxf"
        fuera.write_bytes(b"x")
        self.addCleanup(fuera.unlink)
        salida = f"{entregables.MARCA} {fuera}"
        self.assertEqual(entregables.entregables_en_resultado(salida), [])

    def test_rechaza_travesia_hacia_arriba(self):
        salida = f"{entregables.MARCA} {self.carpeta}/../../.buildai/config.json"
        self.assertEqual(entregables.entregables_en_resultado(salida), [])

    def test_rechaza_extension_fuera_de_la_lista_blanca(self):
        ruta = self._crear("virus.exe")
        self.assertEqual(entregables.entregables_en_resultado(f"{entregables.MARCA} {ruta}"), [])

    def test_ignora_marca_de_archivo_inexistente(self):
        salida = f"{entregables.MARCA} {self.carpeta / 'fantasma.dwg'}"
        self.assertEqual(entregables.entregables_en_resultado(salida), [])


class TestCadenaRuby(unittest.TestCase):
    """El puente de SketchUp recibe Ruby como texto, y en Windows las rutas van
    llenas de barras invertidas que Ruby leería como escapes."""

    def test_escapa_barras_de_windows(self):
        salida = sketchup._cadena_ruby(r"C:\Users\ana\.buildai\entregables\casa.dwg")
        self.assertEqual(salida, r"'C:\\Users\\ana\\.buildai\\entregables\\casa.dwg'")

    def test_escapa_comilla_simple(self):
        self.assertEqual(sketchup._cadena_ruby("l'atelier"), r"'l\'atelier'")

    def test_solo_pro_recibe_la_guardia_de_licencia(self):
        with mock.patch.object(entregables, "CARPETA_ENTREGABLES", Path(tempfile.gettempdir())):
            dwg = sketchup._ruby_exportar("dwg", None)
            dae = sketchup._ruby_exportar("dae", None)
        self.assertIn("Sketchup.is_pro?", dwg)
        self.assertNotIn("Sketchup.is_pro?", dae)


class TestEndpointDescarga(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.carpeta = Path(self.tmp.name)
        parche = mock.patch.object(entregables, "CARPETA_ENTREGABLES", self.carpeta)
        parche.start()
        self.addCleanup(parche.stop)
        self.cliente = TestClient(app)

    def test_descarga_archivo_valido_como_adjunto(self):
        (self.carpeta / "planta.dxf").write_bytes(b"0\nSECTION\n")
        r = self.cliente.get("/api/entregables/planta.dxf")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content, b"0\nSECTION\n")
        self.assertIn("attachment", r.headers["content-disposition"])

    def test_rechaza_extension_no_permitida(self):
        (self.carpeta / "script.exe").write_bytes(b"x")
        self.assertEqual(self.cliente.get("/api/entregables/script.exe").status_code, 404)

    def test_rechaza_nombre_oculto(self):
        (self.carpeta / ".secreto.dxf").write_bytes(b"x")
        self.assertEqual(self.cliente.get("/api/entregables/.secreto.dxf").status_code, 404)

    def test_rechaza_travesia_de_rutas(self):
        r = self.cliente.get("/api/entregables/..%2F..%2Fconfig.json")
        self.assertEqual(r.status_code, 404)

    def test_archivo_inexistente(self):
        self.assertEqual(self.cliente.get("/api/entregables/nada.ifc").status_code, 404)


if __name__ == "__main__":
    unittest.main()
