"""La interfaz muestra un entregable y permite descargarlo.

La lógica de `app.js` vive en el navegador y depende del DOM, así que la única
forma honesta de probarla es levantar el servidor y conducir Chromium de verdad.
Sustituye a la comprobación manual que se hizo al construir la función.

Se omite entera si Playwright no está instalado, para que el resto del suite siga
corriendo en cualquier máquina:

    pip install -e ".[dev]" && playwright install chromium
    python -m unittest tests.test_ui_entregables
"""

import socket
import threading
import unittest
from pathlib import Path
from unittest import mock

import httpx

from buildai import entregables
from buildai.main import app

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover - depende del entorno
    sync_playwright = None

DXF = b"0\nSECTION\n2\nHEADER\n0\nENDSEC\n0\nEOF\n"
IFC = b"ISO-10303-21;\nHEADER;\nENDSEC;\nEND-ISO-10303-21;\n"


def _puerto_libre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@unittest.skipIf(sync_playwright is None, "Playwright no está instalado")
class TestInterfazEntregables(unittest.TestCase):
    """Un solo navegador y un solo servidor para toda la clase: arrancarlos cuesta."""

    @classmethod
    def setUpClass(cls):
        import tempfile

        import uvicorn

        cls.tmp = tempfile.TemporaryDirectory()
        cls.carpeta = Path(cls.tmp.name)
        cls.parche = mock.patch.object(entregables, "CARPETA_ENTREGABLES", cls.carpeta)
        cls.parche.start()
        (cls.carpeta / "planta-baja.dxf").write_bytes(DXF)
        (cls.carpeta / "estructura.ifc").write_bytes(IFC)

        cls.puerto = _puerto_libre()
        cls.base = f"http://127.0.0.1:{cls.puerto}"
        cls.servidor = uvicorn.Server(
            uvicorn.Config(app, host="127.0.0.1", port=cls.puerto, log_level="error")
        )
        cls.hilo = threading.Thread(target=cls.servidor.run, daemon=True)
        cls.hilo.start()
        for _ in range(200):
            if cls.servidor.started:
                break
            threading.Event().wait(0.05)
        else:  # pragma: no cover - solo si el servidor no arranca
            raise RuntimeError("el servidor de pruebas no arrancó")

        cls.playwright = sync_playwright().start()
        cls.navegador = cls.playwright.chromium.launch()

    @classmethod
    def tearDownClass(cls):
        cls.navegador.close()
        cls.playwright.stop()
        cls.servidor.should_exit = True
        cls.hilo.join(timeout=10)
        cls.parche.stop()
        cls.tmp.cleanup()

    def setUp(self):
        self.pagina = self.navegador.new_page(viewport={"width": 1440, "height": 900})
        self.errores = []
        self.pagina.on("pageerror", lambda e: self.errores.append(str(e)))
        self.pagina.goto(self.base, wait_until="networkidle")
        self.addCleanup(self.pagina.close)
        self.addCleanup(lambda: self.assertEqual(self.errores, [], "errores de JavaScript"))

    def entregar(self, archivo, formato, tamano):
        self.pagina.evaluate(
            "ev => agregarEntregable(ev)",
            {"tipo": "entregable", "archivo": archivo, "formato": formato, "bytes": tamano},
        )

    def test_la_burbuja_muestra_formato_nombre_y_tamano(self):
        self.entregar("planta-baja.dxf", "DXF", len(DXF))
        burbuja = self.pagina.locator(".mensaje.entregable")
        self.assertEqual(burbuja.count(), 1)
        self.assertEqual(burbuja.locator(".entregable-formato").inner_text(), "DXF")
        self.assertEqual(burbuja.locator(".entregable-datos b").inner_text(), "planta-baja.dxf")
        self.assertIn("34 B", burbuja.locator(".entregable-datos small").inner_text())

    def test_el_boton_apunta_al_archivo_y_fuerza_la_descarga(self):
        self.entregar("planta-baja.dxf", "DXF", len(DXF))
        enlace = self.pagina.locator(".btn-entregable")
        self.assertEqual(enlace.get_attribute("href"), "/api/entregables/planta-baja.dxf")
        self.assertEqual(enlace.get_attribute("download"), "planta-baja.dxf")

    def test_la_descarga_devuelve_el_archivo_integro(self):
        r = httpx.get(f"{self.base}/api/entregables/planta-baja.dxf")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content, DXF)
        self.assertIn("attachment", r.headers["content-disposition"])

    def test_aparece_una_ficha_en_el_rail(self):
        self.entregar("estructura.ifc", "IFC", len(IFC))
        ficha = self.pagina.locator("#rail-entregables .entregable-archivo")
        self.assertEqual(ficha.count(), 1)
        self.assertEqual(ficha.inner_text(), "IFC")
        self.assertEqual(ficha.get_attribute("href"), "/api/entregables/estructura.ifc")

    def test_el_rail_deja_de_estar_vacio(self):
        vacio = self.pagina.locator('.rail-vacio[data-vacio-de="rail-entregables"]')
        self.assertFalse(vacio.is_hidden(), "debería verse el aviso antes de exportar nada")
        self.entregar("planta-baja.dxf", "DXF", len(DXF))
        self.assertTrue(vacio.is_hidden())

    def test_el_rail_pone_los_mas_recientes_primero(self):
        self.entregar("planta-baja.dxf", "DXF", len(DXF))
        self.entregar("estructura.ifc", "IFC", len(IFC))
        formatos = self.pagina.locator("#rail-entregables .entregable-archivo").all_inner_texts()
        self.assertEqual(formatos, ["IFC", "DXF"])

    def test_el_nombre_del_archivo_se_inserta_como_texto(self):
        """Va por textContent, no por HTML: un nombre con < > no puede inyectar nada."""
        self.entregar("<b>ojo</b>.dxf", "DXF", 10)
        self.assertEqual(
            self.pagina.locator(".entregable-datos b").inner_text(), "<b>ojo</b>.dxf"
        )
        self.assertEqual(self.pagina.locator(".entregable-datos b b").count(), 0)

    def test_queda_registrado_en_la_exportacion_de_la_conversacion(self):
        self.entregar("planta-baja.dxf", "DXF", len(DXF))
        anotado = self.pagina.evaluate(
            "() => transcripcion.filter(t => t.rol === 'entregable')"
        )
        self.assertEqual(anotado, [{"rol": "entregable", "archivo": "planta-baja.dxf",
                                    "formato": "DXF"}])

    def test_una_sesion_recuperada_vuelve_a_pintar_los_entregables(self):
        self.pagina.evaluate(
            "eventos => pintarConversacion(eventos)",
            [{"tipo": "usuario", "texto": "exporta"},
             {"tipo": "entregable", "archivo": "estructura.ifc", "formato": "IFC", "bytes": len(IFC)}],
        )
        self.assertEqual(self.pagina.locator(".mensaje.entregable").count(), 1)
        self.assertEqual(self.pagina.locator("#rail-entregables .entregable-archivo").count(), 1)

    def test_el_tamano_se_muestra_en_unidades_legibles(self):
        for octetos, esperado in ((512, "512 B"), (2048, "2.0 KB"), (5 * 1024 * 1024, "5.0 MB")):
            with self.subTest(octetos=octetos):
                self.assertEqual(self.pagina.evaluate("n => tamanoLegible(n)", octetos), esperado)


if __name__ == "__main__":
    unittest.main()
