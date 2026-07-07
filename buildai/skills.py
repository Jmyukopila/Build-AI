"""Carga de skills: tareas predefinidas en español para arquitectos.

Cada skill es un archivo JSON en la carpeta `skills/` con:
  {"id", "nombre", "icono", "descripcion", "prompt"}
El usuario las ve como botones y al pulsarlas se envía el prompt al agente.
"""

import json
from pathlib import Path

CARPETA_SKILLS = Path(__file__).resolve().parent / "skills_data"


def cargar_skills() -> list:
    skills = []
    if not CARPETA_SKILLS.exists():
        return skills
    for archivo in sorted(CARPETA_SKILLS.glob("*.json")):
        try:
            datos = json.loads(archivo.read_text(encoding="utf-8"))
            if all(k in datos for k in ("id", "nombre", "prompt")):
                datos.setdefault("icono", "tarea")
                datos.setdefault("descripcion", "")
                skills.append(datos)
        except (json.JSONDecodeError, OSError):
            continue
    return skills
