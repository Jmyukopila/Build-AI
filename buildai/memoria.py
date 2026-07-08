"""Memoria de proyectos: BuildAI aprende de las conversaciones anteriores.

Lee las sesiones guardadas del usuario (las mismas que se pueden retomar desde
el historial) y destila un perfil compacto de sus preferencias —materiales que
más usa, tipo de trabajo habitual, temas recurrentes— que el agente inyecta en
su prompt de sistema. Así el asistente es coherente con el estilo del usuario
entre proyectos sin que este tenga que repetírselo cada vez.

Es best-effort: cualquier fallo devuelve un perfil vacío y nunca rompe el turno.
El resultado se cachea y solo se recalcula cuando cambian las sesiones en disco.
"""

import json
import re
from collections import Counter

from . import rutas

# Cache reindexada por la "firma" de la carpeta de sesiones (nº de archivos +
# mtime más reciente), para no re-escanear el disco en cada paso de una tarea.
_cache = {"firma": None, "texto": ""}

# Materiales del kit cuyo uso revela el gusto del usuario. Se omiten los
# estructurales neutros (hormigon, blanco, vidrio…) que aparecen en casi todo.
_MATERIALES = {
    "parquet", "marmol", "madera", "madera_clara", "ladrillo", "baldosa",
    "ceramica", "piedra", "piedra_muro", "antracita", "crema", "cesped",
    "tierra", "arena", "gravilla", "teja", "acero", "espejo",
    "tela_azul", "tela_beige", "tela_gris",
}

# Funciones del kit agrupadas por el tipo de trabajo que delatan.
_CATEGORIAS = {
    "interiorismo": {"dormitorio", "salon", "bano", "cocina", "comedor",
                     "sofa", "cama", "armario", "mesa", "alfombra"},
    "renders fotorrealistas": {"render", "cielo", "camara", "foco_empotrado",
                               "lampara_colgante", "sol"},
    "exteriores y jardín": {"terreno", "arbol", "arbusto", "seto", "piscina",
                            "tumbona", "foco_jardin"},
    "edificios de varias plantas": {"rejilla_pilares", "ventanal",
                                    "cubierta_plana", "escalera"},
}

_TEMAS = [
    "moderna", "rústic", "rustic", "clásic", "clasic", "minimalista", "piscina",
    "jardín", "jardin", "chalet", "adosad", "loft", "oficina", "local",
    "reforma", "ático", "atico", "terraza", "porche", "garaje",
]

_RE_FUNC = re.compile(r"\b([a-z_]{3,})\s*\(")
_RE_MAT = re.compile(r"""material\s*=\s*["']([a-z_]+)["']|material\(\s*["']([a-z_]+)["']""")


def _firma(carpeta):
    mtimes = [p.stat().st_mtime for p in carpeta.glob("*.json")]
    return (len(mtimes), max(mtimes)) if mtimes else (0, 0.0)


def _codigos_y_textos(historial):
    codigos, textos = [], []
    for m in historial:
        if m.get("tipo") == "usuario":
            textos.append(m.get("texto", ""))
        for ll in m.get("llamadas") or []:
            cod = (ll.get("argumentos") or {}).get("codigo")
            if cod:
                codigos.append(cod)
    return codigos, textos


def perfil_texto() -> str:
    """Bloque de "aprendizajes" para el prompt de sistema ("" si no hay datos)."""
    try:
        carpeta = rutas.carpeta_sesiones()
        if not carpeta.exists():
            return ""
        firma = _firma(carpeta)
        if firma == _cache["firma"]:
            return _cache["texto"]

        proyectos = renders = 0
        materiales, categorias, temas = Counter(), Counter(), Counter()
        for ruta in carpeta.glob("*.json"):
            try:
                datos = json.loads(ruta.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            historial = datos.get("historial") or []
            if not any(m.get("tipo") == "usuario" for m in historial):
                continue
            proyectos += 1
            codigos, textos = _codigos_y_textos(historial)
            usadas = set()
            for cod in codigos:
                for a, b in _RE_MAT.findall(cod):
                    nombre = a or b
                    if nombre in _MATERIALES:
                        materiales[nombre] += 1
                for f in _RE_FUNC.findall(cod):
                    usadas.add(f)
                    if f == "render":
                        renders += 1
            for cat, funcs in _CATEGORIAS.items():
                if usadas & funcs:
                    categorias[cat] += 1
            texto = " ".join(textos).lower()
            for t in _TEMAS:
                if t in texto:
                    temas[t] += 1

        if proyectos == 0:
            _cache.update(firma=firma, texto="")
            return ""

        info_render = f", con {renders} render(s) generado(s)" if renders else ""
        lineas = [
            "## Aprendizajes de tus proyectos anteriores",
            f"Has trabajado con BuildAI en {proyectos} conversación(es){info_render}. "
            "Toma estos patrones como las preferencias por defecto de ESTE usuario "
            "(aplícalos salvo que pida otra cosa; no hace falta que se los recites):",
        ]
        if materiales:
            lineas.append("- Materiales que más elige: "
                          + ", ".join(n for n, _ in materiales.most_common(6)) + ".")
        if categorias:
            lineas.append("- Tipo de trabajo habitual: "
                          + ", ".join(c for c, _ in categorias.most_common(3)) + ".")
        if temas:
            lineas.append("- Temas recurrentes en sus peticiones: "
                          + ", ".join(t for t, _ in temas.most_common(5)) + ".")
        lineas.append(
            "- Mantén la coherencia de estilo entre proyectos y ofrece por "
            "iniciativa lo que suele querer (p. ej. rematar con vegetación y un "
            "render si es su costumbre).")
        texto = "\n".join(lineas)
        _cache.update(firma=firma, texto=texto)
        return texto
    except Exception:
        return ""
