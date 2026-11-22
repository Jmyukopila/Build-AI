"""Herramientas del agente para recursos de render y fotos de referencia.

Como las de planos, son internas (no hay un programa que abrir):
- recursos_buscar / recursos_descargar: HDRI, texturas PBR y modelos de Poly
  Haven, solo cuando Blender está conectado (es quien los usa).
- referencias_buscar: fotos de arquitectura real que el usuario y la IA ven en
  el chat, para imitar un estilo o comparar el render con la realidad.
"""

from pathlib import Path

from .. import config as cfg
from . import polyhaven, referencias

PROGRAMA = "Recursos"
BUSCAR = "recursos_buscar"
DESCARGAR = "recursos_descargar"
REFERENCIAS = "referencias_buscar"
NOMBRES = (BUSCAR, DESCARGAR, REFERENCIAS)
_DE_BLENDER = (BUSCAR, DESCARGAR)

_TIPO = {"type": "string", "enum": list(polyhaven.TIPOS),
         "description": "hdri (cielo real), textura (material PBR) o modelo (mueble/objeto 3D)"}


def herramientas(con_blender: bool) -> list:
    lista = []
    if con_blender:
        lista += [
            {
                "nombre": BUSCAR,
                "descripcion": (
                    "Busca recursos REALES y gratuitos (CC0) de Poly Haven para renders de Blender: "
                    "cielos HDRI fotografiados, texturas PBR (ladrillo, piedra, hormigón, madera, "
                    "baldosa, yeso, tejas…) a tamaño real y modelos 3D de mobiliario y decoración. "
                    "Úsalos cuando el usuario quiera un render realista: un HDRI y texturas reales "
                    "superan a cualquier material procedimental. Consulta en español o inglés."
                ),
                "parametros": {
                    "type": "object",
                    "properties": {
                        "tipo": _TIPO,
                        "consulta": {"type": "string", "description": "p. ej. 'ladrillo rojo', 'atardecer ciudad', 'sillón'"},
                        "cantidad": {"type": "integer", "description": "1-20 (por defecto 8)"},
                    },
                    "required": ["tipo"],
                },
            },
            {
                "nombre": DESCARGAR,
                "descripcion": (
                    "Descarga a este ordenador un recurso de Poly Haven (por su id de "
                    "recursos_buscar) para usarlo en Blender con el kit: hdri('<id>'), "
                    "material='ph:<id>' en muro/forjado/caja… o material_pbr('<id>'), y "
                    "modelo('<id>', posicion=(x, y)). Resolución '2k' por defecto ('4k' solo para "
                    "primeros planos: pesa mucho más)."
                ),
                "parametros": {
                    "type": "object",
                    "properties": {
                        "tipo": _TIPO,
                        "id": {"type": "string"},
                        "resolucion": {"type": "string", "enum": list(polyhaven.RESOLUCIONES)},
                    },
                    "required": ["tipo", "id"],
                },
            },
        ]
    lista.append({
        "nombre": REFERENCIAS,
        "descripcion": (
            "Busca fotos de arquitectura REAL (fachadas, interiores, materiales, estilos) y las "
            "muestra en el chat con su autor y licencia; tú también las ves. Úsala para "
            "proponer estilos, para tener una referencia concreta que imitar en un render, o "
            "cuando el usuario pida ideas o ejemplos. Escribe la consulta EN INGLÉS (el banco "
            "está en inglés): p. ej. 'white mediterranean house courtyard'. Cita en tu "
            "respuesta el autor y la fuente de las fotos que uses."
        ),
        "parametros": {
            "type": "object",
            "properties": {
                "consulta": {"type": "string"},
                "cantidad": {"type": "integer", "description": "1-6 (por defecto 4)"},
                "fuente": {"type": "string", "enum": list(referencias.FUENTES)},
            },
            "required": ["consulta"],
        },
    })
    return lista


def ejecutar(nombre, argumentos, historial=None, conectores=None):
    try:
        if nombre == BUSCAR:
            return _buscar(argumentos)
        if nombre == DESCARGAR:
            return _descargar(argumentos)
        if nombre == REFERENCIAS:
            return _referencias(argumentos)
    except (polyhaven.ErrorRecursos, referencias.ErrorReferencias) as exc:
        return f"ERROR: {exc}"
    return f"ERROR: la herramienta '{nombre}' no existe."


def _uso(tipo, ident):
    if tipo == "hdri":
        return f"hdri('{ident}', fuerza=1.0, rotacion=0)"
    if tipo == "textura":
        return f"material='ph:{ident}' en cualquier función del kit (o material_pbr('{ident}'))"
    return f"modelo('{ident}', posicion=(x, y), rotacion=0, nivel=0.0)"


def _buscar(argumentos):
    tipo = str(argumentos.get("tipo", ""))
    encontrados = polyhaven.buscar(tipo, str(argumentos.get("consulta") or ""), argumentos.get("cantidad") or 8)
    if not encontrados:
        return f"No hay {tipo}s de Poly Haven para «{argumentos.get('consulta')}». Prueba otras palabras (en inglés suele haber más)."
    lineas = [f"{len(encontrados)} {tipo}(s) de Poly Haven (CC0). Descarga el elegido con {DESCARGAR}:"]
    for r in encontrados:
        tamano = f", {' × '.join(str(t) for t in r['tamano_m'])} m" if r["tamano_m"] else ""
        hecho = " [ya descargado]" if r["descargado"] else ""
        lineas.append(f"  {r['id']}: {r['nombre']}{tamano} — {', '.join(r['etiquetas'][:6])}{hecho}")
    return "\n".join(lineas)


def _descargar(argumentos):
    tipo = str(argumentos.get("tipo", ""))
    ident = str(argumentos.get("id", "")).strip()
    if ident.startswith("ph:"):
        ident = ident[3:]
    manifiesto = polyhaven.descargar(tipo, ident, str(argumentos.get("resolucion") or polyhaven.RESOLUCION_DEFECTO))
    detalle = ""
    if tipo == "textura":
        ancho, alto = manifiesto["tamano_m"]
        detalle = f" Cada repetición mide {ancho:.2f} × {alto:.2f} m (se aplica a escala real)."
    return (
        f"Descargado {tipo} '{ident}' ({manifiesto['resolucion']}, licencia CC0).{detalle}\n"
        f"Úsalo en blender_ejecutar_python con: {_uso(tipo, ident)}"
    )


def _referencias(argumentos):
    # Import diferido: la carpeta de renders y su marca son del agente, que
    # importa este módulo (así las fotos salen en el chat como los renders).
    from ..agent import CARPETA_RENDERS, _MARCA_RENDER

    clave = (cfg.cargar().get("servicios") or {}).get("pexels", "")
    fotos, avisos = referencias.buscar(
        str(argumentos.get("consulta") or ""), argumentos.get("cantidad") or 4,
        str(argumentos.get("fuente") or "auto"), clave_pexels=clave, carpeta=CARPETA_RENDERS,
    )
    if not fotos:
        return ("No encontré fotos para esa búsqueda. Prueba otras palabras en inglés, más generales."
                + ("\n" + "\n".join(avisos) if avisos else ""))
    lineas = [f"{len(fotos)} referencia(s); el usuario ya las ve en el chat y tú las recibes como imagen:"]
    for f in fotos:
        lineas.append(f"  Ref. {f['numero']}: «{f['titulo'][:70]}» — {f['autor']} · {f['licencia']} · {f['fuente']} · {f['enlace']}")
    lineas += avisos
    lineas += [f"{_MARCA_RENDER} {Path(f['archivo'])}" for f in fotos]
    return "\n".join(lineas)
