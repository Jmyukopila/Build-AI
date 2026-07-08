"""Regresión: _sanear_adjuntos filtra antes de aplicar el tope, no al revés.

Bug: el tope _MAX_ADJUNTOS se aplicaba sobre la lista cruda (`[:12]`) antes de
descartar entradas inválidas, así que unas pocas entradas inválidas al principio
reducían el número de imágenes válidas que llegaban al modelo.

    python -m unittest tests.test_sanear_adjuntos
"""

import base64
import unittest

from buildai.main import _sanear_adjuntos, _MAX_ADJUNTOS

_IMG = {"media_type": "image/jpeg", "datos": base64.b64encode(b"x").decode()}


class TestSanearAdjuntos(unittest.TestCase):
    def test_entradas_invalidas_no_gastan_cupo(self):
        # 3 basura + 12 imágenes válidas: deben sobrevivir las 12.
        bruto = [None, "nope", {"media_type": "text/plain", "datos": "aa"}] + [dict(_IMG)] * 12
        self.assertEqual(len(_sanear_adjuntos(bruto)), 12)

    def test_se_respeta_el_tope_con_todo_valido(self):
        bruto = [dict(_IMG)] * (_MAX_ADJUNTOS + 5)
        self.assertEqual(len(_sanear_adjuntos(bruto)), _MAX_ADJUNTOS)

    def test_descarta_no_imagenes_y_base64_invalido(self):
        bruto = [
            {"media_type": "application/pdf", "datos": _IMG["datos"]},
            {"media_type": "image/png", "datos": "no-es-base64-válido!!"},
            dict(_IMG),
        ]
        self.assertEqual(len(_sanear_adjuntos(bruto)), 1)


if __name__ == "__main__":
    unittest.main()
