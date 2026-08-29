"""Base de conocimiento escalable para arquitectura: tareas, normas, técnicas.

Reemplaza el sistema anterior de skills_data/*.json por archivos Markdown con
front-matter ligero. Cada archivo tiene un `tipo` (tarea/norma/tecnica):
- tarea: botón en la UI, enviado al chat como mensaje literal (ej. las 21 skills de hoy).
- norma: normativa, dimensionamiento, reglamentación — se inyecta en el system prompt.
- tecnica: know-how de modelado — se inyecta en el system prompt.

Recuperación: búsqueda léxica (BM25 vía SQLite FTS5, cero dependencias nuevas,
reconstruida en memoria por turno), no embeddings.
"""

import json
import re
import sqlite3
import unicodedata
from pathlib import Path
from typing import Optional

from . import rutas


def _normalizar_acentos(texto: str) -> str:
    """Normaliza acentos para búsqueda (NFD decomposición, elimina marcas diacríticas)."""
    return "".join(
        c for c in unicodedata.normalize("NFD", texto)
        if unicodedata.category(c) != "Mn"
    )


def _parsear_front_matter(contenido: str) -> tuple[dict, str]:
    """Extrae front-matter (---\nclave: valor\n---) y cuerpo.

    Retorna (metadatos_dict, cuerpo_str). Si no hay front-matter válido,
    retorna ({}, contenido_completo).
    """
    lineas = contenido.split("\n", 1)
    if not lineas[0].strip() == "---":
        return {}, contenido

    if len(lineas) < 2:
        return {}, contenido

    resto = lineas[1]
    partes = resto.split("\n---\n", 1)
    if len(partes) != 2:
        return {}, contenido

    cabecera_str, cuerpo = partes
    metadatos = {}
    for linea in cabecera_str.split("\n"):
        linea = linea.strip()
        if not linea or linea.startswith("#"):
            continue
        if ":" not in linea:
            continue
        clave, valor = linea.split(":", 1)
        clave = clave.strip()
        valor = valor.strip()
        if valor.startswith("[") and valor.endswith("]"):
            valor = [v.strip() for v in valor.strip("[]").split(",") if v.strip()]
        elif valor.lower() in ("true", "false"):
            valor = valor.lower() == "true"
        metadatos[clave] = valor

    return metadatos, cuerpo.strip()


def cargar_recetas() -> list[dict]:
    """Carga todos los .md de ~/.buildai/conocimiento/ y de semillas empaquetadas.

    Retorna lista de recetas con estructura:
      {id, nombre, tipo, icono, descripcion, prompt, programas, tags, mostrar_boton, fuente, cuerpo}
    """
    recetas = []

    # Cargar semillas empaquetadas primero (si existen).
    carpeta_semillas = Path(__file__).resolve().parent / "conocimiento_semillas"
    if carpeta_semillas.exists():
        for archivo in sorted(carpeta_semillas.glob("*.md")):
            try:
                contenido = archivo.read_text(encoding="utf-8")
                metadatos, cuerpo = _parsear_front_matter(contenido)
                if "id" in metadatos and "nombre" in metadatos:
                    metadatos.setdefault("tipo", "tarea")
                    metadatos.setdefault("icono", "tarea")
                    metadatos.setdefault("descripcion", "")
                    metadatos.setdefault("programas", [])
                    metadatos.setdefault("tags", [])
                    metadatos.setdefault("mostrar_boton", True if metadatos.get("tipo") == "tarea" else False)
                    metadatos.setdefault("fuente", "seed")
                    metadatos["cuerpo"] = cuerpo
                    recetas.append(metadatos)
            except Exception:
                continue

    # Cargar archivos del usuario en ~/.buildai/conocimiento (sobrescriben semillas).
    carpeta_usuario = rutas.carpeta_conocimiento()
    if carpeta_usuario.exists():
        for archivo in sorted(carpeta_usuario.glob("*.md")):
            try:
                contenido = archivo.read_text(encoding="utf-8")
                metadatos, cuerpo = _parsear_front_matter(contenido)
                if "id" in metadatos and "nombre" in metadatos:
                    metadatos.setdefault("tipo", "tarea")
                    metadatos.setdefault("icono", "tarea")
                    metadatos.setdefault("descripcion", "")
                    metadatos.setdefault("programas", [])
                    metadatos.setdefault("tags", [])
                    metadatos.setdefault("mostrar_boton", True if metadatos.get("tipo") == "tarea" else False)
                    metadatos.setdefault("fuente", "usuario")
                    metadatos["cuerpo"] = cuerpo
                    # Buscar por id y reemplazar si existe (usuario sobrescribe semilla).
                    idx = next((i for i, r in enumerate(recetas) if r["id"] == metadatos["id"]), None)
                    if idx is not None:
                        recetas[idx] = metadatos
                    else:
                        recetas.append(metadatos)
            except Exception:
                continue

    return recetas


