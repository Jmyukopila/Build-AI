"""Conector con SketchUp a través de la extensión BuildAI (HTTP local)."""

import httpx

from .. import entregables
from .base import Conector, recortar

PUERTO_SKETCHUP = 8602
BASE = f"http://127.0.0.1:{PUERTO_SKETCHUP}"

# Formatos de model.export. Todos menos COLLADA exigen SketchUp Pro.
_EXPORTABLES = ("dwg", "dxf", "ifc", "obj", "fbx", "stl", "dae")
_SOLO_PRO = tuple(f for f in _EXPORTABLES if f != "dae")


class ConectorSketchUp(Conector):
    id = "sketchup"
    nombre = "SketchUp"
    icono = "sketchup"
    ayuda = (
        "1. Pulsa «Conectar automáticamente» aquí abajo: BuildAI instala la "
        "extensión en todas tus versiones de SketchUp (2014 o superior).\n"
        "2. Abre (o reinicia) SketchUp. La extensión se inicia sola y el punto "
        "se pondrá verde en unos segundos.\n"
        "\n"
        "Manual (alternativa): copia addons\\sketchup\\buildai_sketchup.rb a la "
        "carpeta Plugins de SketchUp (%APPDATA%\\SketchUp\\SketchUp 20XX\\"
        "SketchUp\\Plugins) y reinicia SketchUp."
    )

    def disponible(self) -> bool:
        try:
            r = httpx.get(f"{BASE}/ping", timeout=2.0)
            return r.status_code == 200
        except httpx.HTTPError:
            return False

    def herramientas(self) -> list:
        return [
            {
                "nombre": "sketchup_informacion",
                "descripcion": (
                    "Devuelve un resumen del modelo actual de SketchUp: nombre, "
                    "entidades, componentes, materiales y capas/etiquetas."
                ),
                "parametros": {"type": "object", "properties": {}, "required": []},
            },
            {
                "nombre": "sketchup_ejecutar_ruby",
                "descripcion": (
                    "Ejecuta código Ruby dentro de SketchUp usando su API "
                    "(Sketchup.active_model, etc.). Úsala para crear o modificar "
                    "geometría, grupos, componentes y materiales. El valor de la "
                    "última expresión (o lo impreso con puts) se devuelve como texto.\n\n"
                    "CRÍTICO — unidades: la API mide en PULGADAS. Escribe toda medida con "
                    "el sufijo métrico de Ruby: 2.7.m, 80.cm, 300.mm (nunca números sueltos).\n"
                    "Método de trabajo fiable:\n"
                    "- Agrupa cada elemento en su propio grupo con nombre: "
                    "grp = Sketchup.active_model.active_entities.add_group; "
                    "grp.name = 'Muro sur'; construye dentro de grp.entities.\n"
                    "- Muros y volúmenes: dibuja la cara en planta y extrúyela: "
                    "cara = grp.entities.add_face([0,0,0], [5.m,0,0], [5.m,0.2.m,0], "
                    "[0,0.2.m,0]); cara.pushpull(cara.normal.z < 0 ? -2.7.m : 2.7.m) "
                    "(las caras horizontales suelen nacer mirando hacia abajo: comprueba "
                    "cara.normal antes de decidir el signo).\n"
                    "- Huecos de puertas/ventanas: dibuja la cara del hueco sobre la cara "
                    "del muro y haz pushpull del espesor para vaciarlo.\n"
                    "- Materiales y color: mat = Sketchup.active_model.materials.add('Madera'); "
                    "mat.color = Sketchup::Color.new(170, 120, 70); cara.material = mat "
                    "(o grp.material = mat para todo el grupo).\n"
                    "- Organiza por etiquetas: capa = Sketchup.active_model.layers.add "
                    "('Planta 1'); grp.layer = capa.\n"
                    "- Envuelve cada paso en model.start_operation('Paso', true) … "
                    "model.commit_operation para que el usuario pueda deshacerlo de una vez.\n"
                    "- Presentación final: activa sombras con si = model.shadow_info; "
                    "si['DisplayShadows'] = true (y ajusta si['ShadowTime'] = Time.utc(2026, 6, 21, 17, 0, 0) "
                    "para luz de tarde); encuadra con Sketchup.send_action('viewZoomExtents:') "
                    "o coloca la cámara: model.active_view.camera = Sketchup::Camera.new("
                    "[x_ojo, y_ojo, z_ojo], [x_mira, y_mira, z_mira], Z_AXIS) con medidas .m.\n"
                    "- Rendimiento: para volúmenes repetidos define un ComponentDefinition una vez "
                    "y usa add_instance con transformaciones, en vez de redibujar la geometría."
                ),
                "parametros": {
                    "type": "object",
                    "properties": {
                        "codigo": {
                            "type": "string",
                            "description": "Código Ruby a ejecutar en SketchUp.",
                        }
                    },
                    "required": ["codigo"],
                },
            },
            {
                "nombre": "sketchup_exportar",
                "descripcion": (
                    "Exporta el modelo a un archivo profesional y se lo entrega al "
                    "usuario como descarga.\n"
                    "Formatos: 'dwg' y 'dxf' (CAD, para llevar el trabajo a AutoCAD), "
                    "'ifc' (BIM, para coordinar con Revit o ArchiCAD), 'obj', 'fbx' y "
                    "'stl' (3D), 'dae' (COLLADA, el único que también funciona en la "
                    "versión gratuita).\n"
                    "SketchUp gratuito solo exporta 'dae'; los demás formatos exigen "
                    "SketchUp Pro y la herramienta lo avisa si no lo hay."
                ),
                "parametros": {
                    "type": "object",
                    "properties": {
                        "formato": {
                            "type": "string",
                            "enum": list(_EXPORTABLES),
                            "description": "Formato del archivo a generar.",
                        },
                        "nombre": {
                            "type": "string",
                            "description": "Nombre descriptivo, p. ej. 'vivienda-unifamiliar'.",
                        },
                    },
                    "required": ["formato"],
                },
            },
        ]

    def ejecutar(self, nombre: str, argumentos: dict) -> str:
        exportando = nombre == "sketchup_exportar"
        if exportando:
            formato = str(argumentos.get("formato", "")).lower().strip()
            if formato not in _EXPORTABLES:
                return (
                    f"ERROR: SketchUp no exporta a {formato.upper()}. Puede exportar a "
                    f"{', '.join(_EXPORTABLES)}."
                )
            codigo = _ruby_exportar(formato, argumentos.get("nombre"))
        else:
            codigo = argumentos.get("codigo", "")
        try:
            if nombre == "sketchup_informacion":
                r = httpx.get(f"{BASE}/info", timeout=30.0)
            else:
                r = httpx.post(
                    f"{BASE}/ejecutar",
                    json={"codigo": codigo},
                    # Exportar un modelo grande tarda más que ejecutar un script.
                    timeout=180.0 if exportando else 120.0,
                )
        except httpx.HTTPError as exc:
            return (
                f"ERROR: no se pudo hablar con SketchUp ({exc}). "
                "¿Está abierto con la extensión BuildAI iniciada?"
            )
        datos = r.json()
        if not datos.get("ok"):
            return f"ERROR en SketchUp: {recortar(datos.get('error', 'desconocido'))}"
        return recortar(datos.get("resultado", "(sin salida)"))


