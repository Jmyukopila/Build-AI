"""Recursos de render (Poly Haven), banco de referencias y visión de herramientas.

Sin red: los servicios externos se sustituyen por un transporte HTTP falso que
sirve respuestas con la forma real de cada API (comprobada contra las APIs en
vivo al escribir el código). El kit de Blender se verificó aparte en Blender
real; aquí se prueba lo que es nuestro: búsqueda, descarga verificada, rutas,
atribución y cómo llegan las imágenes al modelo.

    python -m unittest tests.test_recursos
"""

import base64
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import httpx
from PIL import Image

from buildai import agent, config as cfg, main
from buildai.providers.anthropic_provider import ProveedorAnthropic
from buildai.providers.openai_compat import ProveedorOpenAICompatible
from buildai.recursos import herramientas, polyhaven, referencias
from tests.dobles import ConectorFalso, kit_blender

_HTTPX_CLIENT = httpx.Client


def jpeg(ancho=1600, alto=1200, color=(180, 120, 90)):
    salida = io.BytesIO()
    Image.new("RGB", (ancho, alto), color).save(salida, "JPEG")
    return salida.getvalue()


CATALOGO_TEXTURAS = {
    "red_brick": {"name": "Red Brick", "tags": ["brick", "wall"], "categories": ["brick", "wall"],
                  "dimensions": [1400, 1400], "download_count": 900},
    "wood_floor": {"name": "Wood Floor", "tags": ["wood", "floor"], "categories": ["wood", "floor"],
                   "dimensions": [1700, 1700], "download_count": 500},
    "rusty_metal": {"name": "Rusty Metal", "tags": ["metal"], "categories": ["metal"],
                    "dimensions": [2000, 2000], "download_count": 50},
}


class ServidorFalso:
    """Transporte httpx que imita Poly Haven, Openverse, Pexels y los CDN de imágenes."""

    def __init__(self):
        self.peticiones = []
        self.archivos = {}
        self.pexels_estado = 200
        self.romper_md5 = False

    def archivo(self, url, contenido):
        self.archivos[url] = contenido
        md5 = hashlib.md5(contenido).hexdigest()
        return {"url": url, "md5": "0" * 32 if self.romper_md5 else md5, "size": len(contenido)}

    def __call__(self, peticion: httpx.Request) -> httpx.Response:
        url = str(peticion.url)
        self.peticiones.append(peticion)
        if url.startswith("https://api.polyhaven.com/assets"):
            return httpx.Response(200, json=CATALOGO_TEXTURAS)
        if url == "https://api.polyhaven.com/files/red_brick":
            base = "https://dl.polyhaven.org/red_brick"
            return httpx.Response(200, json={
                "Diffuse": {"2k": {"jpg": self.archivo(f"{base}/red_brick_diff_2k.jpg", b"color")}},
                "Rough": {"2k": {"jpg": self.archivo(f"{base}/red_brick_rough_2k.jpg", b"rugosidad")}},
                "nor_gl": {"1k": {"jpg": self.archivo(f"{base}/red_brick_nor_gl_1k.jpg", b"normal")}},
                "Displacement": {"2k": {"jpg": self.archivo(f"{base}/red_brick_disp_2k.jpg", b"disp")}},
            })
        if url == "https://api.polyhaven.com/files/sunset":
            return httpx.Response(200, json={"hdri": {
                "1k": {"hdr": self.archivo("https://dl.polyhaven.org/sunset_1k.hdr", b"hdr1k")},
                "2k": {"hdr": self.archivo("https://dl.polyhaven.org/sunset_2k.hdr", b"hdr2k")},
            }})
        if url == "https://api.polyhaven.com/files/Chair":
            principal = self.archivo("https://dl.polyhaven.org/Chair_1k.gltf", b"{}")
            principal["include"] = {
                "Chair.bin": self.archivo("https://dl.polyhaven.org/Chair.bin", b"bin"),
                "textures/Chair_diff.jpg": self.archivo("https://dl.polyhaven.org/Chair_diff.jpg", b"tex"),
                "../../fuera.txt": self.archivo("https://dl.polyhaven.org/malo", b"malo"),
            }
            return httpx.Response(200, json={"gltf": {"1k": {"gltf": principal}}})
        if url.startswith("https://api.openverse.org/"):
            return httpx.Response(200, json={"results": [
                {"title": "Casa blanca", "creator": "Ana", "license": "by", "license_version": "2.0",
                 "source": "flickr", "foreign_landing_url": "https://flickr.com/1", "url": "https://img.test/1.jpg"},
                {"title": "Sin imagen", "creator": "Luis", "license": "by", "url": "http://inseguro/2.jpg"},
                {"title": "Patio", "creator": "Eva", "license": "by-sa", "license_version": "4.0",
                 "source": "wikimedia", "foreign_landing_url": "https://commons/3", "url": "https://img.test/3.jpg"},
            ]})
        if url.startswith("https://api.pexels.com/"):
            if self.pexels_estado != 200:
                return httpx.Response(self.pexels_estado, json={"error": "no"})
            return httpx.Response(200, json={"photos": [
                {"alt": "Villa moderna", "photographer": "Pere", "url": "https://pexels.com/p/1",
                 "src": {"large": "https://img.test/pexels1.jpg"}},
            ]})
        if url.startswith("https://img.test/"):
            return httpx.Response(200, content=jpeg())
        if url in self.archivos:
            return httpx.Response(200, content=self.archivos[url])
        return httpx.Response(404)

    def cliente(self, **kwargs):
        kwargs.pop("transport", None)
        return _HTTPX_CLIENT(transport=httpx.MockTransport(self), **kwargs)


