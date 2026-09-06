"""La cocina dentro de su estancia y la envolvente del edificio.

Históricamente el modelo calculaba a mano la posición de la bancada y a veces
la dejaba fuera de la casa. Estas pruebas fijan la nueva `cocina_estancia()`
(que adosa sola la bancada a la línea interior de la pared, igual que `bano`)
y el aviso de `revisar_escena()` para muebles interiores fuera de la huella.
Se centran en los helpers puros del kit para no necesitar un `bpy` con
geometría de verdad.

    python -m unittest tests.test_estancias_cocina
"""

import types
import unittest

from tests.dobles import kit_blender


class _MatrizIdentidad:
    """Matriz de mundo sin transformaciones: devuelve cada esquina tal cual."""

    def __matmul__(self, punto):
        return punto


class _Objeto:
    """Lo mínimo que usa el kit de un objeto de Blender para medir su caja."""

    def __init__(self, nombre, x_min, y_min, x_max, y_max, alto=3.0):
        self.name = nombre
        self.bound_box = [
            (x_min, y_min, 0), (x_max, y_min, 0), (x_max, y_max, 0), (x_min, y_max, 0),
            (x_min, y_min, alto), (x_max, y_min, alto), (x_max, y_max, alto), (x_min, y_max, alto),
        ]
        self.matrix_world = _MatrizIdentidad()
        self.location = (x_min, y_min, 0)


class TestPosicionesCocina(unittest.TestCase):
    """`_posiciones_cocina`: la geometría la decide el kit, no el modelo."""

    def ejecutar(self, pared, ancho=4.0, fondo=3.0, largo=2.4, con_isla=False):
        with kit_blender() as (kit, _):
            return kit._posiciones_cocina((0, 0), ancho, fondo, pared, largo, con_isla)

    def test_espalda_sobre_la_linea_interior_de_la_pared(self):
        """Las cuatro orientaciones: la bancada pega su espalda a la pared y
        gira con ella."""
        esperado = {"S": (0.8, 0.0, 0), "N": (3.2, 4.0, 180),
                    "E": (4.0, 0.8, 90), "O": (0.0, 3.2, 270)}
        for pared, (x_esp, y_esp, rot_esp) in esperado.items():
            with self.subTest(pared=pared):
                plan = self.ejecutar(pared, ancho=4.0, fondo=4.0)
                self.assertEqual(plan["bancada_origen"], (x_esp, y_esp))
                self.assertEqual(plan["rotacion"], rot_esp)

    def test_la_bancada_queda_dentro_del_rectangulo(self):
        for pared in ("S", "N", "E", "O"):
            with self.subTest(pared=pared):
                plan = self.ejecutar(pared, ancho=4.0, fondo=4.0)
                x, y = plan["bancada_origen"]
                longitud_pared = 4.0
                self.assertGreaterEqual({"S": x, "N": 4 - x, "E": y, "O": 4 - y}[pared], 0.0)
                self.assertLessEqual({"S": x, "N": 4 - x, "E": y, "O": 4 - y}[pared]
                                     + plan["bancada_largo"], longitud_pared)
                self.assertLessEqual(0.63, 4.0)

    def test_estancia_pequena_ajusta_la_bancada_sin_salirse(self):
        plan = self.ejecutar("S", ancho=2.0, fondo=2.0)
        self.assertTrue(plan["ajustada"])
        self.assertEqual(plan["bancada_largo"], 1.0)
        self.assertFalse(plan["omitida"])
        x, _ = plan["bancada_origen"]
        self.assertGreaterEqual(x, 0.0)
        self.assertLessEqual(x + plan["bancada_largo"], 2.0)

    def test_estancia_minima_omite_la_encimera(self):
        plan = self.ejecutar("S", ancho=1.0, fondo=1.0)
        self.assertTrue(plan["omitida"])
        self.assertIsNone(plan["bancada_origen"])
        self.assertEqual(plan["bancada_largo"], 0.0)

    def test_isla_y_foco_en_el_centro_de_la_estancia(self):
        plan = self.ejecutar("S", con_isla=True)
        self.assertEqual(plan["isla"], (2.0, 1.5))
        self.assertEqual(plan["foco"], (2.0, 1.5))
        plan_sin_isla = self.ejecutar("S")
        self.assertIsNone(plan_sin_isla["isla"])

    def test_pared_desconocida_rechazada(self):
        with self.assertRaises(ValueError):
            self.ejecutar("X")


class TestEnvolvente(unittest.TestCase):
    """`_huella_forjados` y `_fuera_de_huella`: los ojos de `revisar_escena`."""

    def huella(self, objetos):
        with kit_blender() as (kit, _):
            return kit._huella_forjados(objetos)

    def test_une_las_plantas_a_distintas_cotas(self):
        forjado = _Objeto("Forjado", 0, 0, 10, 8)
        primera = _Objeto("Forjado_P1", 10, 8, 18, 12)
        cubierta = _Objeto("Cubierta_plana", -0.5, -0.5, 18.5, 12.5)
        self.assertEqual(self.huella([forjado, primera, cubierta]),
                         (-0.5, -0.5, 18.5, 12.5))

    def test_sin_losas_no_hay_huella(self):
        self.assertIsNone(self.huella([_Objeto("Muro", 0, 0, 5, 5)]))

    def test_un_mueble_fuera_avisa_y_dentro_no(self):
        huella = self.huella([_Objeto("Forjado", 0, 0, 10, 8)])
        with kit_blender() as (kit, _):
            self.assertFalse(kit._fuera_de_huella((5, 4), huella))
            self.assertTrue(kit._fuera_de_huella((12, 4), huella))

    def test_tolerancia_para_muebles_pegados_a_la_pared(self):
        huella = self.huella([_Objeto("Forjado", 0, 0, 10, 8)])
        with kit_blender() as (kit, _):
            self.assertFalse(kit._fuera_de_huella((10.1, 8.1), huella, tolerancia=0.15))
            self.assertTrue(kit._fuera_de_huella((10.2, 8.2), huella, tolerancia=0.15))

    def test_sin_geometria_la_caja_se_reduce_a_su_ubicacion(self):
        obj = types.SimpleNamespace(name="Forjado", location=(2, 3, 0))
        with kit_blender() as (kit, _):
            self.assertEqual(kit._bbox_xy(obj), (2, 3, 2, 3))


if __name__ == "__main__":
    unittest.main()