def _slugify(texto: str) -> str:
    """Convierte texto a slug: minúsculas, sin acentos, reemplaza espacios/puntos por guiones."""
    slug = _normalizar_acentos(texto).lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return slug.strip("-")


def buscar(consulta: str, programas: Optional[list] = None) -> list[dict]:
    """Busca recetas por similitud léxica (FTS5) dentro del tipo y programas especificados.

    La búsqueda se filtra por:
    - tipo: solo norma/tecnica (no tarea, que no se recuperan, son botones).
    - programas: si la receta tiene programas específicos y ninguno de los activos
      coincide, se descarta.

    Retorna lista de dicts {id, nombre, descripcion, tipo, cuerpo}.
    """
    if not consulta or not consulta.strip():
        return []

    recetas = cargar_recetas()
    # Filtrar solo norma/tecnica.
    recetas = [r for r in recetas if r.get("tipo") in ("norma", "tecnica")]
    # Filtrar por programas: descartar si tiene programas específicos y ninguno coincide.
    if programas:
        recetas_filtradas = []
        for r in recetas:
            r_programas = r.get("programas", [])
            if not r_programas:  # vacío = aplica a todos
                recetas_filtradas.append(r)
            elif any(p in r_programas for p in programas):
                recetas_filtradas.append(r)
        recetas = recetas_filtradas

    # Indexar con FTS5 en memoria.
    consulta_norm = _normalizar_acentos(consulta).lower()
    con = sqlite3.connect(":memory:")
    con.execute("CREATE VIRTUAL TABLE recetas_fts USING fts5("
                "id, nombre, descripcion, tags, cuerpo)")

    for r in recetas:
        tags_str = ",".join(r.get("tags", []) if isinstance(r.get("tags"), list) else [])
        con.execute(
            "INSERT INTO recetas_fts VALUES (?, ?, ?, ?, ?)",
            (r["id"], _normalizar_acentos(r["nombre"]).lower(),
             _normalizar_acentos(r["descripcion"]).lower(),
             _normalizar_acentos(tags_str).lower(),
             _normalizar_acentos(r["cuerpo"]).lower())
        )
    con.commit()

    # Buscar: prioridad a coincidencias en id/nombre, luego descripcion/tags, luego cuerpo.
    resultados = []
    for rank, row in enumerate(con.execute(
        "SELECT id, rank FROM recetas_fts WHERE recetas_fts MATCH ? ORDER BY rank",
        (consulta_norm,)
    )):
        receta_id = row[0]
        receta = next((r for r in recetas if r["id"] == receta_id), None)
        if receta:
            resultados.append(receta)

    con.close()
    return resultados


