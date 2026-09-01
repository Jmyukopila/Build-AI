"""Exportar desde SketchUp: el Ruby que se genera y cómo se trata la respuesta.

Dos detalles del puente condicionan todo el diseño y por eso se fijan aquí: el
puente devuelve el valor de la ÚLTIMA EXPRESIÓN evaluada, no lo que se imprime
(buildai_sketchup.rb), y las rutas de Windows van llenas de barras invertidas que
Ruby leería como escapes. Además, la versión gratuita de SketchUp no sabe escribir
DWG, DXF ni IFC, y eso debe salir como aviso en español, no como error de Ruby.

    python -m unittest tests.test_exportar_sketchup
"""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from buildai import entregables
from buildai.connectors import sketchup
from tests.dobles import HttpFalso, RespuestaFalsa


class BaseSketchUp(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        parche = mock.patch.object(entregables, "CARPETA_ENTREGABLES", Path(self.tmp.name))
        parche.start()
        self.addCleanup(parche.stop)


class TestRubyGenerado(BaseSketchUp):
    def test_los_formatos_pro_llevan_guardia_de_licencia(self):
        for formato in ("dwg", "dxf", "ifc", "obj", "fbx", "stl"):
            with self.subTest(formato=formato):
                codigo = sketchup._ruby_exportar(formato, "modelo")
                self.assertIn("Sketchup.is_pro?", codigo)
                self.assertIn("SketchUp Pro", codigo)

    def test_collada_no_lleva_guardia_porque_funciona_en_la_gratuita(self):
        codigo = sketchup._ruby_exportar("dae", "modelo")
        self.assertNotIn("Sketchup.is_pro?", codigo)

    def test_el_valor_final_es_la_marca_no_un_puts(self):
        """El puente evalúa y devuelve; un puts se perdería."""
        codigo = sketchup._ruby_exportar("dae", "modelo")
        self.assertIn("'ARCHIVO_GUARDADO: ' + ruta", codigo)
        self.assertNotIn("puts", codigo)

    def test_todos_los_caminos_devuelven_texto(self):
        """Ninguna rama puede acabar en nil: el puente lo convertiría en '' y el
        usuario se quedaría sin saber qué pasó."""
        codigo = sketchup._ruby_exportar("dwg", "modelo")
        self.assertIn("rescue => e", codigo)
        self.assertIn("'ERROR exportando desde SketchUp: ' + e.message", codigo)
        self.assertNotIn("nil", codigo)

    def test_la_ruta_va_en_una_variable_y_no_repetida(self):
        codigo = sketchup._ruby_exportar("dae", "modelo")
        self.assertEqual(codigo.count(str(entregables.CARPETA_ENTREGABLES)), 1)

    def test_usa_el_nombre_propuesto_saneado(self):
        codigo = sketchup._ruby_exportar("ifc", "Vivienda Ruiz")
        self.assertIn("Vivienda-Ruiz-", codigo)

    def test_sin_nombre_hay_uno_por_defecto(self):
        self.assertIn("modelo-", sketchup._ruby_exportar("dae", None))


class TestEscapadoRuby(unittest.TestCase):
    def test_escapa_las_barras_de_windows(self):
        salida = sketchup._cadena_ruby(r"C:\Users\ana\.buildai\entregables\casa.dwg")
        self.assertEqual(salida, r"'C:\\Users\\ana\\.buildai\\entregables\\casa.dwg'")

    def test_escapa_la_comilla_simple(self):
        self.assertEqual(sketchup._cadena_ruby("l'atelier"), r"'l\'atelier'")

    def test_una_ruta_normal_queda_entre_comillas_simples(self):
        self.assertEqual(sketchup._cadena_ruby("/home/ana/x.dae"), "'/home/ana/x.dae'")


class TestConectorSketchUp(BaseSketchUp):
    def exportar(self, argumentos, respuesta=None):
        falso = HttpFalso(respuesta or RespuestaFalsa({"ok": True, "resultado": "hecho"}))
        with mock.patch.object(sketchup.httpx, "post", falso):
            salida = sketchup.ConectorSketchUp().ejecutar("sketchup_exportar", argumentos)
        return salida, falso

    def test_formato_no_soportado_no_llega_a_la_red(self):
        falso = HttpFalso(RespuestaFalsa({"ok": True}))
        with mock.patch.object(sketchup.httpx, "post", falso):
            salida = sketchup.ConectorSketchUp().ejecutar("sketchup_exportar", {"formato": "glb"})
        self.assertEqual(falso.llamadas, [])
        self.assertIn("no exporta a GLB", salida)

    def test_exportar_recibe_mas_plazo_que_ejecutar_codigo(self):
        """Exportar un modelo grande tarda más que correr un script corto."""
        _, falso = self.exportar({"formato": "dae"})
        self.assertEqual(falso.ultima["timeout"], 180.0)

        falso_codigo = HttpFalso(RespuestaFalsa({"ok": True, "resultado": ""}))
        with mock.patch.object(sketchup.httpx, "post", falso_codigo):
            sketchup.ConectorSketchUp().ejecutar("sketchup_ejecutar_ruby", {"codigo": "1"})
        self.assertEqual(falso_codigo.ultima["timeout"], 120.0)

    def test_el_ruby_de_exportacion_es_el_que_viaja(self):
        _, falso = self.exportar({"formato": "ifc", "nombre": "torre"})
        codigo = falso.ultima["json"]["codigo"]
        self.assertIn("Sketchup.active_model.export(ruta)", codigo)
        self.assertIn("torre-", codigo)

    def test_la_marca_del_puente_se_devuelve(self):
        salida, _ = self.exportar(
            {"formato": "dae"},
            respuesta=RespuestaFalsa({"ok": True, "resultado": f"{entregables.MARCA} /tmp/x.dae"}),
        )
        self.assertIn(entregables.MARCA, salida)

    def test_el_aviso_de_version_gratuita_llega_al_usuario(self):
        aviso = "ERROR: exportar a DWG necesita SketchUp Pro."
        salida, _ = self.exportar(
            {"formato": "dwg"}, respuesta=RespuestaFalsa({"ok": True, "resultado": aviso})
        )
        self.assertIn("SketchUp Pro", salida)
        self.assertNotIn(entregables.MARCA, salida)

    def test_sketchup_cerrado_da_un_mensaje_util(self):
        falso = HttpFalso(sketchup.httpx.ConnectError("rechazada"))
        with mock.patch.object(sketchup.httpx, "post", falso):
            salida = sketchup.ConectorSketchUp().ejecutar("sketchup_exportar", {"formato": "dae"})
        self.assertIn("¿Está abierto", salida)

    def test_los_formatos_del_esquema_son_los_que_acepta(self):
        herramienta = next(h for h in sketchup.ConectorSketchUp().herramientas()
                           if h["nombre"] == "sketchup_exportar")
        self.assertEqual(herramienta["parametros"]["properties"]["formato"]["enum"],
                         list(sketchup._EXPORTABLES))


if __name__ == "__main__":
    unittest.main()
