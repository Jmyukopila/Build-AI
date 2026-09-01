"""Exportar desde Blender: qué se le manda al puente y qué operador se llama.

Blender solo escribe formatos de malla — ni IFC ni DWG — así que la mitad de esta
prueba es que el conector lo diga claro en vez de intentarlo y fallar dentro de
Blender. La otra mitad usa un `bpy` falso para comprobar que el kit elige el
operador correcto, incluida la caída a la ruta antigua de OBJ en Blender 3.

    python -m unittest tests.test_exportar_blender
"""

import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from buildai import entregables
from buildai.connectors import blender
from tests.dobles import OPERADORES_BLENDER_3, OPERADORES_BLENDER_4, kit_blender


class TestConectorBlender(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        parche = mock.patch.object(entregables, "CARPETA_ENTREGABLES", Path(self.tmp.name))
        parche.start()
        self.addCleanup(parche.stop)

    def exportar(self, argumentos, respuesta=None):
        enviar = mock.Mock(return_value=respuesta or {"ok": True, "resultado": "hecho"})
        with mock.patch.object(blender, "_enviar", enviar):
            salida = blender.ConectorBlender().ejecutar("blender_exportar", argumentos)
        return salida, enviar

    def _codigo_enviado(self, enviar):
        return enviar.call_args.args[0]["codigo"]

    def test_pedir_ifc_no_abre_el_puente(self):
        """Es el error más probable del modelo: pedirle BIM a un motor de render."""
        salida, enviar = self.exportar({"formato": "ifc"})
        enviar.assert_not_called()
        self.assertIn("no exporta a IFC", salida)
        self.assertIn("Revit", salida)

    def test_pedir_dwg_tampoco(self):
        salida, enviar = self.exportar({"formato": "dwg"})
        enviar.assert_not_called()
        self.assertIn("no exporta a DWG", salida)

    def test_el_codigo_llama_a_exportar_del_kit_con_la_ruta_de_entregables(self):
        _, enviar = self.exportar({"formato": "glb", "nombre": "casa moderna"})
        codigo = self._codigo_enviado(enviar)
        self.assertIn("exportar('glb', '", codigo)
        self.assertIn(str(entregables.CARPETA_ENTREGABLES), codigo)
        self.assertIn("casa-moderna-", codigo)

    def test_el_kit_viaja_junto_al_codigo(self):
        """Sin el kit por delante, `exportar` no existe dentro de Blender."""
        _, enviar = self.exportar({"formato": "glb"})
        self.assertIn("def exportar(formato, ruta):", self._codigo_enviado(enviar))

    def test_la_salida_del_puente_se_devuelve_tal_cual(self):
        salida, _ = self.exportar(
            {"formato": "glb"},
            respuesta={"ok": True, "resultado": f"{entregables.MARCA} /tmp/x.glb"},
        )
        self.assertIn(entregables.MARCA, salida)

    def test_un_error_del_puente_se_explica(self):
        salida, _ = self.exportar({"formato": "glb"}, respuesta={"ok": False, "error": "sin escena"})
        self.assertIn("ERROR en Blender", salida)
        self.assertIn("sin escena", salida)

    def test_blender_cerrado_da_un_mensaje_util(self):
        with mock.patch.object(blender, "_enviar", side_effect=OSError("conexión rechazada")):
            salida = blender.ConectorBlender().ejecutar("blender_exportar", {"formato": "glb"})
        self.assertIn("¿Está abierto", salida)

    def test_los_formatos_del_esquema_son_los_que_acepta(self):
        """El enum que ve el modelo y la validación no pueden divergir."""
        herramienta = next(h for h in blender.ConectorBlender().herramientas()
                           if h["nombre"] == "blender_exportar")
        self.assertEqual(herramienta["parametros"]["properties"]["formato"]["enum"],
                         list(blender._EXPORTABLES))


class TestKitExportar(unittest.TestCase):
    """El kit corre dentro de Blender, así que aquí se le pone un `bpy` falso."""

    def _exportar(self, formato, disponibles=None, fallan=(), sufijo=None):
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / f"modelo.{sufijo or formato}"
            with kit_blender(disponibles, fallan) as (kit, registro):
                salida = io.StringIO()
                with contextlib.redirect_stdout(salida):
                    devuelto = kit.exportar(formato, ruta)
            return devuelto, salida.getvalue(), registro

    def test_glb_usa_gltf_en_modo_binario(self):
        devuelto, texto, registro = self._exportar("glb")
        self.assertEqual(registro[0]["operador"], "export_scene.gltf")
        self.assertEqual(registro[0]["opciones"], {"export_format": "GLB"})
        self.assertIn(entregables.MARCA, texto)
        self.assertIsNotNone(devuelto)

    def test_gltf_usa_el_modo_separado(self):
        _, _, registro = self._exportar("gltf")
        self.assertEqual(registro[0]["opciones"], {"export_format": "GLTF_SEPARATE"})

    def test_cada_formato_llama_a_su_operador(self):
        for formato, operador in (("fbx", "export_scene.fbx"), ("obj", "wm.obj_export"),
                                  ("usd", "wm.usd_export"), ("stl", "wm.stl_export"),
                                  ("dae", "wm.collada_export")):
            with self.subTest(formato=formato):
                _, texto, registro = self._exportar(formato)
                self.assertEqual(registro[0]["operador"], operador)
                self.assertIn(entregables.MARCA, texto)

    def test_en_blender_3_obj_cae_al_operador_antiguo(self):
        """wm.obj_export no existe antes de Blender 4: hay que usar export_scene.obj."""
        _, texto, registro = self._exportar("obj", disponibles=OPERADORES_BLENDER_3)
        self.assertEqual(registro[0]["operador"], "export_scene.obj")
        self.assertIn(entregables.MARCA, texto)

    def test_si_el_primer_operador_revienta_prueba_el_siguiente(self):
        """Un Blender donde existen los dos exportadores de OBJ pero el nuevo falla."""
        _, texto, registro = self._exportar(
            "obj",
            disponibles=OPERADORES_BLENDER_4 | {"export_scene.obj"},
            fallan={"wm.obj_export"},
        )
        self.assertEqual([r["operador"] for r in registro],
                         ["wm.obj_export", "export_scene.obj"])
        self.assertIn(entregables.MARCA, texto)

    def test_formato_desconocido_no_llama_a_ningun_operador(self):
        devuelto, texto, registro = self._exportar("ifc")
        self.assertIsNone(devuelto)
        self.assertEqual(registro, [])
        self.assertIn("ERROR", texto)
        self.assertNotIn(entregables.MARCA, texto)

    def test_si_ningun_operador_sirve_lo_dice_sin_marca(self):
        devuelto, texto, _ = self._exportar(
            "obj",
            disponibles=OPERADORES_BLENDER_4 | {"export_scene.obj"},
            fallan={"wm.obj_export", "export_scene.obj"},
        )
        self.assertIsNone(devuelto)
        self.assertIn("ERROR", texto)
        self.assertNotIn(entregables.MARCA, texto)


if __name__ == "__main__":
    unittest.main()
