"""Conectar la IA: claves pegadas con basura, errores legibles y prueba de conexión.

Cada caso nace de un fallo real al configurar la clave:
- un carácter invisible al copiarla reventaba httpx ("Error inesperado");
- un salto de línea se reintentaba 5 veces (minutos) como si fuera un corte de red;
- Haiku 4.5 recibía thinking adaptativo y devolvía un 400 en cada mensaje;
- los errores 402/403/404 llegaban como JSON en bruto;
- el error no aparecía al guardar, sino a mitad del primer encargo.

    python -m unittest tests.test_conexion_ia
"""

import tempfile
import time
import types
import unittest
from pathlib import Path
from unittest import mock

import anthropic
import httpx

from buildai import config as cfg, main
from buildai.providers import ErrorProveedor, crear_proveedor, probar_conexion
from buildai.providers import openai_compat
from buildai.providers.anthropic_provider import ProveedorAnthropic, admite_pensamiento_adaptativo
from buildai.providers.claves import ClaveInvalida, aviso_proveedor, limpiar
from buildai.providers.openai_compat import ProveedorOpenAICompatible


class TestLimpiarClave(unittest.TestCase):
    def test_quita_la_basura_tipica_de_copiar_y_pegar(self):
        casos = {
            "  sk-or-v1-abc  ": "sk-or-v1-abc",
            "sk-or-v1-abc\n": "sk-or-v1-abc",
            "sk-or-​v1-abc": "sk-or-v1-abc",           # espacio de anchura cero
            "﻿sk-ant-api03-xyz": "sk-ant-api03-xyz",      # BOM
            "sk-ant-xyz ": "sk-ant-xyz",                  # espacio duro
            '"sk-proj-abc"': "sk-proj-abc",
            "“AIzaSyAbc”": "AIzaSyAbc",                         # comillas tipográficas
            "Bearer sk-or-v1-abc": "sk-or-v1-abc",
            "OPENAI_API_KEY=sk-proj-abc": "sk-proj-abc",
            "export ANTHROPIC_API_KEY='sk-ant-abc'": "sk-ant-abc",
            "abc123==": "abc123==",                             # no recorta claves que acaban en =
            "": "",
        }
        for sucia, limpia in casos.items():
            with self.subTest(sucia=sucia):
                self.assertEqual(limpiar(sucia), limpia)

    def test_rechaza_lo_que_no_puede_ser_una_clave(self):
        for mala in ("sk-or-ñandú", "sk or v1", "sk-or\nv1-abc", "sk-ü"):
            with self.subTest(mala=mala), self.assertRaises(ClaveInvalida):
                limpiar(mala)

    def test_avisa_si_la_clave_es_de_otro_proveedor(self):
        self.assertIn("OpenRouter", aviso_proveedor("sk-or-v1-abc", "anthropic"))
        self.assertIn("Anthropic", aviso_proveedor("sk-ant-api03-x", "openai"))
        self.assertIn("Gemini", aviso_proveedor("AIzaSyX", "openrouter"))
        self.assertIsNone(aviso_proveedor("sk-ant-api03-x", "anthropic"))
        self.assertIsNone(aviso_proveedor("sk-proj-x", "openai"))
        self.assertIsNone(aviso_proveedor("lo-que-sea", "opencode"), "formato desconocido: no se juzga")


class TestCrearProveedor(unittest.TestCase):
    def config(self, proveedor, clave, modelo=""):
        return {"proveedor": proveedor, "claves": {proveedor: clave}, "modelos": {proveedor: modelo}}

    def test_limpia_claves_guardadas_antes_del_arreglo(self):
        proveedor = crear_proveedor(self.config("openrouter", "sk-or-​abc\n"))
        self.assertEqual(proveedor.clave, "sk-or-abc")

    def test_clave_imposible_es_un_error_legible(self):
        with self.assertRaisesRegex(ErrorProveedor, "caracteres"):
            crear_proveedor(self.config("openrouter", "sk-or-ñ"))

    def test_sin_modelo_usa_el_de_por_defecto(self):
        self.assertEqual(crear_proveedor(self.config("anthropic", "sk-ant-x")).modelo, "claude-opus-5-5")
        self.assertEqual(crear_proveedor(self.config("openai", "sk-x")).modelo, cfg.MODELOS_POR_DEFECTO["openai"])


