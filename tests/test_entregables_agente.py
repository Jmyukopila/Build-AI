"""El circuito completo de un entregable: herramienta → agente → interfaz.

Las piezas sueltas ya están probadas una a una; aquí se comprueba que encajan:
que un turno real emite el evento `entregable`, que la marca sobrevive al recorte
de resultados largos (si no, el archivo existe pero la interfaz nunca se entera) y
que al recuperar una conversación guardada el entregable vuelve a aparecer.

    python -m unittest tests.test_entregables_agente
"""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from buildai import agent, entregables, sesiones
from buildai.providers.base import LlamadaHerramienta, RespuestaLLM
from tests.dobles import ConectorFalso, ProveedorFalso

CONFIG = {"proveedor": "anthropic", "claves": {"anthropic": "k"}, "modelos": {"anthropic": "m"}}


class BaseTurno(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.carpeta = Path(self.tmp.name)
        parche = mock.patch.object(entregables, "CARPETA_ENTREGABLES", self.carpeta)
        parche.start()
        self.addCleanup(parche.stop)

    def archivo(self, nombre="planta.dxf", contenido=b"0\nSECTION\n"):
        ruta = self.carpeta / nombre
        ruta.write_bytes(contenido)
        return ruta

    def turno(self, salida_herramienta):
        """Ejecuta un turno donde el modelo llama una vez a la herramienta falsa."""
        conector = ConectorFalso(salida=salida_herramienta)
        proveedor = ProveedorFalso([
            RespuestaLLM(llamadas=[LlamadaHerramienta("1", "falso_exportar", {})]),
            RespuestaLLM(texto="Ya lo tienes exportado."),
        ])
        historial, eventos = [], []
        with mock.patch.object(agent, "CONECTORES", [conector]), \
             mock.patch.object(agent, "crear_proveedor", return_value=proveedor), \
             mock.patch.object(agent, "_sistema", return_value="sistema de prueba"), \
             mock.patch.object(agent.cfg, "cargar", return_value=CONFIG), \
             mock.patch.object(agent, "buscar_herramienta",
                               lambda n: (conector, conector.herramientas()[0])):
            agent.ejecutar_turno(historial, "expórtame la planta", eventos.append)
        return eventos, historial


class TestEventoEntregable(BaseTurno):
    def test_un_turno_con_marca_emite_el_evento(self):
        ruta = self.archivo()
        eventos, _ = self.turno(f"Exportado.\n{entregables.MARCA} {ruta}")
        (evento,) = [e for e in eventos if e["tipo"] == "entregable"]
        self.assertEqual(evento["archivo"], "planta.dxf")
        self.assertEqual(evento["formato"], "DXF")
        self.assertEqual(evento["bytes"], 10)

    def test_sin_marca_no_se_emite_nada(self):
        eventos, _ = self.turno("Código ejecutado correctamente (sin salida).")
        self.assertEqual([e for e in eventos if e["tipo"] == "entregable"], [])

    def test_una_marca_que_apunta_fuera_de_la_carpeta_se_descarta(self):
        ajeno = Path(self.tmp.name).parent / "ajeno.dxf"
        ajeno.write_bytes(b"x")
        self.addCleanup(ajeno.unlink)
        eventos, _ = self.turno(f"{entregables.MARCA} {ajeno}")
        self.assertEqual([e for e in eventos if e["tipo"] == "entregable"], [])

    def test_varios_entregables_en_una_sola_llamada(self):
        rutas = [self.archivo("a.dxf"), self.archivo("b.ifc")]
        salida = "\n".join(f"{entregables.MARCA} {r}" for r in rutas)
        eventos, _ = self.turno(salida)
        formatos = [e["formato"] for e in eventos if e["tipo"] == "entregable"]
        self.assertEqual(formatos, ["DXF", "IFC"])

    def test_el_turno_termina_con_la_respuesta_del_modelo(self):
        eventos, _ = self.turno(f"{entregables.MARCA} {self.archivo()}")
        self.assertEqual(eventos[-1], {"tipo": "respuesta", "texto": "Ya lo tienes exportado."})


class TestRecorteDeResultados(BaseTurno):
    def test_la_marca_sobrevive_a_un_resultado_larguisimo(self):
        """Sin esto el archivo se genera pero la sesión guardada lo pierde."""
        ruta = self.archivo()
        relleno = "x" * (agent.MAX_RESULTADO + 500)
        _, historial = self.turno(f"{relleno}\n{entregables.MARCA} {ruta}")
        contenido = next(m["contenido"] for m in historial if m["tipo"] == "resultado")
        self.assertLess(len(contenido), len(relleno) + 500)
        self.assertIn(f"{entregables.MARCA} {ruta}", contenido)

    def test_conviven_la_marca_de_render_y_la_de_entregable(self):
        ruta = self.archivo()
        relleno = "x" * (agent.MAX_RESULTADO + 500)
        salida = (f"{relleno}\nRENDER_GUARDADO: /tmp/r.png\n{entregables.MARCA} {ruta}")
        _, historial = self.turno(salida)
        contenido = next(m["contenido"] for m in historial if m["tipo"] == "resultado")
        self.assertIn("RENDER_GUARDADO: /tmp/r.png", contenido)
        self.assertIn(f"{entregables.MARCA} {ruta}", contenido)

    def test_un_resultado_corto_no_se_toca(self):
        ruta = self.archivo()
        salida = f"Exportado.\n{entregables.MARCA} {ruta}"
        _, historial = self.turno(salida)
        contenido = next(m["contenido"] for m in historial if m["tipo"] == "resultado")
        self.assertEqual(contenido, salida)


class TestSesionRecuperada(BaseTurno):
    def test_para_ui_reconstruye_el_entregable(self):
        ruta = self.archivo("casa.ifc", b"ISO-10303-21;")
        historial = [
            {"tipo": "usuario", "texto": "exporta"},
            {"tipo": "resultado", "id": "1", "nombre": "revit_exportar",
             "contenido": f"Hecho.\n{entregables.MARCA} {ruta}"},
        ]
        eventos = sesiones.para_ui(historial)
        self.assertIn(
            {"tipo": "entregable", "archivo": "casa.ifc", "formato": "IFC", "bytes": 13},
            eventos,
        )

    def test_un_entregable_borrado_del_disco_ya_no_aparece(self):
        """Sesión antigua cuyo archivo el usuario ya movió o borró."""
        historial = [{"tipo": "resultado", "id": "1", "nombre": "x",
                      "contenido": f"{entregables.MARCA} {self.carpeta / 'ido.dwg'}"}]
        self.assertEqual(sesiones.para_ui(historial), [])


if __name__ == "__main__":
    unittest.main()
