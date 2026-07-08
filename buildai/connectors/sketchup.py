"""Conector con SketchUp a través de la extensión BuildAI (HTTP local)."""

import httpx

from .base import Conector, recortar

PUERTO_SKETCHUP = 8602
BASE = f"http://127.0.0.1:{PUERTO_SKETCHUP}"


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
        ]

    def ejecutar(self, nombre: str, argumentos: dict) -> str:
        try:
            if nombre == "sketchup_informacion":
                r = httpx.get(f"{BASE}/info", timeout=30.0)
            else:
                r = httpx.post(
                    f"{BASE}/ejecutar",
                    json={"codigo": argumentos.get("codigo", "")},
                    timeout=120.0,
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
