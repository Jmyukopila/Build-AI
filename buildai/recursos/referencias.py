"""Banco de referencias: fotos de arquitectura real para inspirarse o imitar.

Fuentes:
- Openverse (openverse.org): millones de fotos con licencia Creative Commons,
  sin clave. Es la fuente por defecto, así que funciona desde el primer día.
- Pexels (pexels.com): fotografía de mejor calidad media; requiere una clave
  gratuita que el usuario pone en Ajustes. Si existe, se usa primero.

(Unsplash queda fuera a propósito: sus condiciones exigen mostrar las fotos
desde sus servidores, y aquí hay que descargar una copia para que la IA la vea.)

Cada foto se descarga reducida (≤1024 px), con su atribución GRABADA en un pie:
el crédito viaja con la imagen al chat, a la sesión guardada y a la IA, y así
se cumple la atribución que piden las licencias CC y Pexels. Se guarda en la
carpeta de renders para reutilizar sin cambios cómo la interfaz las muestra.
"""

import hashlib
import io

import httpx
from PIL import Image, ImageDraw

OPENVERSE = "https://api.openverse.org/v1/images/"
PEXELS = "https://api.pexels.com/v1/search"
CABECERAS = {"User-Agent": "BuildAI (asistente de arquitectura; https://github.com/buildai)"}
LADO_MAXIMO = 1024
MAX_BYTES = 15 * 1024 * 1024
FUENTES = ("auto", "openverse", "pexels")


class ErrorReferencias(RuntimeError):
    pass


def _openverse(cliente, consulta, cantidad):
    try:
        r = cliente.get(OPENVERSE, params={"q": consulta, "page_size": cantidad, "mature": "false"})
        r.raise_for_status()
        datos = r.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise ErrorReferencias(f"Openverse no respondió ({exc}).")
    fotos = []
    for f in datos.get("results", []):
        licencia = f"CC {str(f.get('license', '')).upper()} {f.get('license_version') or ''}".strip()
        fotos.append({
            "titulo": f.get("title") or "Sin título",
            "autor": f.get("creator") or "autor desconocido",
            "licencia": licencia,
            "fuente": f"Openverse/{f.get('source', '')}".rstrip("/"),
            "enlace": f.get("foreign_landing_url") or f.get("url"),
            "imagen": f.get("url"),
        })
    return fotos


def _pexels(cliente, consulta, cantidad, clave):
    try:
        r = cliente.get(PEXELS, params={"query": consulta, "per_page": cantidad},
                        headers={"Authorization": clave})
        if r.status_code in (401, 403):
            raise ErrorReferencias("La clave de Pexels no es válida: revísala en Ajustes.")
        r.raise_for_status()
        datos = r.json()
    except httpx.HTTPError as exc:
        raise ErrorReferencias(f"Pexels no respondió ({exc}).")
    except ValueError as exc:
        raise ErrorReferencias(f"Pexels devolvió algo ilegible ({exc}).")
    fotos = []
    for f in datos.get("photos", []):
        src = f.get("src") or {}
        fotos.append({
            "titulo": f.get("alt") or "Foto de Pexels",
            "autor": f.get("photographer") or "autor desconocido",
            "licencia": "Licencia Pexels",
            "fuente": "Pexels",
            "enlace": f.get("url"),
            "imagen": src.get("large") or src.get("medium") or src.get("original"),
        })
    return fotos


def _fuente_texto(tamano):
    from ..planos.vista import fuente

    return fuente(tamano)


def _con_pie(contenido, numero, foto):
    """Imagen reducida con la atribución grabada en una franja inferior."""
    try:
        imagen = Image.open(io.BytesIO(contenido)).convert("RGB")
    except Exception as exc:
        raise ErrorReferencias(f"no es una imagen válida ({exc})")
    imagen.thumbnail((LADO_MAXIMO, LADO_MAXIMO))
    alto_pie = max(22, imagen.width // 40)
    lienzo = Image.new("RGB", (imagen.width, imagen.height + alto_pie), (20, 20, 20))
    lienzo.paste(imagen, (0, 0))
    texto = f"Ref. {numero} · «{foto['titulo'][:60]}» · {foto['autor'][:40]} · {foto['licencia']} · {foto['fuente']}"
    ImageDraw.Draw(lienzo).text((8, imagen.height + alto_pie // 2), texto, fill=(235, 235, 235),
                                font=_fuente_texto(int(alto_pie * 0.55)), anchor="lm")
    salida = io.BytesIO()
    lienzo.save(salida, "JPEG", quality=85)
    return salida.getvalue()


def _descargar(cliente, url):
    if not url or not url.startswith("https://"):
        raise ErrorReferencias("sin enlace https a la imagen")
    with cliente.stream("GET", url) as r:
        r.raise_for_status()
        trozos, total = [], 0
        for trozo in r.iter_bytes(1 << 16):
            total += len(trozo)
            if total > MAX_BYTES:
                raise ErrorReferencias("la imagen pesa demasiado")
            trozos.append(trozo)
    return b"".join(trozos)


def buscar(consulta, cantidad=4, fuente="auto", clave_pexels="", carpeta=None):
    """Busca fotos y descarga las primeras `cantidad` (1-6) con su atribución.

    Devuelve (fotos, avisos): cada foto con sus datos y `archivo`, la ruta de
    la imagen guardada en `carpeta`. Las fotos que no se pueden bajar se
    saltan y se avisa: unas pocas referencias valen más que un error.
    """
    consulta = (consulta or "").strip()
    if not consulta:
        raise ErrorReferencias("Indica qué buscar (p. ej. «casa mediterránea con patio»).")
    cantidad = max(1, min(int(cantidad or 4), 6))
    if fuente not in FUENTES:
        fuente = "auto"
    if fuente == "pexels" and not clave_pexels:
        raise ErrorReferencias("Para buscar en Pexels hace falta su clave gratuita en Ajustes (o usa openverse).")
    avisos = []
    with httpx.Client(headers=CABECERAS, timeout=30.0, follow_redirects=True) as cliente:
        candidatas = []
        if fuente in ("auto", "pexels") and clave_pexels:
            try:
                candidatas = _pexels(cliente, consulta, cantidad * 2, clave_pexels)
            except ErrorReferencias as exc:
                if fuente == "pexels":
                    raise
                avisos.append(f"{exc} Se usa Openverse.")
        if not candidatas and fuente != "pexels":
            candidatas = _openverse(cliente, consulta, cantidad * 2)
        fotos = []
        for foto in candidatas:
            if len(fotos) >= cantidad:
                break
            try:
                contenido = _con_pie(_descargar(cliente, foto["imagen"]), len(fotos) + 1, foto)
            except (httpx.HTTPError, ErrorReferencias) as exc:
                avisos.append(f"Se salta «{foto['titulo'][:40]}»: {exc}.")
                continue
            nombre = "ref-" + hashlib.sha1(foto["imagen"].encode("utf-8")).hexdigest()[:12] + ".jpg"
            carpeta.mkdir(parents=True, exist_ok=True)
            (carpeta / nombre).write_bytes(contenido)
            fotos.append(dict(foto, numero=len(fotos) + 1, archivo=str(carpeta / nombre)))
    return fotos, avisos
