"""La base de conocimiento carga, busca y guarda recetas sin tocar el disco real.

Esta prueba existía con dos defectos que la hacían inútil: afirmaba recuentos
fijos («exactamente 21 tareas») que se rompen cada vez que se añade una semilla,
y `guardar_receta` escribía en la carpeta real del usuario, de modo que sus
residuos falseaban los recuentos de la ejecución siguiente. Ahora los recuentos
se derivan de las semillas del paquete y la carpeta del usuario es temporal.

    python -m unittest tests.test_conocimiento
"""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from buildai import conocimiento

SEMILLAS = Path(conocimiento.__file__).resolve().parent / "conocimiento_semillas"


def _semillas_por_tipo(tipo: str) -> list:
    """Semillas del paquete de un tipo, leídas del front-matter sin usar el módulo
    bajo prueba: si el parser se rompe, los recuentos dejan de coincidir."""
    return [a for a in SEMILLAS.glob("*.md")
            if f"tipo: {tipo}" in a.read_text(encoding="utf-8")]


class BaseConocimiento(unittest.TestCase):
    """Aísla la carpeta del usuario para no leer ni escribir en ~/.buildai."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.carpeta = Path(self.tmp.name)
        parche = mock.patch.object(
            conocimiento.rutas, "carpeta_conocimiento", lambda: self.carpeta
        )
        parche.start()
        self.addCleanup(parche.stop)


class TestCargarRecetas(BaseConocimiento):
    def test_carga_todas_las_semillas_del_paquete(self):
        recetas = conocimiento.cargar_recetas()
        self.assertEqual(len(recetas), len(list(SEMILLAS.glob("*.md"))))

    def test_los_tipos_coinciden_con_el_front_matter(self):
        recetas = conocimiento.cargar_recetas()
        for tipo in ("tarea", "norma", "tecnica"):
            with self.subTest(tipo=tipo):
                cargadas = [r for r in recetas if r.get("tipo") == tipo]
                self.assertEqual(len(cargadas), len(_semillas_por_tipo(tipo)))

    def test_un_archivo_del_usuario_sobrescribe_su_semilla(self):
        id_semilla = conocimiento.cargar_recetas()[0]["id"]
        (self.carpeta / f"{id_semilla}.md").write_text(
            f"---\nid: {id_semilla}\nnombre: Reemplazada\ntipo: tarea\n---\n\nCuerpo nuevo.",
            encoding="utf-8",
        )
        recetas = conocimiento.cargar_recetas()
        coincidencias = [r for r in recetas if r["id"] == id_semilla]
        self.assertEqual(len(coincidencias), 1, "no debe duplicarse la receta")
        self.assertEqual(coincidencias[0]["nombre"], "Reemplazada")
        self.assertEqual(coincidencias[0]["fuente"], "usuario")


class TestRecetasBoton(BaseConocimiento):
    def test_devuelve_las_semillas_marcadas_como_boton(self):
        esperadas = [a for a in SEMILLAS.glob("*.md")
                     if "mostrar_boton: true" in a.read_text(encoding="utf-8")]
        self.assertEqual(len(conocimiento.recetas_boton()), len(esperadas))

    def test_cada_boton_trae_los_campos_que_pide_la_interfaz(self):
        requeridos = {"id", "nombre", "icono", "descripcion", "prompt"}
        for boton in conocimiento.recetas_boton():
            with self.subTest(boton=boton.get("id")):
                self.assertTrue(requeridos.issubset(boton))
                self.assertTrue(boton["prompt"].strip(), "el prompt no puede estar vacío")


class TestBuscar(BaseConocimiento):
    def test_encuentra_la_norma_de_accesibilidad(self):
        resultados = conocimiento.buscar("accesibilidad")
        self.assertTrue(any(r["tipo"] == "norma" for r in resultados))

    def test_encuentra_la_tecnica_de_escalera_de_caracol(self):
        resultados = conocimiento.buscar("escalera caracol")
        self.assertTrue(any(r["tipo"] == "tecnica" for r in resultados))

    def test_nunca_devuelve_tareas(self):
        """Las tareas son botones de la interfaz, no contexto para el modelo."""
        for consulta in ("accesibilidad", "escalera caracol", "iluminación"):
            with self.subTest(consulta=consulta):
                tipos = {r["tipo"] for r in conocimiento.buscar(consulta)}
                self.assertNotIn("tarea", tipos)

    def test_consulta_vacia_no_devuelve_nada(self):
        self.assertEqual(conocimiento.buscar("   "), [])

    def test_filtro_por_programas_descarta_las_de_otro_programa(self):
        (self.carpeta / "solo-blender.md").write_text(
            "---\nid: solo-blender\nnombre: Luz volumetrica en Blender\ntipo: tecnica\n"
            "programas: [blender]\n---\n\nLuz volumetrica con niebla.",
            encoding="utf-8",
        )
        ids_blender = {r["id"] for r in conocimiento.buscar("volumetrica", programas=["blender"])}
        ids_sketchup = {r["id"] for r in conocimiento.buscar("volumetrica", programas=["sketchup"])}
        self.assertIn("solo-blender", ids_blender)
        self.assertNotIn("solo-blender", ids_sketchup)


class TestBloqueParaSistema(BaseConocimiento):
    def test_respeta_el_presupuesto_de_caracteres(self):
        bloque = conocimiento.bloque_para_sistema(
            "accesibilidad", programas=None, max_caracteres=3000, max_resultados=4
        )
        self.assertTrue(bloque, "debería haber contexto para 'accesibilidad'")
        self.assertLessEqual(len(bloque), 3000)
        self.assertIn("## Contexto de arquitectura relevante", bloque)

    def test_sin_coincidencias_no_hay_bloque(self):
        self.assertFalse(conocimiento.bloque_para_sistema(
            "zzzqqqxxx", programas=None, max_caracteres=3000, max_resultados=4))


class TestGuardarReceta(BaseConocimiento):
    def test_guarda_en_la_carpeta_del_usuario_y_se_recupera(self):
        resultado = conocimiento.guardar_receta({
            "nombre": "Receta de prueba",
            "cuerpo": "Cuerpo de la receta de prueba.",
            "tipo": "tecnica",
            "descripcion": "Una receta de prueba",
            "programas": ["blender"],
            "tags": ["prueba"],
        })
        self.assertTrue(resultado.get("ok"), resultado.get("error", ""))
        archivo = self.carpeta / f"{resultado['id']}.md"
        self.assertTrue(archivo.is_file(), "debe escribirse en la carpeta del usuario")
        guardada = next(r for r in conocimiento.cargar_recetas() if r["id"] == resultado["id"])
        self.assertEqual(guardada["nombre"], "Receta de prueba")
        self.assertEqual(guardada["fuente"], "usuario")


class TestNormalizarAcentos(unittest.TestCase):
    def test_elimina_acentos_conservando_el_resto(self):
        self.assertEqual(conocimiento._normalizar_acentos("Accesibilidad"), "Accesibilidad")
        self.assertEqual(conocimiento._normalizar_acentos("iluminación"), "iluminacion")
        self.assertEqual(conocimiento._normalizar_acentos("diseño"), "diseno")


if __name__ == "__main__":
    unittest.main()
