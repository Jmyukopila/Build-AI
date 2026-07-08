"""Regresión: las imágenes de turnos ya cerrados no deben reenviarse al modelo.

Bug: los adjuntos (imágenes en base64) del usuario permanecían en el historial y
se re-subían al proveedor en cada paso de cada turno posterior, disparando coste
y latencia. El arreglo omite del envío al modelo las imágenes de turnos que ya no
están en curso, conservándolas en el historial para la interfaz y la sesión.

Se ejecuta sin dependencias:  python -m unittest tests.test_adjuntos_historial
"""

import json
import unittest

from buildai.agent import _historial_para_modelo
from buildai.providers.anthropic_provider import ProveedorAnthropic

IMG_VIEJA = "IMAGEN_TURNO_1_" + "x" * 200
IMG_ACTUAL = "IMAGEN_TURNO_2_" + "y" * 200


def _historial_dos_turnos():
    return [
        # Turno 1: adjunta una foto y pide un render "como esta foto".
        {"tipo": "usuario", "texto": "una casa como esta foto",
         "adjuntos": [{"media_type": "image/jpeg", "datos": IMG_VIEJA}]},
        {"tipo": "asistente", "texto": "ok", "_raw": [{"type": "text", "text": "ok"}]},
        {"tipo": "resultado", "id": "t1", "nombre": "crear", "contenido": "hecho"},
        # Turno 2 (en curso): adjunta OTRA foto para una petición nueva.
        {"tipo": "usuario", "texto": "y otra igual que esta",
         "adjuntos": [{"media_type": "image/jpeg", "datos": IMG_ACTUAL}]},
    ]


class TestAdjuntosHistorial(unittest.TestCase):
    def test_imagenes_viejas_no_se_reenvian(self):
        historial = _historial_dos_turnos()
        vista = _historial_para_modelo(historial)
        payload = json.dumps(ProveedorAnthropic("k", "m")._convertir_historial(vista))

        self.assertNotIn(IMG_VIEJA, payload,
                         "la imagen de un turno ya cerrado no debe reenviarse al modelo")
        self.assertIn(IMG_ACTUAL, payload,
                      "la imagen del turno en curso sí debe llegar al modelo")

    def test_no_muta_el_historial_original(self):
        historial = _historial_dos_turnos()
        _historial_para_modelo(historial)
        # La UI y la sesión guardada dependen de que las imágenes sigan intactas.
        self.assertEqual(historial[0]["adjuntos"][0]["datos"], IMG_VIEJA)
        self.assertEqual(historial[3]["adjuntos"][0]["datos"], IMG_ACTUAL)

    def test_texto_del_turno_viejo_se_conserva(self):
        historial = _historial_dos_turnos()
        payload = json.dumps(
            ProveedorAnthropic("k", "m")._convertir_historial(_historial_para_modelo(historial))
        )
        # Se quita la imagen, pero el texto del turno viejo debe permanecer.
        self.assertIn("una casa como esta foto", payload)


if __name__ == "__main__":
    unittest.main()
