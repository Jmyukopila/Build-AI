"""Exportar desde Revit: la ruta sin transacción y el conector que la llama.

La razón de que exista `/exportar` como ruta aparte es que la API de Revit
PROHÍBE `Document.Export` dentro de una transacción, y `/ejecutar` abre una
siempre. Si alguien «simplificara» metiendo la exportación en `/ejecutar`, Revit
fallaría en tiempo de ejecución y solo se vería con Revit delante — por eso la
prueba de que no se abre ninguna transacción es la más importante del archivo.

    python -m unittest tests.test_exportar_revit
"""

import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

from buildai import entregables
from buildai.connectors import revit
from tests.dobles import (
    DocumentoRevitFalso, HttpFalso, RespuestaFalsa, peticion, stubs_pyrevit,
)


def vista(imprimible=True, plantilla=False):
    return types.SimpleNamespace(IsTemplate=plantilla, CanBePrinted=imprimible, Id="vista-1")


class BaseRuta(unittest.TestCase):
    """Prueba la ruta /exportar de la extensión de pyRevit."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.carpeta = self.tmp.name

    def exportar(self, datos, documento=None, con_pdf=True):
        cuerpo = {"carpeta": self.carpeta, "nombre": "proyecto"}
        cuerpo.update(datos)
        with stubs_pyrevit(documento, con_pdf=con_pdf) as ext:
            return ext.rutas["/exportar"](peticion(cuerpo)), ext


class TestLaRutaNoAbreTransaccion(BaseRuta):
    def test_ningun_formato_abre_transaccion(self):
        """Revit lanzaría InvalidOperationException si la hubiera."""
        for formato in ("ifc", "dwg", "dxf", "pdf"):
            with self.subTest(formato=formato):
                doc = DocumentoRevitFalso(vista_activa=vista())
                _, ext = self.exportar({"formato": formato}, documento=doc)
                self.assertEqual(ext.transacciones, [])

    def test_ejecutar_si_la_abre(self):
        """Contraste: la otra ruta sí necesita transacción para modificar el modelo."""
        with stubs_pyrevit() as ext:
            ext.rutas["/ejecutar"](peticion({"codigo": "salida.append('hola')"}))
            self.assertEqual(ext.transacciones, ["BuildAI"])


class TestFormatoIFC(BaseRuta):
    def test_por_defecto_usa_la_vista_de_coordinacion_2x3(self):
        respuesta, ext = self.exportar({"formato": "ifc"})
        self.assertTrue(respuesta["ok"])
        self.assertEqual(ext.doc.exportaciones[0]["opciones"].FileVersion, "IFC2x3CV2")

    def test_se_puede_pedir_ifc4(self):
        _, ext = self.exportar({"formato": "ifc", "version": "4"})
        self.assertEqual(ext.doc.exportaciones[0]["opciones"].FileVersion, "IFC4")

    def test_no_necesita_vistas(self):
        """IFC exporta el modelo entero: no depende de qué vista esté abierta."""
        respuesta, ext = self.exportar({"formato": "ifc"}, documento=DocumentoRevitFalso())
        self.assertTrue(respuesta["ok"])
        self.assertIsNone(ext.doc.exportaciones[0]["vistas"])


class TestFormatosDeVista(BaseRuta):
    def test_dwg_exporta_la_vista_activa(self):
        doc = DocumentoRevitFalso(vista_activa=vista())
        respuesta, ext = self.exportar({"formato": "dwg"}, documento=doc)
        self.assertTrue(respuesta["ok"])
        self.assertEqual(ext.doc.exportaciones[0]["vistas"].Count, 1)

    def test_si_la_vista_activa_no_sirve_usa_las_hojas(self):
        doc = DocumentoRevitFalso(vista_activa=vista(imprimible=False),
                                  hojas=[vista(), vista(), vista()])
        respuesta, ext = self.exportar({"formato": "dxf"}, documento=doc)
        self.assertTrue(respuesta["ok"])
        self.assertEqual(ext.doc.exportaciones[0]["vistas"].Count, 3)

    def test_una_plantilla_de_vista_no_cuenta_como_vista_activa(self):
        doc = DocumentoRevitFalso(vista_activa=vista(plantilla=True), hojas=[vista()])
        _, ext = self.exportar({"formato": "dwg"}, documento=doc)
        self.assertEqual(ext.doc.exportaciones[0]["vistas"].Count, 1)

    def test_sin_vistas_ni_hojas_pide_abrir_una(self):
        respuesta, _ = self.exportar({"formato": "dwg"}, documento=DocumentoRevitFalso())
        self.assertFalse(respuesta["ok"])
        self.assertIn("Abre la", respuesta["error"])


class TestFormatoPDF(BaseRuta):
    def test_el_nombre_viaja_en_las_opciones(self):
        doc = DocumentoRevitFalso(vista_activa=vista())
        respuesta, ext = self.exportar({"formato": "pdf"}, documento=doc)
        self.assertTrue(respuesta["ok"])
        self.assertEqual(ext.doc.exportaciones[0]["opciones"].FileName, "proyecto")

    def test_revit_anterior_a_2022_lo_explica_en_vez_de_reventar(self):
        doc = DocumentoRevitFalso(vista_activa=vista())
        respuesta, _ = self.exportar({"formato": "pdf"}, documento=doc, con_pdf=False)
        self.assertFalse(respuesta["ok"])
        self.assertIn("Revit 2022", respuesta["error"])
        self.assertIn("DWG", respuesta["error"], "debe ofrecer una alternativa")


class TestNombreRealDelArchivo(BaseRuta):
    def test_devuelve_el_nombre_que_revit_escribio_no_el_propuesto(self):
        """Revit le añade el nombre de la vista a los DWG. Suponer el nombre
        dejaría al usuario con un entregable que la interfaz no encuentra."""
        doc = DocumentoRevitFalso(vista_activa=vista(), sufijo_vista="-Nivel 1")
        respuesta, _ = self.exportar({"formato": "dwg"}, documento=doc)
        self.assertEqual(respuesta["resultado"], "proyecto-Nivel 1.dwg")

    def test_ignora_los_archivos_que_ya_estaban(self):
        Path(self.carpeta, "anterior.ifc").write_bytes(b"viejo")
        respuesta, _ = self.exportar({"formato": "ifc"})
        self.assertEqual(respuesta["resultado"], "proyecto.ifc")

    def test_si_revit_no_escribe_nada_lo_dice(self):
        doc = DocumentoRevitFalso(escribir=False)
        respuesta, _ = self.exportar({"formato": "ifc"}, documento=doc)
        self.assertFalse(respuesta["ok"])
        self.assertIn("no escribió", respuesta["error"])


class TestValidacionDeEntrada(BaseRuta):
    def test_formato_desconocido(self):
        respuesta, _ = self.exportar({"formato": "skp"})
        self.assertFalse(respuesta["ok"])
        self.assertIn("skp", respuesta["error"])

    def test_faltan_carpeta_o_nombre(self):
        with stubs_pyrevit() as ext:
            respuesta = ext.rutas["/exportar"](peticion({"formato": "ifc"}))
        self.assertFalse(respuesta["ok"])
        self.assertIn("Faltan", respuesta["error"])

    def test_una_excepcion_vuelve_como_traza_no_como_caida(self):
        doc = DocumentoRevitFalso()
        doc.Export = mock.Mock(side_effect=RuntimeError("Revit dijo que no"))
        respuesta, _ = self.exportar({"formato": "ifc"}, documento=doc)
        self.assertFalse(respuesta["ok"])
        self.assertIn("Revit dijo que no", respuesta["error"])


class TestConectorRevit(unittest.TestCase):
    """Lado BuildAI: qué se envía y cómo se interpreta lo que vuelve."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.carpeta = Path(self.tmp.name)
        parche = mock.patch.object(entregables, "CARPETA_ENTREGABLES", self.carpeta)
        parche.start()
        self.addCleanup(parche.stop)

    def exportar(self, argumentos, respuesta):
        falso = HttpFalso(respuesta)
        with mock.patch.object(revit.httpx, "post", falso):
            return revit.ConectorRevit().ejecutar("revit_exportar", argumentos), falso

    def test_el_cuerpo_lleva_carpeta_nombre_sin_extension_y_version(self):
        _, falso = self.exportar(
            {"formato": "ifc", "nombre": "edificio viviendas", "version_ifc": "4"},
            RespuestaFalsa({"ok": True, "resultado": "x.ifc"}),
        )
        cuerpo = falso.ultima["json"]
        self.assertEqual(cuerpo["formato"], "ifc")
        self.assertEqual(cuerpo["carpeta"], str(self.carpeta))
        self.assertEqual(cuerpo["version"], "4")
        self.assertTrue(cuerpo["nombre"].startswith("edificio-viviendas-"))
        self.assertNotIn(".", cuerpo["nombre"], "Revit pone la extensión, no nosotros")

    def test_version_por_defecto_2x3(self):
        _, falso = self.exportar({"formato": "ifc"}, RespuestaFalsa({"ok": True, "resultado": "x.ifc"}))
        self.assertEqual(falso.ultima["json"]["version"], "2x3")

    def test_extension_antigua_pide_reinstalar(self):
        """Un 404 solo puede significar que la extensión no conoce /exportar."""
        salida, _ = self.exportar({"formato": "ifc"}, RespuestaFalsa(status_code=404, texto="no"))
        self.assertIn("desactualizada", salida)
        self.assertIn("Conectar automáticamente", salida)
        self.assertNotIn(entregables.MARCA, salida)

    def test_un_archivo_real_produce_la_marca(self):
        (self.carpeta / "proyecto.ifc").write_bytes(b"ISO-10303-21;")
        salida, _ = self.exportar({"formato": "ifc"},
                                  RespuestaFalsa({"ok": True, "resultado": "proyecto.ifc"}))
        self.assertIn(f"{entregables.MARCA} {self.carpeta / 'proyecto.ifc'}", salida)
        self.assertIn("13 bytes", salida)

    def test_si_revit_dice_ok_pero_el_archivo_no_esta_no_hay_marca(self):
        salida, _ = self.exportar({"formato": "ifc"},
                                  RespuestaFalsa({"ok": True, "resultado": "fantasma.ifc"}))
        self.assertIn("ERROR", salida)
        self.assertNotIn(entregables.MARCA, salida)

    def test_el_error_de_revit_se_propaga(self):
        salida, _ = self.exportar({"formato": "dwg"},
                                  RespuestaFalsa({"ok": False, "error": "No hay ninguna vista"}))
        self.assertIn("ERROR exportando desde Revit", salida)
        self.assertIn("No hay ninguna vista", salida)

    def test_respuesta_no_json(self):
        salida, _ = self.exportar({"formato": "ifc"}, RespuestaFalsa(texto="<html>500</html>"))
        self.assertIn("respuesta inesperada", salida)

    def test_revit_cerrado_da_un_mensaje_util(self):
        falso = HttpFalso(revit.httpx.ConnectError("rechazada"))
        with mock.patch.object(revit.httpx, "post", falso):
            salida = revit.ConectorRevit().ejecutar("revit_exportar", {"formato": "ifc"})
        self.assertIn("pyRevit", salida)

    def test_formato_no_soportado_no_llega_a_la_red(self):
        falso = HttpFalso(RespuestaFalsa({"ok": True}))
        with mock.patch.object(revit.httpx, "post", falso):
            salida = revit.ConectorRevit().ejecutar("revit_exportar", {"formato": "glb"})
        self.assertEqual(falso.llamadas, [])
        self.assertTrue(salida.startswith("ERROR:"))


if __name__ == "__main__":
    unittest.main()
