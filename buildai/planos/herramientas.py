"""Herramientas de planos para el agente: detectar, leer DXF y reconstruir.

No son un conector (no hay un programa "Planos" que abrir), sino herramientas
internas siempre disponibles. Trabajan sobre los adjuntos del mensaje más
reciente que los tenga y, para construir, reutilizan la herramienta de
ejecución del conector de destino.
"""

import base64
import uuid

from . import constructores, detector, importar, modelo, vista

DETECTAR = "plano_detectar_muros"
LEER_DXF = "plano_leer_dxf"
RECONSTRUIR = "plano_reconstruir"
NOMBRES = (DETECTAR, LEER_DXF, RECONSTRUIR)

_EJECUCION = {
    "blender": "blender_ejecutar_python",
    "autocad": "autocad_ejecutar_python",
    "sketchup": "sketchup_ejecutar_ruby",
    "revit": "revit_ejecutar_python",
}

_PUNTO = {"type": "array", "items": {"type": "number"}, "description": "[x, y]"}

_ESQUEMA_PLANO = {
    "type": "object",
    "description": "Plano neutro (ver la descripción de la herramienta).",
    "properties": {
        "unidades": {"type": "string", "enum": ["px", "cm", "mm", "m"]},
        "giro": {"type": "number", "description": "grados que indica plano_detectar_muros, si el plano está girado"},
        "calibracion": {
            "type": "array",
            "description": "Obligatoria con px: cotas leídas del plano, en metros.",
            "items": {
                "type": "object",
                "properties": {
                    "muro": {"type": "string", "description": "id del muro acotado"},
                    "referencia": {"type": "string", "enum": ["exterior", "eje"]},
                    "p1": _PUNTO,
                    "p2": _PUNTO,
                    "medida": {"type": "number", "description": "metros"},
                },
                "required": ["medida"],
            },
        },
        "plantas": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "nombre": {"type": "string"},
                    "nivel": {"type": "number", "description": "cota del suelo, m"},
                    "altura": {"type": "number", "description": "altura libre, m"},
                    "imagen": {"type": "integer", "description": "nº del adjunto del que salen sus px"},
                    "desplazamiento": _PUNTO,
                    "muros": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string"},
                                "inicio": _PUNTO,
                                "fin": _PUNTO,
                                "espesor": {"type": "number", "description": "en las unidades del plano"},
                            },
                            "required": ["inicio", "fin"],
                        },
                    },
                    "huecos": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "tipo": {"type": "string", "enum": list(modelo.TIPOS_HUECO)},
                                "centro": _PUNTO,
                                "ancho": {"type": "number", "description": "m"},
                                "alto": {"type": "number", "description": "m"},
                                "antepecho": {"type": "number", "description": "m"},
                                "abre_hacia": _PUNTO,
                            },
                            "required": ["tipo", "centro"],
                        },
                    },
                    "estancias": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "nombre": {"type": "string"},
                                "centro": _PUNTO,
                                "superficie": {"type": "number", "description": "m² que indica el plano"},
                            },
                            "required": ["nombre", "centro"],
                        },
                    },
                },
                "required": ["muros"],
            },
        },
    },
    "required": ["plantas"],
}

_NUMERO_IMAGEN = {
    "type": "integer",
    "description": "Número del adjunto (1 = el primero) del mensaje más reciente con adjuntos.",
}


