"""Estáticos de la interfaz: deben revalidarse para que una actualización no muestre el logo viejo."""
import unittest

from fastapi.testclient import TestClient

from buildai.main import app


class TestEstaticosRevalidados(unittest.TestCase):
    def setUp(self):
        self.cliente = TestClient(app)

    def test_el_logo_se_revalida_siempre(self):
        r = self.cliente.get("/ui/assets/icono-marca.png")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers["cache-control"], "no-cache")
        # Sin ETag, no-cache obligaría a descargarlo entero cada vez en lugar de un 304.
        self.assertIn("etag", r.headers)

    def test_sin_cambios_responde_304(self):
        etag = self.cliente.get("/ui/app.js").headers["etag"]
        r = self.cliente.get("/ui/app.js", headers={"If-None-Match": etag})
        self.assertEqual(r.status_code, 304)

    def test_ruta_inexistente_sigue_dando_404(self):
        self.assertEqual(self.cliente.get("/ui/no-existe.png").status_code, 404)


if __name__ == "__main__":
    unittest.main()
