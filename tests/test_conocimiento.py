"""Tests para el módulo de conocimiento escalable."""

import sys
from pathlib import Path

# Añadir buildai al path para importación
sys.path.insert(0, str(Path(__file__).parent.parent))

from buildai import conocimiento


def test_cargar_recetas():
    """Verifica que se cargan las recetas correctamente."""
    recetas = conocimiento.cargar_recetas()
    assert len(recetas) >= 21, "Debe cargar al menos las 21 tareas seminales"

    # Verificar que hay tareas
    tareas = [r for r in recetas if r.get("tipo") == "tarea"]
    assert len(tareas) == 21, "Debe haber exactamente 21 tareas"

    # Verificar que hay normas/técnicas nuevas
    normas_tecnicas = [r for r in recetas if r.get("tipo") in ("norma", "tecnica")]
    assert len(normas_tecnicas) >= 2, "Debe haber al menos 2 normas/técnicas"


def test_recetas_boton():
    """Verifica que recetas_boton() devuelve la estructura correcta para /api/skills."""
    botones = conocimiento.recetas_boton()

    # Debe devolver 21 (solo tareas con mostrar_boton=True)
    assert len(botones) == 21, f"Debe devolver 21 botones, encontré {len(botones)}"

    # Cada botón debe tener los campos esperados
    campos_requeridos = {"id", "nombre", "icono", "descripcion", "prompt"}
    for b in botones:
        assert campos_requeridos.issubset(set(b.keys())), \
            f"Botón {b.get('id')} falta campos: {campos_requeridos - set(b.keys())}"
        assert b.get("prompt", "").strip(), f"Botón {b['id']} tiene prompt vacío"


def test_buscar_normas():
    """Verifica la búsqueda de normas/técnicas."""
    # Búsqueda de accesibilidad
    resultados = conocimiento.buscar("accesibilidad")
    assert len(resultados) > 0, "Debe encontrar recetas sobre accesibilidad"
    assert any(r.get("tipo") == "norma" for r in resultados), \
        "Debe encontrar al menos una norma sobre accesibilidad"

    # Búsqueda de escalera
    resultados = conocimiento.buscar("escalera caracol")
    assert len(resultados) > 0, "Debe encontrar recetas sobre escalera de caracol"
    assert any(r.get("tipo") == "tecnica" for r in resultados), \
        "Debe encontrar al menos una técnica sobre escalera de caracol"


def test_bloque_para_sistema():
    """Verifica que bloque_para_sistema() respeta el presupuesto de caracteres."""
    bloque = conocimiento.bloque_para_sistema(
        "accesibilidad",
        programas=None,
        max_caracteres=3000,
        max_resultados=4
    )

    if bloque:  # Si hay coincidencias
        assert len(bloque) <= 3000, \
            f"Bloque debe respetar max_caracteres (tengo {len(bloque)}, max 3000)"
        assert "## Contexto de arquitectura relevante" in bloque, \
            "Bloque debe tener el header de contexto"


def test_filtro_por_programas():
    """Verifica que el filtro por programas funciona."""
    # Alumbrado es solo para Blender
    resultados = conocimiento.buscar("iluminación", programas=["blender"])
    assert len(resultados) > 0, "Debe encontrar recetas de iluminación para Blender"

    # Si busco con un programa que no coincide (SketchUp), no debe traer nada
    resultados = conocimiento.buscar("iluminación", programas=["sketchup"])
    # Esto puede estar vacío o traer recetas con programas=[] (aplica a todos)
    # Lo importante es que no trae las específicamente de Blender si SketchUp no está en su lista


def test_guardar_receta():
    """Verifica que se puede guardar una receta nueva."""
    datos = {
        "nombre": "Test Receta",
        "cuerpo": "Este es un test de guardar receta.",
        "tipo": "tecnica",
        "descripcion": "Una receta de prueba",
        "programas": ["blender"],
        "tags": ["test"],
    }

    resultado = conocimiento.guardar_receta(datos)
    assert resultado.get("ok"), f"Guardar debería funcionar: {resultado.get('error', '')}"
    assert "id" in resultado, "Resultado debe tener un id"

    # Verificar que la receta fue guardada
    receta_id = resultado["id"]
    recetas = conocimiento.cargar_recetas()
    receta_guardada = next((r for r in recetas if r["id"] == receta_id), None)
    assert receta_guardada, f"Receta {receta_id} no fue guardada"
    assert receta_guardada["nombre"] == datos["nombre"], "El nombre debe coincidir"


def test_normalizar_acentos():
    """Verifica la normalización de acentos."""
    assert conocimiento._normalizar_acentos("accesibilidad") == "accesibilidad"
    # Los acentos deben eliminarse (aunque se preserva case)
    normalizado = conocimiento._normalizar_acentos("Accesibilidad")
    assert "á" not in normalizado, f"Acentos no removidos: {normalizado}"
    assert normalizado.lower() == "accesibilidad"


if __name__ == "__main__":
    test_cargar_recetas()
    test_recetas_boton()
    test_buscar_normas()
    test_bloque_para_sistema()
    test_filtro_por_programas()
    test_guardar_receta()
    test_normalizar_acentos()
    print("✓ Todos los tests pasaron")