def herramientas() -> list:
    return [
        {
            "nombre": DETECTAR,
            "descripcion": (
                "Mide al píxel los muros de un plano adjunto (foto, escaneo o página de PDF). "
                "Devuelve cada muro horizontal o vertical con su eje (inicio → fin, en px de la "
                "imagen que ves, origen arriba a la izquierda) y su espesor, más los cortes de "
                "los muros que pueden ser puertas o ventanas. Úsala SIEMPRE antes de "
                "plano_reconstruir con un plano en imagen: tus estimaciones a ojo de "
                "coordenadas fallan por decenas de píxeles y esto no. Revisa el resultado: "
                "quita lo que no sea muro (mobiliario macizo, rótulos) y añade los inclinados. "
                "modo='hueco' si los muros están dibujados solo con sus dos caras sin relleno."
            ),
            "parametros": {
                "type": "object",
                "properties": {
                    "imagen": _NUMERO_IMAGEN,
                    "modo": {"type": "string", "enum": ["auto", "macizo", "hueco"]},
                },
                "required": [],
            },
        },
        {
            "nombre": LEER_DXF,
            "descripcion": (
                "Lee la geometría EXACTA de un plano DXF adjunto (vectorial: no hay que escanear "
                "ni calibrar): muros por sus dos caras, puertas por su arco de giro, ventanas por "
                "sus bloques y los textos (nombres de estancia y superficies) con su posición, "
                "todo en metros. Úsala en vez de plano_detectar_muros cuando el adjunto es un DXF."
            ),
            "parametros": {
                "type": "object",
                "properties": {"imagen": _NUMERO_IMAGEN},
                "required": [],
            },
        },
        {
            "nombre": RECONSTRUIR,
            "descripcion": (
                "Reconstruye un plano a escala real en Blender (casa 3D con muros, huecos con "
                "carpintería y suelos), AutoCAD (planta 2D por capas: muros con relleno, puertas "
                "con su giro, ventanas, rótulos con m² y cotas), SketchUp (3D) o Revit (muros, "
                "suelos, puertas, ventanas y habitaciones BIM nativas). Valida y limpia el plano "
                "antes: endereza, alinea y une muros, mide cada hueco en el dibujo y compara la "
                "superficie de cada estancia con la del plano. El usuario ve una imagen de "
                "control con la reconstrucción encima del original.\n"
                "Formato de `plano` (coordenadas en `unidades`; ancho, alto, antepecho, altura, "
                "nivel y medidas de calibración SIEMPRE en metros):\n"
                "- unidades: 'px' (coordenadas de plano_detectar_muros), 'm' (plano_leer_dxf o "
                "medidas leídas), 'cm' o 'mm'. giro: el que indique plano_detectar_muros.\n"
                "- calibracion (obligatoria con px): cotas del plano, mejor 2-3 de muros largos "
                "distintos: {\"muro\": \"H1\", \"medida\": 10.2, \"referencia\": \"exterior\"} "
                "(cota exterior de fachada) o \"eje\"; o {\"p1\": [x,y], \"p2\": [x,y], \"medida\": m}.\n"
                "- plantas: [{nombre, nivel, altura, imagen (nº de adjunto), muros: [{id, inicio, "
                "fin, espesor}], huecos: [{tipo: puerta|ventana|ventanal|paso, centro: [x,y] (sobre "
                "el muro o en su corte), ancho, alto, antepecho, abre_hacia: [x,y] punto de la "
                "estancia hacia la que abre la puerta}], estancias: [{nombre, centro: [x,y] (un "
                "punto dentro de la estancia, p. ej. donde está su rótulo), superficie: m² que "
                "indica el plano}]}].\n"
                "Método: 1) solo_validar=true; 2) corrige lo que marque el informe (cotas que no "
                "cuadran, estancias que no cierran, superficies con ✘, huecos sin declarar); "
                "3) construye con solo_validar=false. Usa reemplazar=true solo para rehacer una "
                "reconstrucción anterior del mismo plano, con permiso del usuario."
            ),
            "parametros": {
                "type": "object",
                "properties": {
                    "programa": {"type": "string", "enum": list(constructores.PROGRAMAS)},
                    "plano": _ESQUEMA_PLANO,
                    "solo_validar": {"type": "boolean"},
                    "reemplazar": {"type": "boolean"},
                    "imagen": _NUMERO_IMAGEN,
                },
                "required": ["programa", "plano"],
            },
        },
    ]


# ------------------------------------------------------------------ adjuntos

def adjuntos_recientes(historial):
    """Adjuntos del mensaje de usuario más reciente que tenga alguno."""
    for entrada in reversed(historial):
        if entrada.get("tipo") == "usuario" and entrada.get("adjuntos"):
            return entrada["adjuntos"]
    return []


def _adjunto(historial, numero):
    adjuntos = adjuntos_recientes(historial)
    if not adjuntos:
        raise modelo.ErrorPlano("No hay ningún plano adjunto: pide al usuario que lo adjunte con el clip.")
    try:
        numero = int(numero or 1)
    except (TypeError, ValueError):
        numero = 1
    if not 1 <= numero <= len(adjuntos):
        raise modelo.ErrorPlano(f"El adjunto {numero} no existe: hay {len(adjuntos)}.")
    return adjuntos[numero - 1]


def _bytes(adjunto):
    return base64.b64decode(adjunto["datos"])


def nota_adjuntos(adjuntos):
    """Línea que numera los adjuntos para el modelo (lo que no ve en la imagen)."""
    partes = []
    for k, a in enumerate(adjuntos, 1):
        origen = a.get("origen") or {}
        if origen.get("tipo") == "pdf":
            partes.append(f"{k}) página {origen.get('pagina')}/{origen.get('paginas')} del PDF «{origen.get('nombre')}»")
        elif origen.get("tipo") == "dxf":
            partes.append(f"{k}) plano DXF «{origen.get('nombre')}» (vectorial: usa {LEER_DXF})")
        else:
            partes.append(f"{k}) imagen")
    return "[Adjuntos de este mensaje: " + "; ".join(partes) + ".]"


# ----------------------------------------------------------------- ejecución