class BaseRecursos(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.datos = Path(self.tmp.name)
        self.servidor = ServidorFalso()
        for parche in (
            mock.patch.object(polyhaven.rutas, "CARPETA_DATOS", self.datos),
            mock.patch.object(polyhaven.httpx, "Client", self.servidor.cliente),
            mock.patch.object(agent, "CARPETA_RENDERS", self.datos / "renders"),
        ):
            parche.start()
            self.addCleanup(parche.stop)


# --------------------------------------------------------------- Poly Haven

class TestPolyHaven(BaseRecursos):
    def test_busca_en_espanol_y_ordena_por_relevancia(self):
        resultados = polyhaven.buscar("textura", "suelo de madera")
        self.assertEqual(resultados[0]["id"], "wood_floor")
        self.assertEqual(resultados[0]["tamano_m"], [1.7, 1.7])
        self.assertNotIn("rusty_metal", [r["id"] for r in resultados], "sin coincidencias no aparece")

    def test_el_catalogo_se_cachea(self):
        polyhaven.buscar("textura", "ladrillo")
        polyhaven.buscar("textura", "madera")
        consultas = [p for p in self.servidor.peticiones if "/assets" in str(p.url)]
        self.assertEqual(len(consultas), 1)

    def test_descarga_textura_con_md5_y_manifiesto(self):
        manifiesto = polyhaven.descargar("textura", "red_brick")
        self.assertEqual(set(manifiesto["mapas"]), {"color", "rugosidad", "normal"}, "sin desplazamiento")
        self.assertEqual(Path(manifiesto["mapas"]["normal"]).read_bytes(), b"normal",
                         "si falta la resolución pedida, se usa la más cercana")
        self.assertEqual(manifiesto["tamano_m"], [1.4, 1.4])
        self.assertEqual(polyhaven.ruta_manifest("textura", "red_brick").parent.name, "red_brick")
        self.assertTrue(polyhaven.buscar("textura", "ladrillo")[0]["descargado"])

    def test_md5_distinto_no_deja_archivos_a_medias(self):
        self.servidor.romper_md5 = True
        with self.assertRaisesRegex(polyhaven.ErrorRecursos, "dañado"):
            polyhaven.descargar("textura", "red_brick")
        carpeta = self.datos / "recursos" / "polyhaven" / "textura" / "red_brick"
        self.assertEqual(list(carpeta.glob("*")) if carpeta.exists() else [], [])

    def test_hdri_elige_resolucion(self):
        self.assertTrue(polyhaven.descargar("hdri", "sunset", "2k")["archivo"].endswith("sunset_2k.hdr"))
        self.assertTrue(polyhaven.descargar("hdri", "sunset", "4k")["archivo"].endswith("sunset_2k.hdr"))

    def test_modelo_baja_sus_dependencias_sin_salir_de_su_carpeta(self):
        manifiesto = polyhaven.descargar("modelo", "Chair")
        carpeta = Path(manifiesto["archivo"]).parent
        self.assertTrue((carpeta / "Chair.bin").is_file())
        self.assertTrue((carpeta / "textures" / "Chair_diff.jpg").is_file())
        self.assertFalse((self.datos / "recursos" / "fuera.txt").exists())
        self.assertFalse((carpeta.parent.parent / "fuera.txt").exists())

    def test_ids_y_tipos_invalidos(self):
        for malo in ("../x", "a/b", "", "x" * 200):
            with self.assertRaises(polyhaven.ErrorRecursos):
                polyhaven.descargar("textura", malo)
        with self.assertRaises(polyhaven.ErrorRecursos):
            polyhaven.buscar("coche", "x")

    def test_sin_conexion_es_un_error_legible(self):
        def caido(peticion):
            raise httpx.ConnectError("sin red")
        with mock.patch.object(polyhaven.httpx, "Client",
                               lambda **kw: _HTTPX_CLIENT(transport=httpx.MockTransport(caido), **kw)):
            with self.assertRaisesRegex(polyhaven.ErrorRecursos, "conexión"):
                polyhaven.buscar("hdri", "atardecer")


class TestKitBlender(unittest.TestCase):
    def test_el_kit_solo_lee_manifiestos_de_su_carpeta(self):
        with kit_blender() as (kit, _):
            with tempfile.TemporaryDirectory() as tmp:
                kit.CARPETA_RECURSOS = Path(tmp)
                destino = Path(tmp) / "textura" / "red_brick"
                destino.mkdir(parents=True)
                (destino / "manifest.json").write_text(json.dumps({"id": "red_brick"}))
                self.assertEqual(kit._manifiesto("textura", "ph:red_brick")["id"], "red_brick")
                self.assertEqual(kit._manifiesto("textura", "red_brick")["id"], "red_brick")
                for malo in ("../../etc", "a/b", ".oculto", "no_descargada"):
                    self.assertIsNone(kit._manifiesto("textura", malo))


# -------------------------------------------------------------- Referencias

class TestReferencias(BaseRecursos):
    def setUp(self):
        super().setUp()
        parche = mock.patch.object(referencias.httpx, "Client", self.servidor.cliente)
        parche.start()
        self.addCleanup(parche.stop)

    def test_openverse_sin_clave_con_atribucion_grabada(self):
        fotos, avisos = referencias.buscar("white house", 2, carpeta=self.datos / "renders")
        self.assertEqual([f["autor"] for f in fotos], ["Ana", "Eva"])
        self.assertTrue(any("Sin imagen" in a for a in avisos), "la foto sin https se salta con aviso")
        imagen = Image.open(fotos[0]["archivo"])
        self.assertEqual(imagen.width, 1024, "reducida")
        self.assertGreater(imagen.height, 768, "lleva la franja de atribución debajo")
        self.assertEqual(fotos[0]["licencia"], "CC BY 2.0")

    def test_con_clave_usa_pexels(self):
        fotos, _ = referencias.buscar("modern villa", 1, clave_pexels="k", carpeta=self.datos / "renders")
        self.assertEqual((fotos[0]["fuente"], fotos[0]["autor"]), ("Pexels", "Pere"))
        pedido = next(p for p in self.servidor.peticiones if "pexels" in str(p.url))
        self.assertEqual(pedido.headers["Authorization"], "k")

    def test_clave_de_pexels_mala_cae_a_openverse_en_auto(self):
        self.servidor.pexels_estado = 401
        fotos, avisos = referencias.buscar("villa", 1, clave_pexels="mala", carpeta=self.datos / "renders")
        self.assertEqual(fotos[0]["fuente"], "Openverse/flickr")
        self.assertTrue(any("Pexels no es válida" in a for a in avisos))
        with self.assertRaisesRegex(referencias.ErrorReferencias, "no es válida"):
            referencias.buscar("villa", 1, fuente="pexels", clave_pexels="mala", carpeta=self.datos)

    def test_consulta_vacia(self):
        with self.assertRaises(referencias.ErrorReferencias):
            referencias.buscar("  ", carpeta=self.datos)


# ------------------------------------------------------ herramientas y agente

class TestHerramientas(BaseRecursos):
    def setUp(self):
        super().setUp()
        parche = mock.patch.object(referencias.httpx, "Client", self.servidor.cliente)
        parche.start()
        self.addCleanup(parche.stop)

    def test_las_de_poly_haven_solo_con_blender(self):
        self.assertEqual([h["nombre"] for h in herramientas.herramientas(False)], [herramientas.REFERENCIAS])
        self.assertEqual(len(herramientas.herramientas(True)), 3)
        blender = ConectorFalso()
        blender.id = "blender"
        nombres = {h["nombre"] for h in agent._herramientas([blender])}
        self.assertIn(herramientas.DESCARGAR, nombres)
        self.assertNotIn(herramientas.DESCARGAR, {h["nombre"] for h in agent._herramientas([])})

    def test_descargar_dice_como_usarlo_en_el_kit(self):
        texto = herramientas.ejecutar(herramientas.DESCARGAR, {"tipo": "textura", "id": "ph:red_brick"})
        self.assertIn("material='ph:red_brick'", texto)
        self.assertIn("1.40 × 1.40 m", texto)

    def test_referencias_salen_como_imagenes_del_chat(self):
        with mock.patch.object(cfg, "cargar", return_value={"servicios": {"pexels": ""}}):
            texto = herramientas.ejecutar(herramientas.REFERENCIAS, {"consulta": "white house", "cantidad": 2})
        archivos = agent.renders_en_resultado(texto)
        self.assertEqual(len(archivos), 2)
        self.assertTrue(all(a.startswith("ref-") and a.endswith(".jpg") for a in archivos))
        self.assertIn("Ref. 1: «Casa blanca» — Ana · CC BY 2.0", texto)

    def test_errores_legibles(self):
        self.assertTrue(herramientas.ejecutar(herramientas.DESCARGAR, {"tipo": "textura", "id": "../x"}).startswith("ERROR"))


def _imagen_en_renders(carpeta, nombre, color):
    carpeta.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (1920, 1080), color).save(carpeta / nombre)


