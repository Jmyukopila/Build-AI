"""IA incluida: el modelo gratuito y sin clave que BuildAI trae de serie.

Sin red ni GPU: las descargas se sirven con un transporte HTTP falso y el motor
no se arranca de verdad (eso se verificó aparte, con llama-server y el modelo
reales). Aquí se prueba lo que es nuestro: descarga verificada y reanudable,
estados que ve la interfaz, proveedor por defecto y modo ligero.

    python -m unittest tests.test_ia_local
"""

import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import httpx

from buildai import agent, config as cfg, ia_local
from buildai.providers import ErrorProveedor, crear_proveedor, probar_conexion

_HTTPX_STREAM = httpx.stream


class BaseIALocal(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        parche = mock.patch.object(ia_local.rutas, "CARPETA_DATOS", Path(self.tmp.name))
        parche.start()
        self.addCleanup(parche.stop)
        ia_local._estado.fijar("pendiente", "", 0.0)


def servidor(contenido: bytes, admite_rango=True):
    peticiones = []

    def responder(peticion):
        peticiones.append(peticion)
        rango = peticion.headers.get("Range")
        if rango and admite_rango:
            inicio = int(rango.split("=")[1].rstrip("-"))
            return httpx.Response(206, content=contenido[inicio:])
        return httpx.Response(200, content=contenido)

    def stream(metodo, url, **kwargs):
        cliente = httpx.Client(transport=httpx.MockTransport(responder))
        return cliente.stream(metodo, url, headers=kwargs.get("headers"))

    return stream, peticiones


class TestDescarga(BaseIALocal):
    CONTENIDO = b"modelo-gguf-de-prueba" * 1000

    def destino(self):
        return Path(self.tmp.name) / "modelos" / "m.gguf"

    def test_descarga_verificada_con_progreso(self):
        stream, _ = servidor(self.CONTENIDO)
        avance = []
        with mock.patch.object(ia_local.httpx, "stream", stream):
            ia_local._descargar("https://x/m.gguf", self.destino(), hashlib.sha256(self.CONTENIDO).hexdigest(),
                                len(self.CONTENIDO), avance.append)
        self.assertEqual(self.destino().read_bytes(), self.CONTENIDO)
        self.assertEqual(avance[-1], 1.0)

    def test_reanuda_donde_se_corto(self):
        parcial = self.destino().with_name("m.gguf.parcial")
        parcial.parent.mkdir(parents=True)
        parcial.write_bytes(self.CONTENIDO[:5000])
        stream, peticiones = servidor(self.CONTENIDO)
        with mock.patch.object(ia_local.httpx, "stream", stream):
            ia_local._descargar("https://x/m.gguf", self.destino(), hashlib.sha256(self.CONTENIDO).hexdigest(),
                                len(self.CONTENIDO))
        self.assertEqual(peticiones[0].headers["Range"], "bytes=5000-")
        self.assertEqual(self.destino().read_bytes(), self.CONTENIDO)

    def test_si_el_servidor_no_reanuda_empieza_de_cero(self):
        parcial = self.destino().with_name("m.gguf.parcial")
        parcial.parent.mkdir(parents=True)
        parcial.write_bytes(b"basura")
        stream, _ = servidor(self.CONTENIDO, admite_rango=False)
        with mock.patch.object(ia_local.httpx, "stream", stream):
            ia_local._descargar("https://x/m.gguf", self.destino(), hashlib.sha256(self.CONTENIDO).hexdigest(),
                                len(self.CONTENIDO))
        self.assertEqual(self.destino().read_bytes(), self.CONTENIDO)

    def test_archivo_danado_no_se_da_por_bueno(self):
        stream, _ = servidor(self.CONTENIDO)
        with mock.patch.object(ia_local.httpx, "stream", stream), self.assertRaisesRegex(ia_local.ErrorIALocal, "dañado"):
            ia_local._descargar("https://x/m.gguf", self.destino(), "0" * 64, len(self.CONTENIDO))
        self.assertFalse(self.destino().exists())
        self.assertFalse(self.destino().with_name("m.gguf.parcial").exists())


class TestMotorYEstado(BaseIALocal):
    def test_busca_el_motor_incluido_o_descargado(self):
        self.assertIsNone(ia_local.buscar_motor())
        binario = Path(self.tmp.name) / "ia_local" / "motor" / "llama-b1" / ia_local._nombre_binario()
        binario.parent.mkdir(parents=True)
        binario.write_bytes(b"#!")
        self.assertEqual(ia_local.buscar_motor(), binario)

    def test_las_versiones_fijadas_tienen_hash(self):
        for (sistema, arquitectura), (nombre, sha) in ia_local._MOTORES.items():
            self.assertIn(ia_local._VERSION_MOTOR, nombre)
            self.assertEqual(len(sha), 64)
        self.assertEqual(len(ia_local.MODELO["sha256"]), 64)

    def test_mientras_descarga_avisa_con_el_progreso_sin_bloquear(self):
        ia_local._estado.fijar("descargando", "Descargando…", 0.42)
        with mock.patch.object(ia_local, "_responde", return_value=False), \
                mock.patch.object(ia_local, "preparar_en_segundo_plano"):
            with self.assertRaisesRegex(ia_local.ErrorIALocal, "42 %"):
                ia_local.asegurar(espera_maxima=2)

    def test_si_ya_responde_se_usa_directamente(self):
        with mock.patch.object(ia_local, "_responde", return_value=True):
            self.assertEqual(ia_local.asegurar(), f"http://127.0.0.1:{ia_local.PUERTO}/v1")
        self.assertEqual(ia_local.estado()["fase"], "lista")

    def test_preparar_descarga_y_arranca(self):
        motor = Path(self.tmp.name) / "llama-server"
        motor.write_bytes(b"#!")
        with mock.patch.object(ia_local, "buscar_motor", return_value=motor), \
                mock.patch.object(ia_local, "_descargar") as descargar, \
                mock.patch.object(ia_local, "_arrancar_motor") as arrancar:
            ia_local._preparar()
        descargar.assert_called_once()
        arrancar.assert_called_once_with(motor)
        self.assertEqual(ia_local.estado()["fase"], "lista")

    def test_un_fallo_deja_el_estado_en_error_legible(self):
        with mock.patch.object(ia_local, "buscar_motor", side_effect=RuntimeError("disco lleno")):
            ia_local._preparar()
        estado = ia_local.estado()
        self.assertEqual(estado["fase"], "error")
        self.assertIn("disco lleno", estado["mensaje"])


class TestProveedorPorDefecto(BaseIALocal):
    def test_la_ia_incluida_es_el_proveedor_por_defecto_sin_clave(self):
        with mock.patch.object(cfg.rutas, "_RAIZ_PROYECTO", Path(self.tmp.name) / "nada"):
            config = cfg.cargar()
        self.assertEqual(config["proveedor"], "local")
        self.assertTrue(cfg.proveedor_listo(config), "no pide clave")

    def test_crear_proveedor_local_es_ligero_y_sin_vision(self):
        config = {"proveedor": "local", "claves": {}, "modelos": {}}
        with mock.patch.object(ia_local, "asegurar", return_value="http://127.0.0.1:8610/v1"):
            proveedor = crear_proveedor(config)
        self.assertTrue(proveedor.ligero)
        self.assertFalse(proveedor.ve_imagenes)
        self.assertEqual(proveedor.base_url, "http://127.0.0.1:8610/v1")
        self.assertEqual(proveedor.modelo, "qwen3.5-4b")

    def test_mientras_se_prepara_el_error_es_legible(self):
        config = {"proveedor": "local", "claves": {}, "modelos": {}}
        with mock.patch.object(ia_local, "asegurar", side_effect=ia_local.ErrorIALocal("preparando (10 %)")):
            with self.assertRaisesRegex(ErrorProveedor, "preparando"):
                crear_proveedor(config)

    def test_probar_conexion_activa_la_preparacion(self):
        with mock.patch.object(ia_local, "preparar_en_segundo_plano") as preparar:
            texto = probar_conexion({"proveedor": "local", "claves": {}, "modelos": {}})
        preparar.assert_called_once()
        self.assertIn("IA incluida", texto)


class TestNoFingirTrabajo(unittest.TestCase):
    """Un modelo pequeño contestó «He creado la casa» sin ejecutar nada (visto en real)."""

    def turno(self, respuestas, mensaje="Crea un muro de 5 m"):
        from buildai.providers.base import RespuestaLLM, LlamadaHerramienta
        from tests.dobles import ConectorFalso, ProveedorFalso

        proveedor = ProveedorFalso(respuestas)
        proveedor.ligero = True
        conector = ConectorFalso(salida="✔ Muro", nombre_herramienta="blender_ejecutar_python")
        historial, eventos = [], []
        with mock.patch.object(agent, "crear_proveedor", return_value=proveedor), \
                mock.patch.object(agent, "CONECTORES", [conector]), \
                mock.patch.object(agent, "buscar_herramienta", lambda n: (conector, conector.herramientas()[0])), \
                mock.patch.object(agent.cfg, "cargar", return_value={"proveedor": "local", "claves": {}, "modelos": {}}):
            agent.ejecutar_turno(historial, mensaje, eventos.append)
        return historial, eventos, conector, proveedor

    def test_si_dice_que_lo_hizo_sin_ejecutar_se_le_obliga_a_hacerlo(self):
        from buildai.providers.base import RespuestaLLM, LlamadaHerramienta
        historial, eventos, conector, _ = self.turno([
            RespuestaLLM(texto="He creado el muro."),                                    # mentira
            RespuestaLLM(llamadas=[LlamadaHerramienta("1", "blender_ejecutar_python", {"codigo": "muro((0,0),(5,0))"})]),
            RespuestaLLM(texto="Muro creado de verdad."),
        ])
        self.assertEqual(len(conector.ejecuciones), 1)
        respuestas = [e["texto"] for e in eventos if e["tipo"] == "respuesta"]
        self.assertEqual(respuestas, ["Muro creado de verdad."], "la respuesta falsa no llega al usuario")
        from buildai import sesiones
        self.assertFalse(any("[BuildAI]" in (e.get("texto") or "") for e in sesiones.para_ui(historial)),
                         "el recordatorio interno no se pinta como mensaje del usuario")

    def test_una_pregunta_no_dispara_el_recordatorio(self):
        from buildai.providers.base import RespuestaLLM
        _, eventos, conector, proveedor = self.turno([RespuestaLLM(texto="Un muro exterior suele medir 20 cm.")],
                                                    mensaje="¿Cuánto mide un muro exterior?")
        self.assertEqual(len(proveedor.conversaciones), 1)

    def test_como_mucho_dos_recordatorios(self):
        from buildai.providers.base import RespuestaLLM
        _, eventos, _, proveedor = self.turno([RespuestaLLM(texto="Hecho.")] * 5)
        self.assertEqual(len(proveedor.conversaciones), 3, "1 respuesta + 2 recordatorios, sin bucle infinito")


class TestInstalador(unittest.TestCase):
    """El instalador descarga lo mismo que BuildAI espera: si uno cambia y el otro no,
    el modelo bajado en la instalación no se reconocería (o el motor no cuadraría)."""

    RAIZ = Path(__file__).resolve().parent.parent

    def test_el_iss_descarga_el_modelo_que_espera_buildai(self):
        iss = (self.RAIZ / "empaquetado" / "BuildAI.iss").read_text(encoding="utf-8")
        for valor in (ia_local.MODELO["archivo"], ia_local.MODELO["url"], ia_local.MODELO["sha256"]):
            self.assertIn(valor, iss)
        self.assertIn(r".buildai\ia_local\modelos", iss)

    def test_el_script_mete_el_motor_fijado(self):
        ps1 = (self.RAIZ / "empaquetado" / "build_installer.ps1").read_text(encoding="utf-8")
        nombre, sha = ia_local._MOTORES[("Windows", "x64")]
        self.assertIn(nombre, ps1)
        self.assertIn(sha, ps1)
        self.assertIn(r"dist\BuildAI\motor", ps1)


class TestModoLigero(unittest.TestCase):
    def test_instrucciones_y_herramientas_compactas(self):
        from buildai.connectors.blender import ConectorBlender

        completo, ligero = agent._sistema([], "hola"), agent._sistema([], "hola", ligero=True)
        self.assertLess(len(ligero), len(completo) / 5)
        self.assertIn("muro exterior 0,20 m", ligero)
        blender = ConectorBlender()
        with mock.patch.object(ConectorBlender, "disponible", return_value=True):
            normal = agent._herramientas([blender])
            compacto = agent._herramientas([blender], ligero=True)
        tam = lambda hs: sum(len(h["descripcion"]) for h in hs)
        self.assertLess(tam(compacto), tam(normal) / 2)
        de_blender = lambda hs: [h["nombre"] for h in hs if h["nombre"].startswith("blender_")]
        self.assertEqual(de_blender(normal), de_blender(compacto), "las mismas herramientas de Blender")
        self.assertNotIn("recursos_descargar", [h["nombre"] for h in compacto], "sin flujos de varios pasos")

    def test_error_de_contexto_de_ollama_doblemente_envuelto(self):
        import httpx
        from buildai.providers.base import ErrorContextoExcedido
        from buildai.providers.openai_compat import ProveedorOpenAICompatible

        p = ProveedorOpenAICompatible("http://x/v1", "k", "qwen3", "ollama")
        cuerpo = {"error": {"message": '{"error":{"code":400,"message":"request (4268 tokens) exceeds the '
                                       'available context size (4096 tokens)"}}', "type": "invalid_request_error"}}
        r = httpx.Response(400, json=cuerpo, request=httpx.Request("POST", "http://x"))
        detalle = p._detalle_error(r)
        self.assertTrue(detalle.startswith("request (4268 tokens)"), detalle)
        self.assertIsInstance(p._error_definitivo(400, detalle), ErrorContextoExcedido)

    def test_el_agente_reintenta_con_menos_conversacion(self):
        from buildai.providers.base import ErrorContextoExcedido, RespuestaLLM
        from tests.dobles import ProveedorFalso

        class Pequeno(ProveedorFalso):
            ligero, presupuesto, llamadas = True, 8000, 0

            def conversar(self, sistema, historial, herramientas):
                Pequeno.llamadas += 1
                if Pequeno.llamadas == 1:
                    raise ErrorContextoExcedido("no cabe")
                return RespuestaLLM(texto="hecho")

        historial = [{"tipo": "usuario", "texto": "antiguo " + "x" * 6000},
                     {"tipo": "asistente", "texto": "ok", "llamadas": [], "_raw": None}]
        eventos = []
        config = {"proveedor": "local", "claves": {}, "modelos": {}}
        with mock.patch.object(agent, "crear_proveedor", return_value=Pequeno([])), \
                mock.patch.object(agent, "CONECTORES", []), \
                mock.patch.object(agent.cfg, "cargar", return_value=config):
            agent.ejecutar_turno(historial, "nuevo", eventos.append)
        self.assertEqual(Pequeno.llamadas, 2)
        self.assertIn("hecho", [e.get("texto") for e in eventos])

    def test_el_contexto_se_ajusta_quitando_turnos_enteros(self):
        largo = "x" * 10000
        vista = [
            {"tipo": "usuario", "texto": "uno " + largo},
            {"tipo": "asistente", "texto": largo, "llamadas": []},
            {"tipo": "usuario", "texto": "dos"},
            {"tipo": "asistente", "texto": "", "llamadas": [object()]},
            {"tipo": "resultado", "contenido": "ok"},
        ]
        ajustada = agent._ajustar_a_contexto(vista, 5000)
        self.assertEqual(ajustada[0]["texto"], "dos", "empieza en un turno de usuario")
        self.assertEqual(ajustada[-1]["tipo"], "resultado", "la llamada conserva su resultado")


if __name__ == "__main__":
    unittest.main()