def ejecutar(nombre, argumentos, historial, conectores):
    """Ejecuta una herramienta de planos y devuelve el texto para el modelo."""
    try:
        if nombre == DETECTAR:
            return _detectar(argumentos, historial)
        if nombre == LEER_DXF:
            return _leer_dxf(argumentos, historial)
        if nombre == RECONSTRUIR:
            return _reconstruir(argumentos, historial, conectores)
    except (modelo.ErrorPlano, detector.ErrorDetector, importar.ErrorImportacion) as exc:
        return f"ERROR: {exc}"
    return f"ERROR: la herramienta '{nombre}' no existe."


def _detectar(argumentos, historial):
    adjunto = _adjunto(historial, argumentos.get("imagen"))
    origen = adjunto.get("origen") or {}
    if origen.get("tipo") == "dxf":
        return f"ERROR: ese adjunto es un DXF vectorial; usa {LEER_DXF}, que da sus medidas exactas."
    datos, escala = _bytes(adjunto), 1.0
    if origen.get("tipo") == "pdf":
        # Se mide sobre la página en alta resolución y se devuelve en los
        # píxeles de la vista que ve el modelo.
        alta = importar.ruta_guardada(origen.get("id"), "png")
        if alta is not None:
            datos, escala = alta.read_bytes(), float(origen.get("escala_vista") or 1.0)
    modo = str(argumentos.get("modo") or "auto")
    if modo not in ("auto", "macizo", "hueco"):
        modo = "auto"
    return detector.resumen_texto(detector.detectar_muros(datos, modo=modo, escala_salida=escala))


def _leer_dxf(argumentos, historial):
    adjunto = _adjunto(historial, argumentos.get("imagen"))
    origen = adjunto.get("origen") or {}
    if origen.get("tipo") != "dxf":
        return f"ERROR: ese adjunto no es un DXF; para imágenes y PDF usa {DETECTAR}."
    ruta = importar.ruta_guardada(origen.get("id"), "dxf")
    if ruta is None:
        return "ERROR: el DXF original ya no está guardado (se conservan 30 días); pide que lo adjunte de nuevo."
    return importar.resumen_dxf(importar.analizar_dxf(ruta))


def _guardar_vista(png):
    # Import diferido: agent importa este módulo, y la carpeta de renders es suya.
    from ..agent import CARPETA_RENDERS, _MARCA_RENDER

    CARPETA_RENDERS.mkdir(parents=True, exist_ok=True)
    ruta = CARPETA_RENDERS / f"plano-{uuid.uuid4().hex[:10]}.png"
    ruta.write_bytes(png)
    return f"{_MARCA_RENDER} {ruta}"


def _vistas_control(plano, datos_plano, argumentos, historial):
    """Marcas de render con la imagen de control de cada planta."""
    marcas = []
    adjuntos = adjuntos_recientes(historial)
    brutas = datos_plano.get("plantas") or []
    for k, planta in enumerate(plano["plantas"]):
        fondo = None
        numero = (brutas[k].get("imagen") if k < len(brutas) and isinstance(brutas[k], dict) else None) \
            or argumentos.get("imagen") or (1 if len(adjuntos) == 1 else None)
        if planta["transformacion"]["invertir_y"] and numero:
            try:
                adjunto = adjuntos[int(numero) - 1]
                if (adjunto.get("origen") or {}).get("tipo") != "dxf":
                    fondo = _bytes(adjunto)
            except (IndexError, ValueError, TypeError):
                fondo = None
        try:
            marcas.append(_guardar_vista(vista.dibujar(planta, fondo)))
        except Exception:  # la imagen de control nunca debe impedir construir
            continue
    return marcas


def _reconstruir(argumentos, historial, conectores):
    datos_plano = argumentos.get("plano")
    plano, informe = modelo.normalizar(datos_plano)
    marcas = _vistas_control(plano, datos_plano, argumentos, historial)
    pie = ("\n" + "\n".join(marcas)) if marcas else ""

    if argumentos.get("solo_validar"):
        return (
            "VALIDACIÓN (no se ha construido nada todavía):\n" + informe
            + "\n\nCorrige los avisos que procedan y vuelve a llamar con solo_validar=false." + pie
        )

    programa = str(argumentos.get("programa", "")).lower()
    if programa not in _EJECUCION:
        return f"ERROR: programa «{programa}» no válido; usa {', '.join(_EJECUCION)}."
    conector = next((c for c in conectores if c.id == programa), None)
    if conector is None or not conector.disponible():
        return (
            f"ERROR: {programa} no está conectado. El plano es válido; dile al usuario que lo "
            "abra (o elige otro programa conectado).\n\n" + informe + pie
        )
    codigo = constructores.generar(programa, plano, reemplazar=bool(argumentos.get("reemplazar")))
    salida = conector.ejecutar(_EJECUCION[programa], {"codigo": codigo})
    estado = "con errores" if str(salida).startswith("ERROR") else "completada"
    return (
        f"Reconstrucción en {conector.nombre} {estado}.\n\n{informe}\n\n"
        f"Salida de {conector.nombre}:\n{salida}{pie}"
    )
