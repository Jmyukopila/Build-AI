"""Recursos de render de Poly Haven: cielos HDRI, texturas PBR y modelos 3D.

Poly Haven (polyhaven.com) publica todo con licencia CC0 y una API gratuita sin
clave. Es la diferencia entre un render de maqueta y uno fotográfico: un cielo
HDRI real ilumina con la luz de un lugar real, y una textura PBR fotografiada
(color, rugosidad, relieve) no se parece a ningún material procedimental.

La API no tiene búsqueda por texto: se descarga el catálogo de cada tipo (unos
cientos de recursos, ~1 MB), se guarda en caché un día y se busca en local por
nombre, etiquetas y categorías. Los archivos se descargan a
~/.buildai/recursos/polyhaven/<tipo>/<id>/ con un manifest.json que el kit de
Blender lee para cargarlos (Blender no descarga nada).
"""

import hashlib
import json
import re
import time
import unicodedata

import httpx

from .. import rutas

API = "https://api.polyhaven.com"
# Poly Haven pide identificar al cliente; nunca se envían datos del usuario.
CABECERAS = {"User-Agent": "BuildAI (asistente de arquitectura; https://github.com/buildai)"}
CADUCIDAD_CATALOGO = 24 * 3600

# Tipo en BuildAI → tipo de la API.
TIPOS = {"hdri": "hdris", "textura": "textures", "modelo": "models"}
RESOLUCIONES = ("1k", "2k", "4k")
# Con 2k una fachada o un cielo se ven nítidos en un render 1920×1080 sin
# descargar decenas de MB por recurso; 4k solo para primeros planos.
RESOLUCION_DEFECTO = "2k"
_ID_VALIDO = re.compile(r"^[A-Za-z0-9_\-]{1,80}$")

# Mapas de textura que usa el kit: nombre en la API → papel en el material.
# El de desplazamiento no se baja: exige subdividir la malla, y el mapa normal
# ya da el relieve visible en un render de arquitectura.
_MAPAS_TEXTURA = {"Diffuse": "color", "Rough": "rugosidad", "nor_gl": "normal"}


class ErrorRecursos(RuntimeError):
    pass


def carpeta():
    destino = rutas.CARPETA_DATOS / "recursos" / "polyhaven"
    destino.mkdir(parents=True, exist_ok=True)
    return destino


def _cliente():
    return httpx.Client(headers=CABECERAS, timeout=60.0, follow_redirects=True)


def _get_json(cliente, ruta):
    try:
        r = cliente.get(f"{API}{ruta}")
        r.raise_for_status()
        return r.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise ErrorRecursos(f"No pude consultar Poly Haven ({exc}). ¿Hay conexión a internet?")


# ------------------------------------------------------------------ catálogo