def _cadena_ruby(texto: str) -> str:
    """Literal Ruby entre comillas simples. Las rutas de Windows van llenas de
    barras invertidas, que Ruby interpretaría como escapes."""
    return "'" + str(texto).replace("\\", "\\\\").replace("'", "\\'") + "'"


def _ruby_exportar(formato: str, nombre: str) -> str:
    """Código Ruby que exporta y DEVUELVE el resultado como texto: el puente de
    SketchUp entrega el valor de la última expresión, no lo que se imprime."""
    ruta = entregables.ruta_para(nombre or "modelo", formato)
    aviso_pro = (
        f"ERROR: exportar a {formato.upper()} necesita SketchUp Pro. Con la versión "
        "gratuita solo se puede exportar a DAE (COLLADA)."
    )
    lineas = [
        "begin",
        f"  ruta = {_cadena_ruby(str(ruta))}",
    ]
    if formato in _SOLO_PRO:
        lineas += [
            "  if !Sketchup.is_pro?",
            f"    {_cadena_ruby(aviso_pro)}",
            "  elsif Sketchup.active_model.export(ruta)",
        ]
    else:
        lineas.append("  if Sketchup.active_model.export(ruta)")
    lineas += [
        "    'ARCHIVO_GUARDADO: ' + ruta",
        "  else",
        "    'ERROR: SketchUp rechazó la exportación. Comprueba que el modelo tiene geometría.'",
        "  end",
        "rescue => e",
        "  'ERROR exportando desde SketchUp: ' + e.message",
        "end",
    ]
    return "\n".join(lineas)