class TestAnthropic(unittest.TestCase):
    def test_pensamiento_adaptativo_solo_donde_existe(self):
        for modelo in ("claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5", "claude-fable-5-2",
                       "claude-haiku-5-5", "claude-opus-4-6", "claude-mythos-5-2"):
            self.assertTrue(admite_pensamiento_adaptativo(modelo), modelo)
        for modelo in ("claude-haiku-4-5", "claude-haiku-4-5-20251001", "claude-sonnet-4-5",
                       "claude-opus-4-5-20251101", "claude-opus-4-20250514", "claude-3-7-sonnet-latest"):
            self.assertFalse(admite_pensamiento_adaptativo(modelo), modelo)

    def _conversar_con(self, modelo):
        capturado = {}

        class Mensajes:
            def create(self, **kwargs):
                capturado.update(kwargs)
                return types.SimpleNamespace(stop_reason="end_turn", content=[])

        cliente = types.SimpleNamespace(messages=Mensajes())
        with mock.patch.object(anthropic, "Anthropic", return_value=cliente):
            ProveedorAnthropic("sk-ant-x", modelo).conversar("s", [{"tipo": "usuario", "texto": "hola"}], [])
        return capturado

    def test_haiku_4_5_ya_no_recibe_thinking_adaptativo(self):
        self.assertNotIn("thinking", self._conversar_con("claude-haiku-4-5"))
        self.assertEqual(self._conversar_con("claude-opus-5-5")["thinking"], {"type": "adaptive"})

    def _error(self, clase, codigo, mensaje="detalle"):
        respuesta = httpx.Response(codigo, request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"))
        return clase(mensaje, response=respuesta, body=None)

    def test_errores_traducidos_del_mas_concreto_al_mas_general(self):
        p = ProveedorAnthropic("sk-ant-x", "claude-inventado")
        casos = [
            (self._error(anthropic.AuthenticationError, 401), "no es válida"),
            (self._error(anthropic.PermissionDeniedError, 403), "no tiene permiso"),
            (self._error(anthropic.NotFoundError, 404), "«claude-inventado» no existe"),
            (self._error(anthropic.RateLimitError, 429), "limitando"),
            (self._error(anthropic.BadRequestError, 400, "Your credit balance is too low"), "no tiene saldo"),
            (self._error(anthropic.InternalServerError, 529), "problemas ahora mismo"),
        ]
        for exc, esperado in casos:
            with self.subTest(clase=type(exc).__name__):
                self.assertIn(esperado, str(p._traducir_error(exc)))

    def test_probar_usa_la_api_de_modelos_sin_gastar_tokens(self):
        cliente = mock.Mock()
        with mock.patch.object(anthropic, "Anthropic", return_value=cliente):
            texto = ProveedorAnthropic("sk-ant-x", "claude-opus-5-5").probar()
        cliente.models.retrieve.assert_called_once_with("claude-opus-5-5")
        cliente.messages.create.assert_not_called()
        self.assertIn("disponible", texto)


def respuesta(codigo, json=None):
    return httpx.Response(codigo, json=json if json is not None else {},
                          request=httpx.Request("POST", "https://x/v1/chat/completions"))


class TestOpenAICompatible(unittest.TestCase):
    def setUp(self):
        self.p = ProveedorOpenAICompatible("https://x/v1", "sk-or-abc", "modelo-x", "openrouter")
        dormir = mock.patch.object(openai_compat.time, "sleep")
        dormir.start()
        self.addCleanup(dormir.stop)

    def conversar(self, lado):
        with mock.patch.object(openai_compat.httpx, "post", side_effect=lado) as post:
            try:
                self.p.conversar("s", [{"tipo": "usuario", "texto": "hola"}], [])
            except ErrorProveedor as exc:
                return str(exc), post.call_count
        return None, post.call_count

    def test_clave_con_basura_no_se_reintenta_como_un_corte_de_red(self):
        for fallo in (httpx.LocalProtocolError("Illegal header value"), UnicodeEncodeError("ascii", "x", 0, 1, "x")):
            with self.subTest(fallo=type(fallo).__name__):
                mensaje, llamadas = self.conversar(fallo)
                self.assertEqual(llamadas, 1, "sin reintentos ni esperas de minutos")
                self.assertIn("caracteres no válidos", mensaje)

    def test_errores_explicados_sin_json_en_bruto(self):
        casos = [
            (respuesta(402, {"error": {"message": "Insufficient credits"}}), "no tiene saldo"),
            (respuesta(403, {"error": {"message": "Key disabled"}}), "rechaza la petición"),
            (respuesta(404, {"error": {"message": "No endpoints found"}}), "«modelo-x» no existe"),
            (respuesta(400, {"error": {"message": "model 'modelo-x' is not a valid model ID"}}), "no existe"),
            (respuesta(200, {"error": {"code": 402, "message": "Insufficient credits"}}), "no tiene saldo"),
            (respuesta(200, {"error": "texto suelto"}), "texto suelto"),
            (respuesta(401), "no es válida"),
            # Gemini: clave inválida con 400 (comprobado contra su API real).
            (respuesta(400, [{"error": {"message": "API key not valid. Please pass a valid API key."}}]), "no es válida"),
        ]
        for resp, esperado in casos:
            with self.subTest(codigo=resp.status_code, esperado=esperado):
                mensaje, _ = self.conversar([resp])
                self.assertIn(esperado, mensaje)
                self.assertNotIn('{"error"', mensaje)

    def test_probar_hace_una_sola_peticion_minima(self):
        self.p.nombre = "openai"  # OpenRouter usa /key (ver TestSaturacion)
        with mock.patch.object(openai_compat.httpx, "post", return_value=respuesta(200, {"choices": [{"message": {"content": "ok"}}]})) as post:
            self.assertIn("responde", self.p.probar())
        self.assertEqual(post.call_count, 1)
        self.assertEqual(post.call_args.kwargs["json"]["max_tokens"], 16)

    def test_probar_con_limite_de_uso_da_la_clave_por_buena(self):
        self.p.nombre = "openai"
        with mock.patch.object(openai_compat.httpx, "post", return_value=respuesta(429)):
            self.assertIn("Clave válida", self.p.probar())

    def test_probar_modelo_inexistente(self):
        self.p.nombre = "openai"
        with mock.patch.object(openai_compat.httpx, "post", return_value=respuesta(404, {"error": {"message": "no"}})):
            with self.assertRaisesRegex(ErrorProveedor, "no existe"):
                self.p.probar()


def limite_openrouter(restantes, renovar_en_s, mensaje="Rate limit exceeded"):
    """429 de un límite PROPIO de OpenRouter: según su documentación lleva X-RateLimit-*."""
    reset_ms = str(int((time.time() + renovar_en_s) * 1000))
    return httpx.Response(
        429, json={"error": {"code": 429, "message": mensaje}},
        headers={"X-RateLimit-Limit": "50", "X-RateLimit-Remaining": str(restantes), "X-RateLimit-Reset": reset_ms},
        request=httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions"),
    )


def ok(texto="hecho"):
    return respuesta(200, {"choices": [{"message": {"content": texto}}]})


class TestSaturacion(unittest.TestCase):
    """«Los agentes están saturados»: casi siempre los modelos gratuitos de OpenRouter."""

    def setUp(self):
        self.p = ProveedorOpenAICompatible("https://openrouter.ai/api/v1", "sk-or-x", "libre-a:free", "openrouter")
        self.avisos = []
        self.p.notificar = self.avisos.append
        self.esperas = []
        dormir = mock.patch.object(openai_compat.time, "sleep", side_effect=self.esperas.append)
        dormir.start()
        self.addCleanup(dormir.stop)
        ritmo = mock.patch.object(ProveedorOpenAICompatible, "_respetar_ritmo")
        ritmo.start()
        self.addCleanup(ritmo.stop)

    def conversar(self, respuestas):
        with mock.patch.object(openai_compat.httpx, "post", side_effect=respuestas) as post:
            resultado = self.p.conversar("s", [{"tipo": "usuario", "texto": "hola"}], [])
        return resultado, post

    def test_cupo_diario_agotado_no_reintenta_y_lo_explica(self):
        with self.assertRaises(ErrorProveedor) as ctx:
            self.conversar([limite_openrouter(0, 6 * 3600)])
        mensaje = str(ctx.exception)
        self.assertIn("peticiones gratuitas de hoy", mensaje)
        self.assertIn("No es que esté saturado", mensaje)
        self.assertIn("se renuevan hacia las", mensaje)
        self.assertEqual(self.esperas, [], "ni un segundo de espera inútil")

    def test_limite_por_minuto_espera_lo_justo(self):
        resultado, post = self.conversar([limite_openrouter(0, 20), ok()])
        self.assertEqual(resultado.texto, "hecho")
        self.assertEqual(len(self.esperas), 1)
        self.assertTrue(19 <= self.esperas[0] <= 22, self.esperas)

    def test_modelo_saturado_pasa_a_otro_gratuito(self):
        self.p.buscar_alternativas = lambda con_imagenes: ["libre-b:free", "libre-c:free"]
        saturado = respuesta(503, {"error": {"message": "overloaded"}})
        resultado, post = self.conversar([saturado, saturado, ok("desde b")])
        self.assertEqual(resultado.texto, "desde b")
        self.assertEqual(post.call_args.kwargs["json"]["model"], "libre-b:free")
        self.assertEqual(self.p.modelo, "libre-b:free", "el resto del turno sigue con el que funciona")
        self.assertTrue(any("sigo con «libre-b:free»" in a for a in self.avisos))

    def test_cada_alternativa_tiene_su_presupuesto_y_el_bucle_termina(self):
        self.p.buscar_alternativas = lambda con_imagenes: ["libre-b:free"]
        with self.assertRaises(ErrorProveedor):
            self.conversar([respuesta(503)] * 50)
        # 2 fallos con el primero, cambio, y luego el presupuesto completo del segundo.
        self.assertEqual(self.p.modelo, "libre-b:free")

    def test_sin_alternativas_reintenta_como_antes(self):
        resultado, post = self.conversar([respuesta(502), respuesta(502), ok()])
        self.assertEqual(resultado.texto, "hecho")
        self.assertEqual(post.call_count, 3)

    def test_probar_openrouter_no_gasta_cupo_y_dice_cuanto_queda(self):
        clave = httpx.Response(200, json={"data": {"free_model_daily_requests": {"used": 12, "limit": 50, "remaining": 38}}},
                               request=httpx.Request("GET", "https://openrouter.ai/api/v1/key"))
        with mock.patch.object(openai_compat.httpx, "get", return_value=clave), \
                mock.patch.object(openai_compat.httpx, "post") as post, \
                mock.patch("buildai.modelos.listar", return_value={"modelos": [{"id": "libre-a:free"}], "nota": ""}):
            texto = self.p.probar()
        post.assert_not_called()
        self.assertIn("Hoy te quedan 38 de 50", texto)

    def test_probar_openrouter_con_cupo_a_cero(self):
        clave = httpx.Response(200, json={"data": {"free_model_daily_requests": {"used": 50, "limit": 50, "remaining": 0}}},
                               request=httpx.Request("GET", "https://openrouter.ai/api/v1/key"))
        with mock.patch.object(openai_compat.httpx, "get", return_value=clave), \
                mock.patch("buildai.modelos.listar", return_value={"modelos": [{"id": "libre-a:free"}], "nota": ""}):
            with self.assertRaisesRegex(ErrorProveedor, "peticiones gratuitas de hoy"):
                self.p.probar()


class TestAlternativas(unittest.TestCase):
    CATALOGO = {"modelos": [
        {"id": "texto:free", "ve_imagenes": False}, {"id": "vision:free", "ve_imagenes": True},
        {"id": "elegido:free", "ve_imagenes": True}, {"id": "de-pago", "ve_imagenes": True},
    ], "nota": ""}

    def test_nunca_ofrece_modelos_de_pago_ni_el_mismo(self):
        from buildai import modelos
        with mock.patch.object(modelos, "listar", return_value=self.CATALOGO):
            self.assertEqual(modelos.alternativas_gratuitas("openrouter", "elegido:free"), ["texto:free", "vision:free"])
            self.assertEqual(modelos.alternativas_gratuitas("openrouter", "elegido:free", con_imagenes=True)[0], "vision:free")
            self.assertEqual(modelos.alternativas_gratuitas("openrouter", "de-pago"), [], "un modelo de pago no cambia solo")

    def test_crear_proveedor_solo_prepara_alternativas_para_gratuitos(self):
        gratis = crear_proveedor({"proveedor": "openrouter", "claves": {"openrouter": "sk-or-x"}, "modelos": {"openrouter": "a:free"}})
        pago = crear_proveedor({"proveedor": "openrouter", "claves": {"openrouter": "sk-or-x"}, "modelos": {"openrouter": "openai/gpt-5.5"}})
        otro = crear_proveedor({"proveedor": "openai", "claves": {"openai": "sk-x"}, "modelos": {}})
        self.assertIsNotNone(gratis.buscar_alternativas)
        self.assertIsNone(pago.buscar_alternativas)
        self.assertIsNone(otro.buscar_alternativas)


class TestOllama(unittest.TestCase):
    def test_modelo_no_instalado(self):
        config = {"proveedor": "ollama", "claves": {}, "modelos": {"ollama": "llama-que-no-hay"}}
        tags = mock.Mock(json=lambda: {"models": [{"name": "qwen3:4b"}]})
        with mock.patch("buildai.providers._ollama_ve_imagenes", return_value=False), \
                mock.patch("httpx.get", return_value=tags):
            with self.assertRaisesRegex(ErrorProveedor, "ollama pull llama-que-no-hay"):
                probar_conexion(config)


class TestServidor(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        for parche in (mock.patch.object(cfg.rutas, "CARPETA_DATOS", Path(self.tmp.name)),
                       mock.patch.object(cfg.rutas, "_RAIZ_PROYECTO", Path(self.tmp.name) / "nada")):
            parche.start()
            self.addCleanup(parche.stop)
        from fastapi.testclient import TestClient
        self.cliente = TestClient(main.app)

    def test_guardar_limpia_la_clave(self):
        r = self.cliente.post("/api/config", json={"proveedor": "openrouter", "claves": {"openrouter": " sk-or-​abc\n"}}).json()
        self.assertTrue(r["ok"])
        self.assertEqual(cfg.cargar()["claves"]["openrouter"], "sk-or-abc")

    def test_clave_imposible_no_se_guarda_y_se_explica(self):
        r = self.cliente.post("/api/config", json={"proveedor": "openrouter", "claves": {"openrouter": "sk-or-ñ"}}).json()
        self.assertFalse(r["ok"])
        self.assertIn("caracteres", r["error"])
        self.assertEqual(cfg.cargar()["claves"]["openrouter"], "")

    def test_avisa_de_clave_en_el_proveedor_equivocado(self):
        r = self.cliente.post("/api/config", json={"proveedor": "anthropic", "claves": {"anthropic": "sk-or-v1-abc"}}).json()
        self.assertTrue(r["ok"])
        self.assertIn("OpenRouter", r["avisos"][0])

    def test_probar_devuelve_siempre_un_mensaje(self):
        with mock.patch.object(main, "probar_conexion", return_value="Conectado"):
            self.assertEqual(self.cliente.post("/api/config/probar").json(), {"ok": True, "mensaje": "Conectado"})
        with mock.patch.object(main, "probar_conexion", side_effect=ErrorProveedor("La clave no es válida")):
            self.assertEqual(self.cliente.post("/api/config/probar").json()["error"], "La clave no es válida")
        with mock.patch.object(main, "probar_conexion", side_effect=RuntimeError("raro")):
            self.assertIn("raro", self.cliente.post("/api/config/probar").json()["error"])

    def test_el_oauth_roto_de_opencode_ya_no_se_ofrece(self):
        self.assertFalse(cfg.PROVEEDORES["opencode"]["oauth_disponible"])


if __name__ == "__main__":
    unittest.main()