def catalogo(tipo, cliente=None):
    """{id: datos} de todos los recursos de un tipo, con caché de un día."""
    if tipo not in TIPOS:
        raise ErrorRecursos(f"Tipo «{tipo}» desconocido: usa {', '.join(TIPOS)}.")
    cache = carpeta() / f"catalogo_{tipo}.json"
    if cache.is_file() and time.time() - cache.stat().st_mtime < CADUCIDAD_CATALOGO:
        try:
            return json.loads(cache.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass  # caché corrupta: se vuelve a pedir
    propio = cliente is None
    cliente = cliente or _cliente()
    try:
        datos = _get_json(cliente, f"/assets?t={TIPOS[tipo]}")
    finally:
        if propio:
            cliente.close()
    if not isinstance(datos, dict) or not datos:
        raise ErrorRecursos("Poly Haven devolvió un catálogo vacío.")
    cache.write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")
    return datos


def _sin_acentos(texto):
    return "".join(c for c in unicodedata.normalize("NFD", texto.lower()) if unicodedata.category(c) != "Mn")


# El catálogo está en inglés y el usuario habla español: lo justo para que las
# búsquedas típicas de arquitectura encuentren algo sin traductor.
_TRADUCCIONES = {
    "ladrillo": "brick", "piedra": "stone rock", "madera": "wood", "hormigon": "concrete",
    "cemento": "concrete", "marmol": "marble", "baldosa": "tiles", "azulejo": "tiles",
    "suelo": "floor", "pared": "wall", "muro": "wall", "teja": "roof roofing", "tejado": "roofing",
    "cubierta": "roofing", "yeso": "plaster", "enlucido": "plaster", "estuco": "plaster",
    "asfalto": "asphalt", "grava": "gravel", "gravilla": "gravel", "arena": "sand", "cesped": "grass",
    "hierba": "grass", "tierra": "soil ground", "adoquin": "cobblestone", "metal": "metal",
    "tela": "fabric", "cuero": "leather", "parquet": "wood floor", "tarima": "wood floor",
    "atardecer": "sunset", "amanecer": "sunrise", "noche": "night", "nublado": "overcast cloudy",
    "soleado": "clear sunny", "cielo": "sky", "interior": "indoor", "exterior": "outdoor",
    "ciudad": "urban city", "calle": "street urban", "campo": "field rural", "playa": "beach",
    "montana": "mountain", "bosque": "forest", "parque": "park", "dia": "day midday",
    "silla": "chair", "sillon": "armchair", "sofa": "sofa", "mesa": "table", "lampara": "lamp",
    "planta": "plant potted", "arbol": "tree", "estanteria": "shelf", "cama": "bed",
    "mueble": "furniture", "jarron": "vase", "libro": "book", "cuadro": "frame",
}


def _terminos(consulta):
    palabras = re.findall(r"\w+", _sin_acentos(consulta))
    terminos = []
    for p in palabras:
        terminos.extend(_TRADUCCIONES.get(p, p).split())
    return [t for t in terminos if len(t) >= 3]


def buscar(tipo, consulta="", cantidad=8, cliente=None):
    """Recursos que mejor encajan con la consulta (en español o inglés).

    Puntuación: cada término cuenta más si aparece en el id o el nombre, algo
    menos en etiquetas y categorías, y poco en la descripción. A igualdad,
    gana el más descargado (suele ser el de mejor calidad).
    """
    datos = catalogo(tipo, cliente)
    terminos = _terminos(consulta or "")
    resultados = []
    for ident, info in datos.items():
        nombre = _sin_acentos(f"{ident} {info.get('name', '')}")
        etiquetas = _sin_acentos(" ".join(info.get("tags", []) + list(info.get("categories", []))
                                          + [str(info.get("category", ""))]
                                          + [str(v) for v in (info.get("attributes") or {}).values()]))
        descripcion = _sin_acentos(str(info.get("description", "")))
        puntos = 0
        for t in terminos:
            puntos += 3 * (t in nombre) + 2 * (t in etiquetas) + 1 * (t in descripcion)
        if terminos and puntos == 0:
            continue
        resultados.append((puntos, info.get("download_count", 0), ident, info))
    resultados.sort(key=lambda r: (-r[0], -r[1]))
    salida = []
    for _, _, ident, info in resultados[:max(1, min(int(cantidad or 8), 20))]:
        dimensiones = info.get("dimensions")
        salida.append({
            "id": ident,
            "nombre": info.get("name", ident),
            "categorias": info.get("categories") or info.get("category"),
            "etiquetas": (info.get("tags") or [])[:8],
            # Las texturas traen su tamaño real en mm: el kit las aplica a escala.
            "tamano_m": [round(d / 1000, 2) for d in dimensiones] if dimensiones else None,
            "descargado": ruta_manifest(tipo, ident) is not None,
        })
    return salida


# ------------------------------------------------------------------ descarga

def ruta_manifest(tipo, ident):
    if not isinstance(ident, str) or not _ID_VALIDO.match(ident):
        return None
    ruta = carpeta() / tipo / ident / "manifest.json"
    return ruta if ruta.is_file() else None


def _descargar_archivo(cliente, info, destino):
    """Descarga verificando el MD5 que publica Poly Haven; escritura atómica."""
    if destino.is_file() and info.get("md5") and _md5(destino) == info["md5"]:
        return destino
    destino.parent.mkdir(parents=True, exist_ok=True)
    parcial = destino.with_name(destino.name + ".parcial")
    try:
        with cliente.stream("GET", info["url"]) as r:
            r.raise_for_status()
            with parcial.open("wb") as f:
                for trozo in r.iter_bytes(1 << 16):
                    f.write(trozo)
    except httpx.HTTPError as exc:
        parcial.unlink(missing_ok=True)
        raise ErrorRecursos(f"Falló la descarga de {destino.name} ({exc}).")
    if info.get("md5") and _md5(parcial) != info["md5"]:
        parcial.unlink(missing_ok=True)
        raise ErrorRecursos(f"{destino.name} llegó dañado (MD5 distinto); vuelve a intentarlo.")
    parcial.replace(destino)
    return destino


def _md5(ruta):
    h = hashlib.md5()
    with ruta.open("rb") as f:
        for trozo in iter(lambda: f.read(1 << 20), b""):
            h.update(trozo)
    return h.hexdigest()


def _elegir_resolucion(variantes, preferida):
    """La resolución pedida; si no existe, la mayor por debajo; si tampoco, la menor."""
    if preferida in variantes:
        return preferida
    disponibles = [r for r in RESOLUCIONES if r in variantes]
    if not disponibles:
        return sorted(variantes)[0]
    menores = [r for r in disponibles if RESOLUCIONES.index(r) < RESOLUCIONES.index(preferida)]
    return menores[-1] if menores else disponibles[0]


def descargar(tipo, ident, resolucion=RESOLUCION_DEFECTO, cliente=None):
    """Descarga un recurso y devuelve su manifiesto (rutas locales y medidas)."""
    if tipo not in TIPOS:
        raise ErrorRecursos(f"Tipo «{tipo}» desconocido: usa {', '.join(TIPOS)}.")
    if not isinstance(ident, str) or not _ID_VALIDO.match(ident):
        raise ErrorRecursos(f"Identificador de recurso no válido: {ident!r}.")
    if resolucion not in RESOLUCIONES:
        resolucion = RESOLUCION_DEFECTO
    destino = carpeta() / tipo / ident
    propio = cliente is None
    cliente = cliente or _cliente()
    try:
        archivos = _get_json(cliente, f"/files/{ident}")
        if tipo == "hdri":
            variantes = archivos.get("hdri") or {}
            if not variantes:
                raise ErrorRecursos(f"«{ident}» no es un HDRI.")
            res = _elegir_resolucion(variantes, resolucion)
            info = variantes[res].get("hdr") or variantes[res].get("exr")
            ruta = _descargar_archivo(cliente, info, destino / info["url"].rsplit("/", 1)[-1])
            manifiesto = {"tipo": tipo, "id": ident, "resolucion": res, "archivo": str(ruta)}
        elif tipo == "textura":
            mapas = {}
            for clave_api, papel in _MAPAS_TEXTURA.items():
                variantes = archivos.get(clave_api) or {}
                if not variantes:
                    continue
                res = _elegir_resolucion(variantes, resolucion)
                info = variantes[res].get("jpg") or variantes[res].get("png")
                if info:
                    mapas[papel] = str(_descargar_archivo(cliente, info, destino / info["url"].rsplit("/", 1)[-1]))
            if "color" not in mapas:
                raise ErrorRecursos(f"«{ident}» no es una textura (no tiene mapa de color).")
            dimensiones = (catalogo(tipo, cliente).get(ident) or {}).get("dimensions") or [2000, 2000]
            manifiesto = {"tipo": tipo, "id": ident, "resolucion": resolucion, "mapas": mapas,
                          "tamano_m": [d / 1000 for d in dimensiones[:2]]}
        else:
            variantes = archivos.get("gltf") or {}
            if not variantes:
                raise ErrorRecursos(f"«{ident}» no es un modelo con versión glTF.")
            # Los modelos son mobiliario y decoración: 1k basta y pesa mucho menos.
            res = _elegir_resolucion(variantes, "1k" if resolucion == RESOLUCION_DEFECTO else resolucion)
            principal = variantes[res]["gltf"]
            ruta = _descargar_archivo(cliente, principal, destino / principal["url"].rsplit("/", 1)[-1])
            # El .gltf referencia su .bin y sus texturas por ruta relativa.
            for relativa, info in (principal.get("include") or {}).items():
                if ".." in relativa or relativa.startswith(("/", "\\")):
                    continue  # nunca escribir fuera de la carpeta del recurso
                _descargar_archivo(cliente, info, destino / relativa)
            manifiesto = {"tipo": tipo, "id": ident, "resolucion": res, "archivo": str(ruta)}
    finally:
        if propio:
            cliente.close()
    manifiesto["licencia"] = "CC0 (Poly Haven)"
    (destino / "manifest.json").write_text(json.dumps(manifiesto, ensure_ascii=False, indent=1), encoding="utf-8")
    return manifiesto
