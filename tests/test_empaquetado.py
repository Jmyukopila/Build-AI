"""El .spec de PyInstaller no puede referirse a rutas que ya no existen.

Nace de un fallo real: el spec empaquetaba `buildai/skills_data`, que desapareció
al rediseñar la base de conocimiento, y dejó de empaquetar las semillas. Nada lo
detectaba porque el instalador solo se construye en Windows y el error habría
salido allí, tarde. Estas comprobaciones son de segundos y cubren esa clase entera
de fallo.

    python -m unittest tests.test_empaquetado
"""

import re
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SPEC = RAIZ / "empaquetado" / "buildai.spec"


def _rutas_de_datos() -> list:
    """Rutas de `datas` del spec, leídas como texto: importarlo exigiría PyInstaller."""
    fuente = SPEC.read_text(encoding="utf-8")
    bloque = fuente[fuente.index("datas=["):fuente.index("hiddenimports=[")]
    rutas = []
    for linea in bloque.splitlines():
        piezas = re.findall(r'"([^"]+)"', linea)
        # str(RAIZ / "a" / "b"), "destino"  →  las piezas antes del destino
        if len(piezas) >= 2:
            rutas.append(RAIZ.joinpath(*piezas[:-1]))
    return rutas


class TestDatosEmpaquetados(unittest.TestCase):
    def test_el_spec_existe(self):
        self.assertTrue(SPEC.is_file())

    def test_se_reconocen_las_rutas_de_datos(self):
        self.assertGreaterEqual(len(_rutas_de_datos()), 5, "el parseo del spec ha dejado de funcionar")

    def test_todas_las_rutas_de_datos_existen(self):
        for ruta in _rutas_de_datos():
            with self.subTest(ruta=str(ruta.relative_to(RAIZ))):
                self.assertTrue(ruta.exists(), f"el spec empaqueta algo que no existe: {ruta}")

    def test_se_empaqueta_la_base_de_conocimiento(self):
        """Sin las semillas, la app instalada arranca sin criterio de arquitectura."""
        nombres = [r.name for r in _rutas_de_datos()]
        self.assertIn("conocimiento_semillas", nombres)

    def test_se_empaquetan_los_kits_que_pyinstaller_no_detecta(self):
        """Se leen como texto, nunca se importan: PyInstaller no los ve solo."""
        nombres = [r.name for r in _rutas_de_datos()]
        self.assertIn("blender_kit.py", nombres)
        self.assertIn("revit_kit.py", nombres)


class TestPaqueteDeDatos(unittest.TestCase):
    """El instalador usa el spec, pero `pip install` usa package-data: los dos
    tienen que incluir lo mismo o la instalación desde fuente sale coja."""

    def test_pyproject_incluye_las_semillas_y_los_addons(self):
        pyproject = (RAIZ / "pyproject.toml").read_text(encoding="utf-8")
        for patron in ("conocimiento_semillas/*.md", "addons/blender/*.py",
                       "addons/sketchup/*.rb", "ui/*.html"):
            with self.subTest(patron=patron):
                self.assertIn(patron, pyproject)


if __name__ == "__main__":
    unittest.main()
