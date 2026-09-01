"""Exportar desde AutoCAD escribe una copia y jamás toca el dibujo abierto.

La regla que fija esta prueba es la que más daño haría si se rompiera: AutoCAD
tiene `SaveAs`, es la forma obvia de guardar en otro formato, y **renombraría el
dibujo que el arquitecto tiene abierto**. Por eso el doble revienta si alguien
lo llama. Todo va contra un AutoCAD falso: el real solo existe en Windows.

    python -m unittest tests.test_exportar_autocad
"""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from buildai import entregables
from buildai.connectors import autocad
from tests.dobles import AplicacionAutoCADFalsa, DocumentoAutoCADFalso


class BaseAutoCAD(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        parche = mock.patch.object(entregables, "CARPETA_ENTREGABLES", Path(self.tmp.name))
        parche.start()
        self.addCleanup(parche.stop)
        # El sondeo real duerme medio segundo por vuelta: aquí sobra con un pestañeo.
        rapido = mock.patch.object(autocad, "_INTERVALO_SONDEO", 0.005)
        rapido.start()
        self.addCleanup(rapido.stop)

    def exportar(self, argumentos, documento=None, espera=1):
        """Ejecuta la herramienta contra un AutoCAD falso y devuelve (salida, doc)."""
        doc = documento if documento is not None else DocumentoAutoCADFalso()
        acad = AplicacionAutoCADFalsa(doc)
        with mock.patch.object(autocad, "_obtener_acad", return_value=acad), \
             mock.patch.object(autocad, "_ESPERA_MAXIMA", espera):
            salida = autocad.ConectorAutoCAD().ejecutar("autocad_exportar", argumentos)
        return salida, doc


class TestFormatoDWG(BaseAutoCAD):
    def test_usa_wblock_con_la_ruta_de_destino(self):
        salida, doc = self.exportar({"formato": "dwg", "nombre": "planta baja"})
        (_, orden), = doc.ordenes("SendCommand")
        self.assertTrue(orden.startswith("_.-WBLOCK\n"), orden)
        self.assertIn(str(entregables.CARPETA_ENTREGABLES), orden)
        self.assertTrue(orden.endswith("\n*\n"), "debe volcar el dibujo entero")
        self.assertIn(entregables.MARCA, salida)

    def test_nunca_usa_saveas(self):
        """SaveAs renombraría el dibujo abierto del usuario: el doble lo prohíbe."""
        salida, doc = self.exportar({"formato": "dwg"})
        self.assertEqual(doc.ordenes("SaveAs"), [])
        self.assertIn(entregables.MARCA, salida)

    def test_la_orden_fuerza_el_ingles(self):
        """El prefijo '_.' hace que funcione en un AutoCAD en español o alemán."""
        _, doc = self.exportar({"formato": "dwg"})
        (_, orden), = doc.ordenes("SendCommand")
        self.assertTrue(orden.startswith("_."), orden)

    def test_sin_nombre_toma_el_del_dibujo(self):
        doc = DocumentoAutoCADFalso(nombre="Vivienda Ruiz.dwg")
        salida, _ = self.exportar({"formato": "dwg"}, documento=doc)
        self.assertIn("Vivienda-Ruiz-", salida)


class TestFormatoDXF(BaseAutoCAD):
    def test_usa_export_con_un_conjunto_de_seleccion(self):
        salida, doc = self.exportar({"formato": "dxf", "nombre": "planta"})
        (_, ruta, extension, conjunto), = doc.ordenes("Export")
        self.assertEqual(extension, "DXF")
        self.assertTrue(ruta.endswith(".dxf"))
        self.assertIsNotNone(conjunto, "doc.Export exige un SelectionSet")
        self.assertIn(entregables.MARCA, salida)

    def test_no_pasa_por_la_linea_de_comandos(self):
        """Export es síncrono; usar SendCommand aquí traería carreras innecesarias."""
        _, doc = self.exportar({"formato": "dxf"})
        self.assertEqual(doc.ordenes("SendCommand"), [])


class TestFormatoPDF(BaseAutoCAD):
    def test_traza_con_el_controlador_pdf_de_autocad(self):
        salida, doc = self.exportar({"formato": "pdf", "nombre": "planos"})
        (_, ruta, configuracion), = doc.ordenes("PlotToFile")
        self.assertTrue(ruta.endswith(".pdf"))
        self.assertEqual(configuracion, "DWG To PDF.pc3")
        self.assertIn(entregables.MARCA, salida)


class TestErrores(BaseAutoCAD):
    def test_formato_no_soportado_no_llega_a_com(self):
        salida, doc = self.exportar({"formato": "ifc"})
        self.assertTrue(salida.startswith("ERROR:"))
        self.assertEqual(doc.registro, [], "no debe tocarse AutoCAD")

    def test_si_autocad_no_escribe_el_archivo_no_hay_marca(self):
        doc = DocumentoAutoCADFalso(escribir=False)
        salida, _ = self.exportar({"formato": "dwg"}, documento=doc, espera=0.2)
        self.assertIn("ERROR", salida)
        self.assertNotIn(entregables.MARCA, salida)

    def test_una_excepcion_de_com_se_devuelve_como_texto(self):
        doc = DocumentoAutoCADFalso()
        doc.Export = mock.Mock(side_effect=Exception("-2147352567 rechazado"))
        salida, _ = self.exportar({"formato": "dxf"}, documento=doc)
        self.assertIn("ERROR exportando a DXF", salida)
        self.assertIn("-2147352567", salida)


class TestConjuntoDeSeleccion(BaseAutoCAD):
    def test_reutiliza_el_nombre_borrando_el_conjunto_previo(self):
        """AutoCAD falla al añadir un SelectionSet cuyo nombre ya existe."""
        doc = DocumentoAutoCADFalso(conjuntos_existentes=("BUILDAI_EXPORT",))
        autocad._conjunto_vacio(doc)
        self.assertEqual(len(doc.SelectionSets.borrados), 1)
        self.assertEqual(doc.SelectionSets.añadidos, ["BUILDAI_EXPORT"])

    def test_sin_conjunto_previo_solo_lo_crea(self):
        doc = DocumentoAutoCADFalso()
        autocad._conjunto_vacio(doc)
        self.assertEqual(doc.SelectionSets.borrados, [])
        self.assertEqual(doc.SelectionSets.añadidos, ["BUILDAI_EXPORT"])


class TestEsperaDeArchivo(unittest.TestCase):
    def setUp(self):
        rapido = mock.patch.object(autocad, "_INTERVALO_SONDEO", 0.005)
        rapido.start()
        self.addCleanup(rapido.stop)

    def test_espera_a_que_el_archivo_deje_de_crecer(self):
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "x.dwg"
            ruta.write_bytes(b"contenido")
            self.assertTrue(autocad._esperar_archivo(ruta, segundos=1))

    def test_agota_el_plazo_si_el_archivo_no_aparece(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertFalse(autocad._esperar_archivo(Path(tmp) / "no-existe.dwg", segundos=0.2))

    def test_un_archivo_vacio_no_cuenta_como_terminado(self):
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "x.dwg"
            ruta.write_bytes(b"")
            self.assertFalse(autocad._esperar_archivo(ruta, segundos=0.2))


if __name__ == "__main__":
    unittest.main()