class TestVisionDeHerramientas(BaseRecursos):
    def historial(self):
        carpeta = self.datos / "renders"
        for k in range(6):
            _imagen_en_renders(carpeta, f"render-{k}.png", (k * 40, 0, 0))
        return [
            {"tipo": "usuario", "texto": "turno anterior"},
            {"tipo": "asistente", "texto": "", "llamadas": [], "_raw": None},
            {"tipo": "resultado", "id": "v", "nombre": "x", "contenido": "viejo", "imagenes": ["render-0.png"]},
            {"tipo": "usuario", "texto": "render"},
            {"tipo": "asistente", "texto": "", "llamadas": [], "_raw": None},
        ] + [
            {"tipo": "resultado", "id": str(k), "nombre": "x", "contenido": f"r{k}", "imagenes": [f"render-{k}.png"]}
            for k in range(1, 6)
        ]

    def test_solo_las_del_turno_en_curso_y_las_mas_recientes(self):
        vista = agent._historial_para_modelo(self.historial())
        con_imagen = [m["contenido"] for m in vista if m.get("imagenes_datos")]
        self.assertEqual(con_imagen, ["r2", "r3", "r4", "r5"], "como mucho 4, las últimas")
        imagen = Image.open(io.BytesIO(base64.b64decode(vista[-1]["imagenes_datos"][0]["datos"])))
        self.assertEqual((imagen.format, imagen.width), ("JPEG", 1024), "reducida para no inflar la petición")

    def test_adjuntos_del_usuario_tampoco_llegan_a_modelos_sin_vision(self):
        """Ollama devolvía 500 ("image input is not supported") y se reintentaba como saturado."""
        historial = [{"tipo": "usuario", "texto": "mira", "adjuntos": [{"media_type": "image/png", "datos": "x"}]}]
        (vista,) = agent._historial_para_modelo(historial, con_imagenes=False)
        self.assertNotIn("adjuntos", vista)
        self.assertIn("no puede ver imágenes", vista["texto"])
        self.assertIn("adjuntos", historial[0], "el historial guardado conserva la imagen")
        (con_vision,) = agent._historial_para_modelo(historial)
        self.assertIn("adjuntos", con_vision)

    def test_nada_para_modelos_sin_vision_ni_en_lo_guardado(self):
        historial = self.historial()
        vista = agent._historial_para_modelo(historial, con_imagenes=False)
        self.assertFalse(any(m.get("imagenes_datos") for m in vista))
        self.assertFalse(any("imagenes_datos" in m for m in historial), "el historial guardado no lleva base64")

    def test_anthropic_las_pone_en_el_tool_result(self):
        vista = [
            {"tipo": "resultado", "id": "a", "contenido": "uno",
             "imagenes_datos": [{"media_type": "image/jpeg", "datos": "QUJD"}]},
            {"tipo": "resultado", "id": "b", "contenido": "dos"},
        ]
        (mensaje,) = ProveedorAnthropic("k", "m")._convertir_historial(vista)
        primero, segundo = mensaje["content"]
        self.assertEqual([b["type"] for b in primero["content"]], ["text", "image"])
        self.assertEqual(segundo["content"], "dos")

    def test_openai_las_manda_despues_de_todos_los_resultados(self):
        from buildai.providers.base import LlamadaHerramienta

        vista = [
            {"tipo": "usuario", "texto": "hola"},
            {"tipo": "asistente", "texto": "", "llamadas": [LlamadaHerramienta("a", "x", {}), LlamadaHerramienta("b", "y", {})]},
            {"tipo": "resultado", "id": "a", "contenido": "uno",
             "imagenes_datos": [{"media_type": "image/jpeg", "datos": "QUJD"}]},
            {"tipo": "resultado", "id": "b", "contenido": "dos"},
        ]
        mensajes = ProveedorOpenAICompatible("http://x", "k", "m", "openai")._convertir_historial("s", vista)
        self.assertEqual([m["role"] for m in mensajes], ["system", "user", "assistant", "tool", "tool", "user"])
        self.assertEqual(mensajes[-1]["content"][1]["image_url"]["url"], "data:image/jpeg;base64,QUJD")