def bloque_para_sistema(consulta: str, programas: Optional[list] = None,
                        max_caracteres: int = 3000, max_resultados: int = 4) -> str:
    """Recupera las N normas/técnicas más relevantes y arma un bloque para inyectar en system prompt.

    Retorna un string vacío si no hay coincidencias o si los resultados superan
    el presupuesto de caracteres (para no crecer el prompt sin límite).
    """
    resultados = buscar(consulta, programas)[:max_resultados]
    if not resultados:
        return ""

    bloque_lineas = ["## Contexto de arquitectura relevante:"]
    contador_caracteres = sum(len(l) for l in bloque_lineas) + 2

    for r in resultados:
        titulo = f"\n### {r['nombre']} ({r.get('tipo', 'otro').capitalize()})"
        cuerpo_texto = r.get("cuerpo", "").strip()

        fragmento_caracteres = len(titulo) + len(cuerpo_texto) + 4
        if contador_caracteres + fragmento_caracteres > max_caracteres:
            break

        bloque_lineas.append(titulo)
        bloque_lineas.append(cuerpo_texto)
        contador_caracteres += fragmento_caracteres

    if len(bloque_lineas) == 1:  # Solo el header
        return ""

    return "\n".join(bloque_lineas)


def recetas_boton() -> list[dict]:
    """Retorna recetas de tipo 'tarea' con mostrar_boton=True, formato {id, nombre, icono, descripcion, prompt}.

    Este es el contrato que la UI (`app.js:cargarSkills`) espera para los botones.
    """
    todas = cargar_recetas()
    botones = [r for r in todas if r.get("tipo") == "tarea" and r.get("mostrar_boton", False)]
    return [
        {
            "id": r["id"],
            "nombre": r["nombre"],
            "icono": r.get("icono", "tarea"),
            "descripcion": r.get("descripcion", ""),
            "prompt": r.get("cuerpo", ""),
        }
        for r in botones
    ]


def guardar_receta(datos: dict) -> dict:
    """Guarda una receta nueva en ~/.buildai/conocimiento/.

    Valida campos mínimos (nombre, cuerpo), genera id si falta (slugify),
    establece fuente="usuario", escribe el .md con front-matter.

    Retorna {ok, id, error} (error solo si fallo).
    """
    nombre = (datos.get("nombre") or "").strip()
    cuerpo = (datos.get("cuerpo") or "").strip()

    if not nombre or not cuerpo:
        return {"ok": False, "error": "Nombre y cuerpo son obligatorios."}

    receta_id = datos.get("id") or _slugify(nombre)
    if not receta_id:
        return {"ok": False, "error": "No se pudo generar un id válido."}

    tipo = (datos.get("tipo") or "tarea").strip()
    if tipo not in ("tarea", "norma", "tecnica"):
        tipo = "tarea"

    icono = (datos.get("icono") or "tarea").strip()
    descripcion = (datos.get("descripcion") or "").strip()
    programas = datos.get("programas", [])
    if isinstance(programas, str):
        programas = [p.strip() for p in programas.split(",") if p.strip()]

    tags = datos.get("tags", [])
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]

    mostrar_boton = tipo == "tarea" and datos.get("mostrar_boton", True)

    # Armar front-matter.
    lineas_fm = [
        "---",
        f"id: {receta_id}",
        f"nombre: {nombre}",
        f"tipo: {tipo}",
        f"icono: {icono}",
        f"descripcion: {descripcion}",
        f"programas: [{', '.join(programas)}]" if programas else "programas: []",
        f"tags: {', '.join(tags)}" if tags else "tags: []",
        f"mostrar_boton: {str(mostrar_boton).lower()}",
        "fuente: usuario",
        "---",
        "",
        cuerpo,
    ]

    carpeta = rutas.carpeta_conocimiento()
    archivo = carpeta / f"{receta_id}.md"

    try:
        archivo.write_text("\n".join(lineas_fm), encoding="utf-8")
        return {"ok": True, "id": receta_id}
    except Exception as e:
        return {"ok": False, "error": f"Error al guardar: {str(e)}"}