# ------------------------------------------------------------------ servidor

class TestServidor(BaseRecursos):
    def test_sirve_las_referencias_jpg_y_nada_fuera_de_su_carpeta(self):
        from fastapi.testclient import TestClient

        carpeta = self.datos / "renders"
        carpeta.mkdir(parents=True)
        (carpeta / "ref-abc.jpg").write_bytes(jpeg(10, 10))
        (carpeta / "notas.txt").write_text("x")
        with mock.patch.object(main, "CARPETA_RENDERS", carpeta):
            cliente = TestClient(main.app)
            r = cliente.get("/api/renders/ref-abc.jpg")
            self.assertEqual((r.status_code, r.headers["content-type"]), (200, "image/jpeg"))
            self.assertEqual(cliente.get("/api/renders/notas.txt").status_code, 404)

    def test_la_clave_de_pexels_se_guarda_pero_no_se_devuelve(self):
        from fastapi.testclient import TestClient

        cliente = TestClient(main.app)
        with mock.patch.object(cfg.rutas, "CARPETA_DATOS", self.datos), \
                mock.patch.object(cfg.rutas, "_RAIZ_PROYECTO", self.datos / "nada"):
            self.assertFalse(cliente.get("/api/config").json()["servicios_configurados"]["pexels"])
            cliente.post("/api/config", json={"servicios": {"pexels": " clave-secreta "}})
            respuesta = cliente.get("/api/config")
            self.assertTrue(respuesta.json()["servicios_configurados"]["pexels"])
            self.assertNotIn("clave-secreta", respuesta.text)
            self.assertEqual(cfg.cargar()["servicios"]["pexels"], "clave-secreta")
            cliente.post("/api/config", json={"servicios": {"pexels": ""}})
            self.assertEqual(cfg.cargar()["servicios"]["pexels"], "clave-secreta", "vacío no borra")


if __name__ == "__main__":
    unittest.main()
