"""Kit de construcción paramétrico para Blender.

Este archivo NO se importa en la app: su código fuente se antepone a cada
ejecución de `blender_ejecutar_python`, de modo que el modelo de IA dispone
de funciones de arquitectura de alto nivel (muro, forjado, cubierta,
escalera…) en vez de tener que escribir geometría bpy a mano. Así incluso
los modelos gratuitos construyen edificios complejos de forma fiable.

Convenciones: unidades en metros, eje Z hacia arriba, coordenadas de
esquina (no de centro). Todo usa mallas puras (from_pydata), sin operadores
de interfaz, para funcionar igual con Blender abierto o en segundo plano.
"""

import math
import random
import time
from pathlib import Path

import bpy
from mathutils import Vector

# ---------------------------------------------------------------- materiales

# Paleta de acabados habituales; material("vidrio") etc. los crea al vuelo.
# Los que llevan "textura" generan un veteado/grano procedimental (sin imágenes).
_PRESETS = {
    "blanco":       {"color": (0.92, 0.92, 0.90), "rugosidad": 0.7},
    "crema":        {"color": (0.90, 0.86, 0.76), "rugosidad": 0.7},
    "gris_claro":   {"color": (0.75, 0.75, 0.75), "rugosidad": 0.6},
    "hormigon":     {"color": (0.55, 0.55, 0.53), "rugosidad": 0.8, "textura": "hormigon"},
    "antracita":    {"color": (0.09, 0.09, 0.10), "rugosidad": 0.5},
    "negro_mate":   {"color": (0.02, 0.02, 0.02), "rugosidad": 0.35},
    "madera":       {"color": (0.43, 0.28, 0.16), "rugosidad": 0.5, "textura": "madera"},
    "madera_clara": {"color": (0.66, 0.51, 0.34), "rugosidad": 0.5, "textura": "madera"},
    "parquet":      {"color": (0.58, 0.42, 0.26), "rugosidad": 0.35, "textura": "madera"},
    "marmol":       {"color": (0.88, 0.87, 0.84), "rugosidad": 0.15, "textura": "marmol"},
    "ladrillo":     {"color": (0.50, 0.24, 0.17), "rugosidad": 0.9, "textura": "ladrillo"},
    "baldosa":      {"color": (0.78, 0.77, 0.74), "rugosidad": 0.25, "textura": "baldosa"},
    "ceramica":     {"color": (0.94, 0.94, 0.92), "rugosidad": 0.12},
    "tela_gris":    {"color": (0.42, 0.42, 0.44), "rugosidad": 0.95, "textura": "tela"},
    "tela_beige":   {"color": (0.72, 0.66, 0.55), "rugosidad": 0.95, "textura": "tela"},
    "tela_azul":    {"color": (0.23, 0.30, 0.42), "rugosidad": 0.95, "textura": "tela"},
    "hoja":         {"color": (0.16, 0.28, 0.12), "rugosidad": 0.9, "textura": "tela"},
    "teja":         {"color": (0.44, 0.18, 0.12), "rugosidad": 0.8},
    "piedra":       {"color": (0.58, 0.55, 0.48), "rugosidad": 0.9, "textura": "hormigon"},
    "piedra_muro":  {"color": (0.60, 0.53, 0.43), "rugosidad": 0.9, "textura": "ladrillo"},
    "cesped":       {"color": (0.18, 0.33, 0.12), "rugosidad": 0.95, "textura": "cesped"},
    "tierra":       {"color": (0.30, 0.20, 0.13), "rugosidad": 0.97, "textura": "tierra"},
    "tierra_seca":  {"color": (0.46, 0.33, 0.20), "rugosidad": 0.97, "textura": "tierra"},
    "arena":        {"color": (0.76, 0.68, 0.50), "rugosidad": 1.0, "textura": "arena"},
    "gravilla":     {"color": (0.50, 0.48, 0.45), "rugosidad": 0.9, "textura": "gravilla"},
    "pavimento":    {"color": (0.55, 0.53, 0.48), "rugosidad": 0.8, "textura": "hormigon"},
    "acero":        {"color": (0.62, 0.63, 0.65), "rugosidad": 0.3, "metalico": 1.0},
    "metal_negro":  {"color": (0.05, 0.05, 0.05), "rugosidad": 0.4, "metalico": 1.0},
    "espejo":       {"color": (0.85, 0.87, 0.90), "rugosidad": 0.02, "metalico": 1.0},
    "vidrio":       {"color": (0.80, 0.88, 0.88), "rugosidad": 0.03, "transparente": True},
    "agua":         {"color": (0.80, 0.92, 0.94), "rugosidad": 0.02, "transparente": True, "textura": "agua"},
    "baldosa_piscina": {"color": (0.45, 0.72, 0.76), "rugosidad": 0.15, "textura": "baldosa"},
}


def _entrada(nodo, *nombres):
    """Devuelve la primera entrada del nodo que exista (los nombres cambian entre versiones)."""
    for n in nombres:
        if n in nodo.inputs:
            return nodo.inputs[n]
    return None


def material(nombre, color=None, rugosidad=None, metalico=None, transparente=None,
             textura=None, escala=None, emision=None):
    """Crea (o reutiliza) un material. Presets con acabado listo: blanco, crema,
    gris_claro, hormigon, antracita, negro_mate, madera, madera_clara, parquet,
    marmol, ladrillo, baldosa, ceramica, tela_gris, tela_beige, tela_azul, hoja,
    teja, piedra, piedra_muro, cesped, pavimento, acero, metal_negro, espejo,
    vidrio, agua, baldosa_piscina. `color` es (r, g, b) entre 0 y 1; `textura`
    añade veteado y relieve procedimental ("madera", "marmol", "hormigon",
    "ladrillo", "tela", "baldosa", "cesped" o "agua"); `emision` (vatios aprox.)
    hace que el material brille con luz propia (pantallas de lámparas, letreros)."""
    existente = bpy.data.materials.get(nombre)
    if existente is not None and color is None:
        return existente
    base = dict(_PRESETS.get(nombre, {}))
    if color is not None:
        base["color"] = color
    if rugosidad is not None:
        base["rugosidad"] = rugosidad
    if metalico is not None:
        base["metalico"] = metalico
    if transparente is not None:
        base["transparente"] = transparente
    if textura is not None:
        base["textura"] = textura
    if emision is not None:
        base["emision"] = emision
    base.setdefault("color", (0.8, 0.8, 0.8))
    base.setdefault("rugosidad", 0.6)
    base.setdefault("metalico", 0.0)
    base.setdefault("transparente", False)
    base.setdefault("textura", None)
    base.setdefault("emision", 0.0)

    mat = existente or bpy.data.materials.new(nombre)
    mat.use_nodes = True
    bsdf = next((n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if bsdf is not None:
        r, g, b = base["color"]
        bsdf.inputs["Base Color"].default_value = (r, g, b, 1.0)
        bsdf.inputs["Roughness"].default_value = base["rugosidad"]
        bsdf.inputs["Metallic"].default_value = base["metalico"]
        if base["transparente"]:
            trans = _entrada(bsdf, "Transmission Weight", "Transmission")
            if trans is not None:
                trans.default_value = 1.0
            ior = _entrada(bsdf, "IOR")
            if ior is not None:
                ior.default_value = 1.33 if base["textura"] == "agua" else 1.45
            # Alpha < 1 solo para que EEVEE (el visor) lo muestre transparente;
            # render() lo devuelve a 1.0 en Cycles, donde manda la transmisión.
            alfa = _entrada(bsdf, "Alpha")
            if alfa is not None:
                alfa.default_value = 0.35
            for prop, valor in (("blend_method", "BLEND"), ("surface_render_method", "BLENDED")):
                if hasattr(mat, prop):
                    try:
                        setattr(mat, prop, valor)
                    except Exception:
                        pass
            for prop in ("use_screen_refraction", "use_raytrace_refraction"):
                if hasattr(mat, prop):
                    try:
                        setattr(mat, prop, True)
                    except Exception:
                        pass
        if base["emision"]:
            em_color = _entrada(bsdf, "Emission Color", "Emission")
            if em_color is not None:
                em_color.default_value = (r, g, b, 1.0)
            em_fuerza = _entrada(bsdf, "Emission Strength")
            if em_fuerza is not None:
                em_fuerza.default_value = base["emision"]
        if base["textura"]:
            try:
                _nodos_textura(mat, bsdf, base["textura"], base["color"], escala)
            except Exception as exc:
                print(f"(aviso: textura de '{nombre}' no aplicada: {exc})")
    mat.diffuse_color = (*base["color"], 1.0)
    return mat


# Fuerza del relieve (bump) por tipo de textura: el microrrelieve es lo que
# hace que un material deje de parecer plástico en el render.
_RELIEVE = {"ladrillo": 0.35, "baldosa": 0.06, "madera": 0.10, "marmol": 0.03,
            "hormigon": 0.15, "tela": 0.25, "cesped": 0.45, "agua": 0.10,
            "tierra": 0.5, "arena": 0.28, "gravilla": 0.6}


def _conectar_relieve(nt, bsdf, tex, fuerza):
    """Convierte el patrón de la textura en microrrelieve sobre la normal."""
    if fuerza <= 0 or "Fac" not in tex.outputs or "Normal" not in bsdf.inputs:
        return
    bump = nt.nodes.new("ShaderNodeBump")
    e = _entrada(bump, "Strength")
    if e is not None:
        e.default_value = fuerza
    nt.links.new(tex.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])


def _nodos_textura(mat, bsdf, tipo, color, escala):
    """Veteado y relieve procedimental (sin imágenes)."""
    nt = mat.node_tree
    r, g, b = color
    oscuro = (r * 0.55, g * 0.55, b * 0.55, 1.0)
    claro = (min(r * 1.15, 1.0), min(g * 1.15, 1.0), min(b * 1.15, 1.0), 1.0)
    coord = nt.nodes.new("ShaderNodeTexCoord")
    relieve = _RELIEVE.get(tipo, 0.1)

    if tipo == "agua":
        # Solo ondulación de la superficie: el color lo pone la transmisión.
        tex = nt.nodes.new("ShaderNodeTexNoise")
        tex.inputs["Scale"].default_value = escala or 3.0
        detalle = _entrada(tex, "Detail")
        if detalle is not None:
            detalle.default_value = 6.0
        nt.links.new(coord.outputs["Object"], tex.inputs["Vector"])
        _conectar_relieve(nt, bsdf, tex, relieve)
        return
    if tipo == "ladrillo":
        tex = nt.nodes.new("ShaderNodeTexBrick")
        tex.inputs["Color1"].default_value = (r, g, b, 1.0)
        tex.inputs["Color2"].default_value = oscuro
        tex.inputs["Mortar"].default_value = (0.80, 0.78, 0.74, 1.0)
        tex.inputs["Scale"].default_value = escala or 3.5
        # El patrón de ladrillo es 2D en el plano XY: se gira al plano vertical
        # de los muros (los muros del kit se construyen en su plano local X-Z).
        mapeo = nt.nodes.new("ShaderNodeMapping")
        mapeo.inputs["Rotation"].default_value = (math.pi / 2, 0.0, 0.0)
        nt.links.new(coord.outputs["Object"], mapeo.inputs["Vector"])
        nt.links.new(mapeo.outputs["Vector"], tex.inputs["Vector"])
        nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
        _conectar_relieve(nt, bsdf, tex, relieve)
        return
    if tipo == "baldosa":
        tex = nt.nodes.new("ShaderNodeTexChecker")
        tex.inputs["Color1"].default_value = (r, g, b, 1.0)
        tex.inputs["Color2"].default_value = (r * 0.85, g * 0.85, b * 0.85, 1.0)
        tex.inputs["Scale"].default_value = escala or 1.7
        nt.links.new(coord.outputs["Object"], tex.inputs["Vector"])
        nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
        _conectar_relieve(nt, bsdf, tex, relieve)
        return

    if tipo in ("cesped", "tierra", "tierra_seca", "arena", "gravilla"):
        # Suelo natural: manchas de color a gran escala (calvas de césped, zonas
        # secas, vetas de tierra) + un microrrelieve fino aparte. Sin la mancha,
        # una superficie grande de suelo lee como fieltro plano de un solo tono.
        manchas = nt.nodes.new("ShaderNodeTexNoise")
        manchas.inputs["Scale"].default_value = escala or {
            "cesped": 3.0, "tierra": 2.2, "tierra_seca": 2.2,
            "arena": 4.0, "gravilla": 6.0}.get(tipo, 3.0)
        det = _entrada(manchas, "Detail")
        if det is not None:
            det.default_value = 5.0
        seco = {
            "cesped":      (min(r * 1.7, 1.0), min(g * 1.25, 1.0), b * 0.75, 1.0),
            "tierra":      (min(r * 1.35, 1.0), min(g * 1.30, 1.0), min(b * 1.30, 1.0), 1.0),
            "tierra_seca": (min(r * 1.25, 1.0), min(g * 1.25, 1.0), min(b * 1.25, 1.0), 1.0),
            "arena":       (min(r * 1.12, 1.0), min(g * 1.10, 1.0), min(b * 1.08, 1.0), 1.0),
            "gravilla":    (min(r * 1.25, 1.0), min(g * 1.25, 1.0), min(b * 1.25, 1.0), 1.0),
        }[tipo]
        rampa = nt.nodes.new("ShaderNodeValToRGB")
        rampa.color_ramp.elements[0].color = oscuro
        rampa.color_ramp.elements[1].color = seco
        nt.links.new(coord.outputs["Object"], manchas.inputs["Vector"])
        nt.links.new(manchas.outputs["Fac"], rampa.inputs["Fac"])
        nt.links.new(rampa.outputs["Color"], bsdf.inputs["Base Color"])
        micro = nt.nodes.new("ShaderNodeTexNoise")
        micro.inputs["Scale"].default_value = {
            "cesped": 55.0, "arena": 90.0, "gravilla": 22.0}.get(tipo, 40.0)
        mdet = _entrada(micro, "Detail")
        if mdet is not None:
            mdet.default_value = 3.0
        nt.links.new(coord.outputs["Object"], micro.inputs["Vector"])
        _conectar_relieve(nt, bsdf, micro, relieve)
        return

    if tipo == "madera":
        tex = nt.nodes.new("ShaderNodeTexWave")
        tex.inputs["Scale"].default_value = escala or 1.2
        for entrada, valor in (("Distortion", 7.0), ("Detail", 2.0)):
            e = _entrada(tex, entrada)
            if e is not None:
                e.default_value = valor
    else:  # marmol, hormigon, tela
        tex = nt.nodes.new("ShaderNodeTexNoise")
        tex.inputs["Scale"].default_value = escala or {
            "marmol": 2.5, "tela": 60.0}.get(tipo, 14.0)
        detalle = _entrada(tex, "Detail")
        if detalle is not None:
            detalle.default_value = {"marmol": 8.0}.get(tipo, 3.0)
    rampa = nt.nodes.new("ShaderNodeValToRGB")
    rampa.color_ramp.elements[0].color = oscuro
    rampa.color_ramp.elements[1].color = claro
    if tipo == "marmol":
        # Vetas finas oscuras sobre fondo claro
        rampa.color_ramp.elements[0].position = 0.42
        rampa.color_ramp.elements[1].position = 0.55
    nt.links.new(coord.outputs["Object"], tex.inputs["Vector"])
    nt.links.new(tex.outputs["Fac"], rampa.inputs["Fac"])
    nt.links.new(rampa.outputs["Color"], bsdf.inputs["Base Color"])
    _conectar_relieve(nt, bsdf, tex, relieve)


def _mat(m):
    if m is None:
        return None
    return m if isinstance(m, bpy.types.Material) else material(str(m))


# ------------------------------------------------------- mallas y colecciones

def coleccion(nombre):
    """Devuelve la colección con ese nombre, creándola y enlazándola si no existe."""
    col = bpy.data.collections.get(nombre)
    if col is None:
        col = bpy.data.collections.new(nombre)
    if col.name not in bpy.context.scene.collection.children:
        try:
            bpy.context.scene.collection.children.link(col)
        except RuntimeError:
            pass  # ya enlazada en otra rama del árbol
    return col


def _nuevo_objeto(nombre, malla, capa=None, material=None):
    obj = bpy.data.objects.new(nombre, malla)
    destino = coleccion(capa) if capa else bpy.context.scene.collection
    destino.objects.link(obj)
    m = _mat(material)
    if m is not None:
        malla.materials.append(m)
    return obj


_CARAS_CAJA = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]


def _agregar_caja(verts, caras, p0, p1):
    (x0, y0, z0), (x1, y1, z1) = p0, p1
    b = len(verts)
    verts += [
        (x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
        (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1),
    ]
    caras += [tuple(b + i for i in cara) for cara in _CARAS_CAJA]


def _agregar_cilindro(verts, caras, cx, cy, z0, z1, radio, seg=16):
    b = len(verts)
    for z in (z0, z1):
        for i in range(seg):
            a = 2 * math.pi * i / seg
            verts.append((cx + radio * math.cos(a), cy + radio * math.sin(a), z))
    for i in range(seg):
        j = (i + 1) % seg
        caras.append((b + i, b + j, b + seg + j, b + seg + i))
    caras.append(tuple(reversed(range(b, b + seg))))
    caras.append(tuple(range(b + seg, b + 2 * seg)))


def _agregar_esfera(verts, caras, centro, radio, seg=18, anillos=12):
    cx, cy, cz = centro
    b = len(verts)
    verts.append((cx, cy, cz - radio))          # polo sur
    for k in range(1, anillos):
        phi = math.pi * k / anillos
        z = cz - radio * math.cos(phi)
        r = radio * math.sin(phi)
        for i in range(seg):
            a = 2 * math.pi * i / seg
            verts.append((cx + r * math.cos(a), cy + r * math.sin(a), z))
    verts.append((cx, cy, cz + radio))          # polo norte
    norte = len(verts) - 1
    for i in range(seg):
        j = (i + 1) % seg
        caras.append((b, b + 1 + j, b + 1 + i))
        base_sup = b + 1 + (anillos - 2) * seg
        caras.append((norte, base_sup + i, base_sup + j))
    for k in range(anillos - 2):
        f0, f1 = b + 1 + k * seg, b + 1 + (k + 1) * seg
        for i in range(seg):
            j = (i + 1) % seg
            caras.append((f0 + i, f0 + j, f1 + j, f1 + i))


def _malla_piezas(nombre, cajas=(), cilindros=(), esferas=()):
    """Malla combinada de piezas en coordenadas locales:
    cajas [((x0,y0,z0),(x1,y1,z1))…], cilindros [(cx,cy,z0,z1,radio)…],
    esferas [((cx,cy,cz), radio)…]."""
    verts, caras = [], []
    for p0, p1 in cajas:
        _agregar_caja(verts, caras, p0, p1)
    for cx, cy, z0, z1, radio in cilindros:
        _agregar_cilindro(verts, caras, cx, cy, z0, z1, radio)
    for centro, radio in esferas:
        _agregar_esfera(verts, caras, centro, radio)
    malla = bpy.data.meshes.new(nombre)
    malla.from_pydata(verts, [], caras)
    malla.update()
    # Sombreado suave en las superficies curvas (las cajas se quedan facetadas):
    # sin esto, cilindros y esferas se ven "low-poly" en el render.
    primera_curva = 6 * len(cajas)
    if len(malla.polygons) > primera_curva:
        for i, cara in enumerate(malla.polygons):
            cara.use_smooth = i >= primera_curva
    return malla


def _malla_cajas(nombre, cajas):
    """Una malla formada por cajas alineadas a ejes: [((x0,y0,z0),(x1,y1,z1)), …]."""
    return _malla_piezas(nombre, cajas=cajas)


def _colocar(obj, x, y, z, angulo=0.0):
    obj.location = (x, y, z)
    obj.rotation_euler = (0.0, 0.0, angulo)
    return obj


def _sin_sombra(obj):
    """El vidrio y el agua no deben bloquear la luz en el render: sin esto,
    las ventanas proyectan sombra opaca y los interiores salen negros."""
    if obj is None:
        return obj
    for prop in ("visible_shadow",):
        if hasattr(obj, prop):
            try:
                setattr(obj, prop, False)
            except Exception:
                pass
    ciclos = getattr(obj, "cycles_visibility", None)
    if ciclos is not None and hasattr(ciclos, "shadow"):
        try:
            ciclos.shadow = False
        except Exception:
            pass
    return obj


def caja(nombre, origen, dimensiones, material="gris_claro", capa=None):
    """Caja simple. `origen` es la esquina mínima (x, y, z); `dimensiones` (dx, dy, dz)."""
    dx, dy, dz = dimensiones
    malla = _malla_cajas(nombre, [((0, 0, 0), (dx, dy, dz))])
    obj = _nuevo_objeto(nombre, malla, capa, material)
    _colocar(obj, *origen)
    print(f"✔ {obj.name}: caja {dx:.2f}×{dy:.2f}×{dz:.2f} m")
    return obj


def limpiar_todo():
    """Borra TODOS los objetos de la escena. Úsalo solo con permiso del usuario."""
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    try:
        bpy.data.orphans_purge(do_recursive=True)
    except Exception:
        pass
    print("✔ Escena vaciada por completo")


# ------------------------------------------------------------------- muros

def _local_a_mundo(x0, y0, angulo):
    cos_a, sin_a = math.cos(angulo), math.sin(angulo)

    def convertir(u, v):
        return (x0 + u * cos_a - v * sin_a, y0 + u * sin_a + v * cos_a)
    return convertir


def muro(inicio, fin, alto=2.7, espesor=0.2, nivel=0.0, huecos=None,
         material="blanco", capa=None, nombre=None):
    """Muro recto de (x, y) inicio a fin, con huecos y carpinterías automáticas.

    Cada hueco es un dict: {"tipo": "ventana"|"puerta"|"ventanal"|"paso",
    "a": distancia en m desde el inicio, "ancho": m, y opcionales "alto" y
    "antepecho"}. Ventanas y puertas añaden solas su marco, cristal u hoja.
    """
    x0, y0 = inicio
    x1, y1 = fin
    largo = math.hypot(x1 - x0, y1 - y0)
    if largo < 0.01:
        print("✘ muro ignorado: inicio y fin coinciden")
        return None
    angulo = math.atan2(y1 - y0, x1 - x0)
    e2 = espesor / 2.0

    normalizados = []
    for h in (huecos or []):
        tipo = h.get("tipo", "ventana")
        defecto_alto = {"ventana": 1.2, "puerta": 2.05, "ventanal": alto - 0.25, "paso": 2.05}
        defecto_ante = {"ventana": 0.9, "puerta": 0.0, "ventanal": 0.0, "paso": 0.0}
        alto_h = float(h.get("alto", defecto_alto.get(tipo, 1.2)))
        ante = float(h.get("antepecho", defecto_ante.get(tipo, 0.0)))
        a = max(0.0, float(h["a"]))
        ancho_h = float(h["ancho"])
        if a + ancho_h > largo + 0.01 or ante + alto_h > alto + 0.01:
            print(f"✘ hueco fuera del muro (a={a}, ancho={ancho_h}): omitido")
            continue
        normalizados.append({"tipo": tipo, "a": a, "ancho": ancho_h, "alto": alto_h, "ante": ante})
    normalizados.sort(key=lambda h: h["a"])

    cajas = []
    cursor = 0.0
    for h in normalizados:
        if h["a"] > cursor + 0.005:
            cajas.append(((cursor, -e2, 0), (h["a"], e2, alto)))
        if h["ante"] > 0.005:
            cajas.append(((h["a"], -e2, 0), (h["a"] + h["ancho"], e2, h["ante"])))
        techo_hueco = h["ante"] + h["alto"]
        if techo_hueco < alto - 0.005:
            cajas.append(((h["a"], -e2, techo_hueco), (h["a"] + h["ancho"], e2, alto)))
        cursor = h["a"] + h["ancho"]
    if cursor < largo - 0.005:
        cajas.append(((cursor, -e2, 0), (largo, e2, alto)))

    nombre = nombre or "Muro"
    obj = _nuevo_objeto(nombre, _malla_cajas(nombre, cajas or [((0, -e2, 0), (largo, e2, alto))]), capa, material)
    _colocar(obj, x0, y0, nivel, angulo)

    for h in normalizados:
        if h["tipo"] != "paso":
            _carpinteria(h, x0, y0, nivel, angulo, e2, capa)

    print(f"✔ {obj.name}: {largo:.2f} m de largo × {alto:.2f} m, {len(normalizados)} hueco(s)")
    return obj


def _carpinteria(h, x0, y0, nivel, angulo, e2, capa):
    """Marco + cristal (ventana/ventanal) u hoja (puerta) dentro de un hueco de muro."""
    perfil = 0.06
    a, ancho, alto_h, ante = h["a"], h["ancho"], h["alto"], h["ante"]
    cajas_marco = [
        ((a, -perfil / 2, ante), (a + perfil, perfil / 2, ante + alto_h)),
        ((a + ancho - perfil, -perfil / 2, ante), (a + ancho, perfil / 2, ante + alto_h)),
        ((a + perfil, -perfil / 2, ante + alto_h - perfil), (a + ancho - perfil, perfil / 2, ante + alto_h)),
    ]
    if ante > 0.005 or h["tipo"] != "puerta":
        cajas_marco.append(((a + perfil, -perfil / 2, ante), (a + ancho - perfil, perfil / 2, ante + perfil)))
    marco = _nuevo_objeto("Marco", _malla_cajas("Marco", cajas_marco), capa, "antracita")
    _colocar(marco, x0, y0, nivel, angulo)

    if h["tipo"] == "puerta":
        relleno = _nuevo_objeto(
            "Puerta",
            _malla_cajas("Puerta", [((a + perfil, -0.025, ante), (a + ancho - perfil, 0.025, ante + alto_h - perfil))]),
            capa, "madera",
        )
    else:
        relleno = _sin_sombra(_nuevo_objeto(
            "Cristal",
            _malla_cajas("Cristal", [((a + perfil, -0.008, ante + perfil), (a + ancho - perfil, 0.008, ante + alto_h - perfil))]),
            capa, "vidrio",
        ))
    _colocar(relleno, x0, y0, nivel, angulo)


def ventanal(inicio, fin, alto=2.5, nivel=0.0, division=1.2, capa=None):
    """Muro cortina acristalado de suelo a techo, con montantes cada `division` m.
    Ideal para fachadas de casas modernas y plantas bajas de edificios."""
    x0, y0 = inicio
    x1, y1 = fin
    largo = math.hypot(x1 - x0, y1 - y0)
    if largo < 0.05:
        print("✘ ventanal ignorado: demasiado corto")
        return None
    angulo = math.atan2(y1 - y0, x1 - x0)
    p = 0.05
    tramos = max(1, round(largo / division))
    paso = largo / tramos
    cajas = [((0, -p, 0), (largo, p, p)), ((0, -p, alto - p), (largo, p, alto))]
    for i in range(tramos + 1):
        u = min(max(i * paso - p / 2, 0), largo - p)
        cajas.append(((u, -p, p), (u + p, p, alto - p)))
    perfiles = _nuevo_objeto("Ventanal", _malla_cajas("Ventanal", cajas), capa, "antracita")
    _colocar(perfiles, x0, y0, nivel, angulo)
    cristal = _sin_sombra(_nuevo_objeto(
        "Ventanal_cristal",
        _malla_cajas("Ventanal_cristal", [((p, -0.008, p), (largo - p, 0.008, alto - p))]),
        capa, "vidrio",
    ))
    _colocar(cristal, x0, y0, nivel, angulo)
    print(f"✔ {perfiles.name}: {largo:.2f} × {alto:.2f} m, {tramos} paño(s)")
    return perfiles


# --------------------------------------------------------- forjados y cubiertas

def _contorno_ccw(puntos):
    area = sum(puntos[i][0] * puntos[(i + 1) % len(puntos)][1]
               - puntos[(i + 1) % len(puntos)][0] * puntos[i][1] for i in range(len(puntos)))
    return list(puntos) if area >= 0 else list(reversed(puntos))


def forjado(contorno, nivel=0.0, espesor=0.3, material="hormigon", capa=None, nombre=None):
    """Losa horizontal con planta poligonal. `contorno` es una lista de (x, y);
    la cara superior queda en `nivel` (la cota del suelo terminado)."""
    puntos = _contorno_ccw(contorno)
    n = len(puntos)
    if n < 3:
        print("✘ forjado ignorado: hacen falta al menos 3 puntos")
        return None
    verts = [(x, y, -espesor) for x, y in puntos] + [(x, y, 0.0) for x, y in puntos]
    caras = [tuple(reversed(range(n))), tuple(range(n, 2 * n))]
    caras += [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
    nombre = nombre or "Forjado"
    malla = bpy.data.meshes.new(nombre)
    malla.from_pydata(verts, [], caras)
    malla.update()
    obj = _nuevo_objeto(nombre, malla, capa, material)
    obj.location = (0, 0, nivel)
    print(f"✔ {obj.name}: losa de {n} lados a cota {nivel:.2f} m")
    return obj


def cubierta_plana(contorno, nivel, espesor=0.3, peto=0.6, material="hormigon", capa=None):
    """Cubierta plana moderna: losa + peto perimetral. `nivel` es la cara superior
    de la losa (cota del suelo de la azotea)."""
    losa = forjado(contorno, nivel, espesor, material, capa, nombre="Cubierta_plana")
    puntos = _contorno_ccw(contorno)
    if peto > 0.01:
        for i in range(len(puntos)):
            muro(puntos[i], puntos[(i + 1) % len(puntos)], alto=peto, espesor=0.15,
                 nivel=nivel, material=material, capa=capa, nombre="Peto")
    return losa


def cubierta_dos_aguas(origen, ancho, fondo, nivel, pendiente=30, alero=0.5,
                       eje="x", material="teja", capa=None):
    """Cubierta a dos aguas sobre un rectángulo. `origen` es la esquina (x, y) del
    rectángulo de muros, `eje` la dirección de la cumbrera ("x" o "y"),
    `pendiente` en grados y `alero` el vuelo extra en todo el perímetro."""
    x, y = origen
    if eje == "y":
        largo, luz = fondo, ancho
    else:
        largo, luz = ancho, fondo
    semiluz = luz / 2 + alero
    altura = semiluz * math.tan(math.radians(pendiente))
    # Prisma triangular en coordenadas locales: cumbrera a lo largo de u
    u0, u1 = -alero, largo + alero
    verts_l = [
        (u0, -semiluz, 0), (u1, -semiluz, 0), (u1, semiluz, 0), (u0, semiluz, 0),
        (u0, 0, altura), (u1, 0, altura),
    ]
    caras = [(0, 1, 2, 3)[::-1], (0, 1, 5, 4), (2, 3, 4, 5), (1, 2, 5), (3, 0, 4)]
    if eje == "y":
        verts = [(x + ancho / 2 + v, y + u, w) for u, v, w in verts_l]
    else:
        verts = [(x + u, y + fondo / 2 + v, w) for u, v, w in verts_l]
    malla = bpy.data.meshes.new("Cubierta")
    malla.from_pydata(verts, [], caras)
    malla.update()
    obj = _nuevo_objeto("Cubierta", malla, capa, material)
    obj.location = (0, 0, nivel)
    print(f"✔ {obj.name}: dos aguas, {pendiente}° de pendiente, cumbrera a +{altura:.2f} m")
    return obj


# ------------------------------------------------- escaleras, barandillas, pilares

def escalera(origen, direccion="+x", ancho=1.0, alto_total=2.7, nivel=0.0,
             huella=0.28, material="hormigon", capa=None):
    """Tramo recto de escalera maciza desde `origen` (x, y) subiendo `alto_total` m.
    `direccion`: "+x", "-x", "+y" o "-y". Calcula sola el número de peldaños con
    contrahuella cómoda (~17,5 cm) e informa del desarrollo en planta."""
    n = max(2, round(alto_total / 0.175))
    contrahuella = alto_total / n
    cajas = [((i * huella, 0, 0), ((i + 1) * huella, ancho, (i + 1) * contrahuella)) for i in range(n)]
    angulos = {"+x": 0.0, "+y": math.pi / 2, "-x": math.pi, "-y": -math.pi / 2}
    obj = _nuevo_objeto("Escalera", _malla_cajas("Escalera", cajas), capa, material)
    _colocar(obj, origen[0], origen[1], nivel, angulos.get(direccion, 0.0))
    print(f"✔ {obj.name}: {n} peldaños de {contrahuella * 100:.1f} cm, "
          f"desarrollo {n * huella:.2f} m en dirección {direccion}")
    return obj


def barandilla(inicio, fin, nivel=0.0, alto=1.0, capa=None):
    """Barandilla moderna (postes + pasamanos + panel de vidrio) entre dos puntos (x, y)."""
    x0, y0 = inicio
    x1, y1 = fin
    largo = math.hypot(x1 - x0, y1 - y0)
    if largo < 0.05:
        print("✘ barandilla ignorada: demasiado corta")
        return None
    angulo = math.atan2(y1 - y0, x1 - x0)
    p = 0.04
    tramos = max(1, round(largo / 1.5))
    cajas = [((0, -0.03, alto - 0.04), (largo, 0.03, alto))]
    for i in range(tramos + 1):
        u = min(max(i * (largo / tramos) - p / 2, 0), largo - p)
        cajas.append(((u, -p / 2, 0), (u + p, p / 2, alto - 0.04)))
    postes = _nuevo_objeto("Barandilla", _malla_cajas("Barandilla", cajas), capa, "metal_negro")
    _colocar(postes, x0, y0, nivel, angulo)
    panel = _sin_sombra(_nuevo_objeto(
        "Barandilla_vidrio",
        _malla_cajas("Barandilla_vidrio", [((p, -0.006, 0.05), (largo - p, 0.006, alto - 0.06))]),
        capa, "vidrio",
    ))
    _colocar(panel, x0, y0, nivel, angulo)
    print(f"✔ {postes.name}: {largo:.2f} m")
    return postes


def rejilla_pilares(origen, num_x, num_y, sep_x, sep_y, alto, nivel=0.0,
                    lado=0.3, material="hormigon", capa=None):
    """Retícula estructural de pilares (num_x × num_y) desde la esquina `origen`,
    separados sep_x / sep_y metros. La base de todos queda en `nivel`."""
    x0, y0 = origen
    cajas = []
    for i in range(num_x):
        for j in range(num_y):
            cx, cy = i * sep_x, j * sep_y
            cajas.append(((cx - lado / 2, cy - lado / 2, 0), (cx + lado / 2, cy + lado / 2, alto)))
    obj = _nuevo_objeto("Pilares", _malla_cajas("Pilares", cajas), capa, material)
    _colocar(obj, x0, y0, nivel)
    print(f"✔ {obj.name}: {num_x * num_y} pilares de {alto:.2f} m")
    return obj


# ---------------------------------------------------------- entorno y render

def _malla_grid_ondulada(nombre, ancho, fondo, centro, amplitud, paso=1.5):
    """Rejilla de suelo con la cara superior desplazada por ondas suaves de baja
    frecuencia (relieve natural, sin picos). El borde se deja a cota 0 para que
    case con soleras/forjados. Malla abierta; un Solidify le da grosor luego."""
    cx, cy = centro
    nx = max(2, int(ancho / paso))
    ny = max(2, int(fondo / paso))
    x0, y0 = cx - ancho / 2, cy - fondo / 2
    verts, caras = [], []
    for j in range(ny + 1):
        for i in range(nx + 1):
            x = x0 + ancho * i / nx
            y = y0 + fondo * j / ny
            z = amplitud * (
                0.6 * math.sin(x * 0.11 + 1.3) * math.cos(y * 0.09 - 0.7)
                + 0.4 * math.sin(x * 0.05 - y * 0.06 + 2.1))
            if min(i, nx - i, j, ny - j) < 2:   # borde plano en cota 0
                z = 0.0
            verts.append((x, y, z))
    for j in range(ny):
        for i in range(nx):
            a = j * (nx + 1) + i
            caras.append((a, a + 1, a + nx + 2, a + nx + 1))
    malla = bpy.data.meshes.new(nombre)
    malla.from_pydata(verts, [], caras)
    malla.update()
    for cara in malla.polygons:
        cara.use_smooth = True
    return malla


def terreno(ancho=60, fondo=60, centro=(0, 0), material="cesped", capa=None,
            ondulacion=0.0):
    """Plano de suelo centrado en `centro`, con la cara superior en cota 0.
    `ondulacion` (m) da un relieve natural suave al terreno (0 = plano; 0.3-0.8
    para una parcela con desniveles ligeros). El borde se mantiene a cota 0 para
    casar con la solera y el hueco de una piscina se recorta igual de bien."""
    cx, cy = centro
    if not ondulacion:
        return caja("Terreno", (cx - ancho / 2, cy - fondo / 2, -0.1), (ancho, fondo, 0.1),
                    material=material, capa=capa)
    malla = _malla_grid_ondulada("Terreno", ancho, fondo, centro, ondulacion)
    obj = _nuevo_objeto("Terreno", malla, capa, material)
    solid = obj.modifiers.new("Terreno_grosor", "SOLIDIFY")
    if solid is not None:
        solid.thickness = 0.3
        solid.offset = -1.0
    print(f"✔ Terreno {ancho:.0f}×{fondo:.0f} m con ondulación de {ondulacion:.1f} m")
    return obj


def _quitar_objetos(prefijos, tipos):
    """Elimina objetos creados por el kit (p. ej. un Sol anterior) para no duplicarlos."""
    for obj in list(bpy.data.objects):
        if obj.type in tipos and any(obj.name.startswith(p) for p in prefijos):
            bpy.data.objects.remove(obj, do_unlink=True)


def _crear_sol(elevacion, azimut, fuerza, color=(1.0, 0.98, 0.94)):
    _quitar_objetos(("Sol",), ("LIGHT",))
    luz = bpy.data.lights.new("Sol", type="SUN")
    luz.energy = fuerza
    luz.color = color
    luz.use_shadow = True
    if hasattr(luz, "angle"):
        luz.angle = math.radians(0.53)  # tamaño real del disco solar: sombras nítidas pero no de laboratorio
    # Oclusión ambiental: sombras suaves en rincones e interiores (si el motor la soporta)
    eevee = getattr(bpy.context.scene, "eevee", None)
    if eevee is not None and hasattr(eevee, "use_gtao"):
        eevee.use_gtao = True
    obj = bpy.data.objects.new("Sol", luz)
    bpy.context.scene.collection.objects.link(obj)
    obj.rotation_euler = (math.radians(90 - elevacion), 0, math.radians(azimut))
    return obj


def sol(elevacion=35, azimut=200, fuerza=3.0):
    """Luz de sol con cielo básico. `elevacion` en grados sobre el horizonte,
    `azimut` giro en planta (200 ≈ luz cálida de tarde desde el suroeste).
    Para un cielo realista de verdad usa mejor cielo("dia"|"atardecer"|…)."""
    # Color más cálido cuanto más bajo esté el sol, como en la realidad
    t = max(0.0, min(1.0, elevacion / 40.0))
    color = (1.0, 0.55 + 0.43 * t, 0.30 + 0.64 * t)
    obj = _crear_sol(elevacion, azimut, fuerza, color)
    mundo = bpy.context.scene.world or bpy.data.worlds.new("Mundo")
    bpy.context.scene.world = mundo
    mundo.use_nodes = True
    fondo = next((n for n in mundo.node_tree.nodes if n.type == "BACKGROUND"), None)
    if fondo is not None:
        fondo.inputs["Color"].default_value = (0.55, 0.70, 0.90, 1.0)
        fondo.inputs["Strength"].default_value = 0.8
    print(f"✔ Sol a {elevacion}° de elevación y cielo añadidos")
    return obj


def camara(objetivo=(0, 0, 2), distancia=20, azimut=225, altura=6, lente=50,
           apertura=None):
    """Cámara mirando al punto `objetivo` desde `distancia` m, girada `azimut`
    grados en planta y a `altura` m del suelo. Queda como cámara activa y
    sustituye a la cámara anterior del kit (no se acumulan).
    Para vista peatonal usa altura=1.65; para vista general de un edificio,
    sube altura y distancia; para interiores usa lente=24 (gran angular),
    altura=1.5 y una distancia corta desde una esquina de la estancia.
    `apertura` (nº f, p. ej. 2.8) activa la profundidad de campo enfocada
    en el objetivo — bonito en interiores, innecesario en fachadas."""
    _quitar_objetos(("Camara",), ("CAMERA",))
    datos = bpy.data.cameras.new("Camara")
    datos.lens = lente
    obj = bpy.data.objects.new("Camara", datos)
    bpy.context.scene.collection.objects.link(obj)
    az = math.radians(azimut)
    pos = Vector((objetivo[0] + distancia * math.cos(az),
                  objetivo[1] + distancia * math.sin(az), altura))
    obj.location = pos
    direccion = Vector(objetivo) - pos
    obj.rotation_euler = direccion.to_track_quat("-Z", "Y").to_euler()
    if apertura:
        datos.dof.use_dof = True
        datos.dof.focus_distance = max(direccion.length, 0.5)
        datos.dof.aperture_fstop = apertura
    bpy.context.scene.camera = obj
    print(f"✔ Cámara activa mirando a {tuple(round(v, 1) for v in objetivo)}")
    return obj


# ------------------------------------------------ mobiliario e interiorismo
# Convención de los muebles: `origen` es la esquina izquierda de su parte
# trasera (la que se apoya contra la pared), el mueble crece hacia su frente,
# y `rotacion` gira en grados sobre ese origen (0 = frente hacia +Y).

def _suavizar(obj, radio):
    """Redondea las aristas con un bisel y suaviza el sombreado: sin esto los
    muebles parecen cajas duras de maqueta. `radio` en metros (0.01 madera,
    0.03-0.05 colchones, cojines y sanitarios)."""
    mod = obj.modifiers.new("Redondeo", "BEVEL")
    mod.width = radio
    mod.segments = 3
    mod.limit_method = "ANGLE"
    mod.angle_limit = math.radians(45)
    for cara in obj.data.polygons:
        cara.use_smooth = True
    return obj


def _pieza(nombre, capa, material, cajas=(), cilindros=(), esferas=(), suave=None):
    obj = _nuevo_objeto(nombre, _malla_piezas(nombre, cajas, cilindros, esferas), capa, material)
    if suave:
        _suavizar(obj, suave)
    return obj


def _situar(objetos, origen, nivel, rotacion):
    ang = math.radians(rotacion)
    for obj in objetos:
        if obj is not None:
            _colocar(obj, origen[0], origen[1], nivel, ang)


def cama(origen, ancho=1.5, largo=2.0, rotacion=0, nivel=0.0, capa=None,
         ropa="tela_azul", madera="madera_clara"):
    """Cama con cabecero, colchón, almohadas y colcha. `ancho` 0.9 individual,
    1.35/1.5/1.8 doble. El cabecero queda contra la línea del origen."""
    patas = [((x, y, 0), (x + 0.07, y + 0.07, 0.16))
             for x in (0.05, ancho - 0.12) for y in (0.05, largo - 0.12)]
    estructura = _pieza("Cama", capa, madera,
                        cajas=patas + [((0, 0, 0.16), (ancho, largo, 0.34)),
                                       ((0, -0.06, 0), (ancho, 0, 1.1))], suave=0.012)
    colchon = _pieza("Cama_colchon", capa, "blanco",
                     cajas=[((0.04, 0.04, 0.34), (ancho - 0.04, largo - 0.06, 0.55))],
                     suave=0.05)
    n_alm = 1 if ancho < 1.2 else 2
    paso = ancho / n_alm
    almohadas = _pieza("Cama_almohadas", capa, "crema",
                       cajas=[((i * paso + 0.09, 0.10, 0.56), ((i + 1) * paso - 0.09, 0.55, 0.68))
                              for i in range(n_alm)], suave=0.05)
    colcha = _pieza("Cama_colcha", capa, ropa,
                    cajas=[((0.01, largo * 0.33, 0.55), (ancho - 0.01, largo - 0.03, 0.62)),
                           ((0.01, largo * 0.33, 0.30), (ancho - 0.01, largo - 0.01, 0.56))],
                    suave=0.03)
    _situar([estructura, colchon, almohadas, colcha], origen, nivel, rotacion)
    print(f"✔ {estructura.name}: {ancho:.2f} × {largo:.2f} m")
    return estructura


def mesita_noche(origen, ancho=0.45, rotacion=0, nivel=0.0, capa=None, material="madera_clara"):
    """Mesita de noche con cajón."""
    cuerpo = _pieza("Mesita", capa, material,
                    cajas=[((0, 0, 0.05), (ancho, 0.4, 0.5)), ((0, 0, 0), (ancho, 0.05, 0.05))],
                    suave=0.008)
    frente = _pieza("Mesita_cajon", capa, "antracita",
                    cajas=[((ancho / 2 - 0.06, 0.40, 0.33), (ancho / 2 + 0.06, 0.42, 0.36))])
    _situar([cuerpo, frente], origen, nivel, rotacion)
    print(f"✔ {cuerpo.name}")
    return cuerpo


def mesa(origen, ancho=1.6, fondo=0.9, alto=0.75, rotacion=0, nivel=0.0,
         capa=None, material="madera"):
    """Mesa de patas en las esquinas (comedor, escritorio o, con alto=0.4, de centro)."""
    patas = [((x, y, 0), (x + 0.06, y + 0.06, alto - 0.04))
             for x in (0.08, ancho - 0.14) for y in (0.08, fondo - 0.14)]
    obj = _pieza("Mesa", capa, material,
                 cajas=patas + [((0, 0, alto - 0.04), (ancho, fondo, alto))], suave=0.01)
    _situar([obj], origen, nivel, rotacion)
    print(f"✔ {obj.name}: {ancho:.2f} × {fondo:.2f} × {alto:.2f} m")
    return obj


def silla(origen, rotacion=0, nivel=0.0, capa=None, material="madera", tapizado="tela_gris"):
    """Silla de 45 cm de asiento; el respaldo queda contra la línea del origen."""
    patas = [((x, 0.37, 0), (x + 0.04, 0.41, 0.42)) for x in (0.02, 0.39)]
    patas += [((x, 0.015, 0), (x + 0.04, 0.055, 0.90)) for x in (0.02, 0.39)]
    estructura = _pieza("Silla", capa, material,
                        cajas=patas + [((0.02, 0.015, 0.55), (0.43, 0.05, 0.88))],
                        suave=0.008)
    asiento = _pieza("Silla_asiento", capa, tapizado,
                     cajas=[((0.01, 0.03, 0.42), (0.44, 0.44, 0.47))], suave=0.018)
    _situar([estructura, asiento], origen, nivel, rotacion)
    return estructura


def sofa(origen, plazas=3, rotacion=0, nivel=0.0, capa=None, tela="tela_gris"):
    """Sofá de `plazas` asientos con brazos y cojines; espalda en la línea del origen."""
    ancho = 0.7 * plazas + 0.4
    patas = _pieza("Sofa_patas", capa, "metal_negro",
                   cilindros=[(x, y, 0, 0.06, 0.02)
                              for x in (0.10, ancho - 0.10) for y in (0.10, 0.75)])
    base = _pieza("Sofa", capa, tela, cajas=[
        ((0, 0, 0.06), (ancho, 0.85, 0.35)),
        ((0, 0, 0.06), (0.2, 0.85, 0.62)),
        ((ancho - 0.2, 0, 0.06), (ancho, 0.85, 0.62)),
        ((0, 0, 0.35), (ancho, 0.22, 0.80)),
    ], suave=0.04)
    cojines = []
    for i in range(plazas):
        x0 = 0.2 + i * 0.7
        cojines += [((x0 + 0.02, 0.24, 0.35), (x0 + 0.68, 0.83, 0.51)),
                    ((x0 + 0.02, 0.20, 0.50), (x0 + 0.68, 0.36, 0.79))]
    cojin_obj = _pieza("Sofa_cojines", capa, tela, cajas=cojines, suave=0.05)
    _situar([patas, base, cojin_obj], origen, nivel, rotacion)
    print(f"✔ {base.name}: {plazas} plaza(s), {ancho:.2f} m")
    return base


def sillon(origen, rotacion=0, nivel=0.0, capa=None, tela="tela_beige"):
    """Sillón de una plaza."""
    return sofa(origen, plazas=1, rotacion=rotacion, nivel=nivel, capa=capa, tela=tela)


def comedor(origen, comensales=6, rotacion=0, nivel=0.0, capa=None, material="madera"):
    """Mesa de comedor con las sillas ya colocadas para `comensales` personas."""
    por_lado = max(1, (comensales + 1) // 2)
    largo = max(1.4, 0.65 * por_lado + 0.35)
    fondo = 1.0
    mesa(origen, ancho=largo, fondo=fondo, rotacion=rotacion, nivel=nivel,
         capa=capa, material=material)
    ang = math.radians(rotacion)

    def _mundo(u, v):
        return (origen[0] + u * math.cos(ang) - v * math.sin(ang),
                origen[1] + u * math.sin(ang) + v * math.cos(ang))
    colocadas = 0
    for i in range(por_lado):
        cx = (i + 0.5) * largo / por_lado
        silla(_mundo(cx - 0.225, -0.50), rotacion=rotacion, nivel=nivel, capa=capa)
        colocadas += 1
        if colocadas < comensales:
            silla(_mundo(cx + 0.225, fondo + 0.50), rotacion=rotacion + 180,
                  nivel=nivel, capa=capa)
            colocadas += 1
    print(f"✔ Comedor: mesa de {largo:.2f} m y {colocadas} silla(s)")


def armario(origen, ancho=2.0, alto=2.2, fondo=0.6, rotacion=0, nivel=0.0,
            capa=None, material="madera_clara"):
    """Armario de puertas batientes; espalda en la línea del origen."""
    cuerpo = _pieza("Armario", capa, material,
                    cajas=[((0, 0, 0), (ancho, fondo - 0.02, alto))], suave=0.01)
    puertas = max(2, round(ancho / 0.6))
    detalles = []
    for i in range(1, puertas):
        u = i * ancho / puertas
        detalles.append(((u - 0.005, fondo - 0.02, 0.05), (u + 0.005, fondo, alto - 0.05)))
    for i in range(puertas):
        u = (i + 0.5) * ancho / puertas + (0.08 if i % 2 == 0 else -0.08)
        detalles.append(((u - 0.01, fondo - 0.01, 1.0), (u + 0.01, fondo + 0.02, 1.15)))
    frente = _pieza("Armario_puertas", capa, "antracita", cajas=detalles)
    _situar([cuerpo, frente], origen, nivel, rotacion)
    print(f"✔ {cuerpo.name}: {ancho:.2f} × {alto:.2f} m, {puertas} puertas")
    return cuerpo


def estanteria(origen, ancho=0.9, alto=1.8, fondo=0.35, baldas=4, rotacion=0,
               nivel=0.0, capa=None, material="madera"):
    """Estantería abierta con `baldas` alturas."""
    cajas = [((0, 0, 0), (0.025, fondo, alto)), ((ancho - 0.025, 0, 0), (ancho, fondo, alto)),
             ((0, 0, 0), (ancho, 0.02, alto))]
    for i in range(baldas + 1):
        z = i * (alto - 0.025) / baldas
        cajas.append(((0.025, 0, z), (ancho - 0.025, fondo, z + 0.025)))
    obj = _pieza("Estanteria", capa, material, cajas=cajas)
    _situar([obj], origen, nivel, rotacion)
    print(f"✔ {obj.name}: {ancho:.2f} × {alto:.2f} m")
    return obj


def cocina(origen, largo=3.0, rotacion=0, nivel=0.0, capa=None, con_altos=True,
           mueble="madera_clara", encimera="marmol"):
    """Bancada de cocina completa: muebles bajos, encimera con placa y fregadero
    y, opcionalmente, muebles altos. La espalda va contra la pared (línea del origen)."""
    bajos = _pieza("Cocina", capa, mueble,
                   cajas=[((0, 0.02, 0.1), (largo, 0.6, 0.85))], suave=0.006)
    zocalo = _pieza("Cocina_zocalo", capa, "antracita",
                    cajas=[((0.02, 0.06, 0), (largo - 0.02, 0.56, 0.1))])
    sobre = _pieza("Cocina_encimera", capa, encimera,
                   cajas=[((0, 0, 0.85), (largo, 0.63, 0.89))])
    placa = _pieza("Cocina_placa", capa, "negro_mate",
                   cajas=[((largo * 0.18, 0.08, 0.89), (largo * 0.18 + 0.6, 0.58, 0.895))])
    fregadero = _pieza("Cocina_fregadero", capa, "acero",
                       cajas=[((largo * 0.68, 0.10, 0.885), (largo * 0.68 + 0.5, 0.55, 0.89))],
                       cilindros=[(largo * 0.68 + 0.25, 0.10, 0.89, 1.15, 0.02)])
    piezas = [bajos, zocalo, sobre, placa, fregadero]
    if con_altos:
        piezas.append(_pieza("Cocina_altos", capa, mueble,
                             cajas=[((0, 0, 1.5), (largo, 0.35, 2.15))]))
    _situar(piezas, origen, nivel, rotacion)
    print(f"✔ {bajos.name}: bancada de {largo:.2f} m" + (" con muebles altos" if con_altos else ""))
    return bajos


def lavabo(origen, ancho=0.8, rotacion=0, nivel=0.0, capa=None):
    """Mueble de lavabo con seno, grifo y espejo (espalda contra la pared)."""
    mueble_l = _pieza("Lavabo_mueble", capa, "madera_clara",
                      cajas=[((0, 0.02, 0.25), (ancho, 0.45, 0.75))], suave=0.008)
    seno = _pieza("Lavabo", capa, "ceramica",
                  cajas=[((0, 0, 0.75), (ancho, 0.47, 0.87))], suave=0.025)
    grifo = _pieza("Lavabo_grifo", capa, "acero",
                   cilindros=[(ancho / 2, 0.08, 0.87, 1.12, 0.015)])
    espejo_l = _pieza("Lavabo_espejo", capa, "espejo",
                      cajas=[((0.05, 0, 1.05), (ancho - 0.05, 0.02, 1.75))])
    _situar([mueble_l, seno, grifo, espejo_l], origen, nivel, rotacion)
    print(f"✔ {seno.name}: {ancho:.2f} m con espejo")
    return seno


def inodoro(origen, rotacion=0, nivel=0.0, capa=None):
    """Inodoro con cisterna (espalda contra la pared; ocupa unos 0,5 × 0,7 m)."""
    obj = _pieza("Inodoro", capa, "ceramica",
                 cajas=[((0.05, 0.02, 0.15), (0.45, 0.2, 0.78)),
                        ((0.06, 0.16, 0.40), (0.44, 0.55, 0.46))],
                 cilindros=[(0.25, 0.36, 0, 0.40, 0.18)], suave=0.02)
    _situar([obj], origen, nivel, rotacion)
    print(f"✔ {obj.name}")
    return obj


def ducha(origen, ancho=0.9, fondo=0.9, rotacion=0, nivel=0.0, capa=None):
    """Ducha de obra: plato, mamparas de vidrio y columna (para un rincón: las
    dos caras sin mampara van contra las paredes)."""
    plato = _pieza("Ducha_plato", capa, "ceramica",
                   cajas=[((0, 0, 0), (ancho, fondo, 0.05))])
    columna = _pieza("Ducha_grifo", capa, "acero",
                     cilindros=[(ancho / 2, 0.05, 0.05, 2.0, 0.025)],
                     cajas=[((ancho / 2 - 0.12, 0.03, 1.95), (ancho / 2 + 0.12, 0.30, 1.99))])
    mamparas = _pieza("Ducha_mampara", capa, "vidrio",
                      cajas=[((ancho - 0.01, 0, 0.05), (ancho, fondo, 1.95)),
                             ((0, fondo - 0.01, 0.05), (ancho * 0.45, fondo, 1.95))])
    _situar([plato, columna, mamparas], origen, nivel, rotacion)
    print(f"✔ Ducha de {ancho:.2f} × {fondo:.2f} m")
    return plato


def banera(origen, largo=1.7, ancho=0.75, rotacion=0, nivel=0.0, capa=None):
    """Bañera exenta contra la pared (línea del origen)."""
    e = 0.09
    obj = _pieza("Banera", capa, "ceramica", cajas=[
        ((0, 0, 0), (largo, ancho, 0.12)),
        ((0, 0, 0.12), (e, ancho, 0.58)), ((largo - e, 0, 0.12), (largo, ancho, 0.58)),
        ((e, 0, 0.12), (largo - e, e, 0.58)), ((e, ancho - e, 0.12), (largo - e, ancho, 0.58)),
    ], suave=0.035)
    grifo = _pieza("Banera_grifo", capa, "acero",
                   cilindros=[(0.15, ancho / 2, 0.58, 0.85, 0.018)])
    _situar([obj, grifo], origen, nivel, rotacion)
    print(f"✔ {obj.name}: {largo:.2f} × {ancho:.2f} m")
    return obj


def alfombra(origen, ancho=2.5, fondo=1.8, rotacion=0, nivel=0.0, capa=None,
             material="tela_beige"):
    """Alfombra rectangular."""
    obj = _pieza("Alfombra", capa, material,
                 cajas=[((0, 0, 0), (ancho, fondo, 0.015))], suave=0.005)
    _situar([obj], origen, nivel, rotacion)
    print(f"✔ {obj.name}: {ancho:.2f} × {fondo:.2f} m")
    return obj


def cuadro(posicion, ancho=0.8, alto=0.6, altura_centro=1.5, rotacion=0, nivel=0.0,
           capa=None, color=(0.35, 0.42, 0.50)):
    """Cuadro colgado en una pared: `posicion` (x, y) es su esquina izquierda
    contra la pared y `rotacion` la orientación de esa pared."""
    z0 = altura_centro - alto / 2
    marco = _pieza("Cuadro_marco", capa, "antracita", cajas=[
        ((0, 0, z0), (0.04, 0.035, z0 + alto)), ((ancho - 0.04, 0, z0), (ancho, 0.035, z0 + alto)),
        ((0.04, 0, z0 + alto - 0.04), (ancho - 0.04, 0.035, z0 + alto)),
        ((0.04, 0, z0), (ancho - 0.04, 0.035, z0 + 0.04)),
    ])
    lienzo = _pieza("Cuadro", capa, material(f"Lienzo_{len(bpy.data.materials)}", color=color, rugosidad=0.9),
                    cajas=[((0.04, 0, z0 + 0.04), (ancho - 0.04, 0.02, z0 + alto - 0.04))])
    _situar([marco, lienzo], posicion, nivel, rotacion)
    return marco


def espejo_pared(posicion, ancho=0.6, alto=1.0, altura_centro=1.5, rotacion=0,
                 nivel=0.0, capa=None):
    """Espejo colgado en una pared (misma colocación que `cuadro`)."""
    z0 = altura_centro - alto / 2
    obj = _pieza("Espejo", capa, "espejo", cajas=[((0, 0, z0), (ancho, 0.025, z0 + alto))])
    _situar([obj], posicion, nivel, rotacion)
    return obj


def television(posicion, pulgadas=55, altura=1.0, rotacion=0, nivel=0.0, capa=None):
    """Televisor plano contra una pared o sobre un mueble; `posicion` es la
    esquina izquierda de su parte trasera."""
    diagonal = pulgadas * 0.0254
    ancho, alto = diagonal * 0.87, diagonal * 0.49
    obj = _pieza("Television", capa, "negro_mate",
                 cajas=[((0, 0, altura), (ancho, 0.045, altura + alto))])
    _situar([obj], posicion, nivel, rotacion)
    print(f"✔ {obj.name}: {pulgadas}\" ({ancho:.2f} m)")
    return obj


def planta_decorativa(centro, alto=1.3, nivel=0.0, capa=None):
    """Planta de interior en maceta; `centro` es el (x, y) de la maceta."""
    maceta = _pieza("Planta_maceta", capa, "antracita",
                    cilindros=[(0, 0, 0, alto * 0.24, 0.16)])
    tronco = _pieza("Planta_tronco", capa, "madera",
                    cilindros=[(0, 0, alto * 0.24, alto * 0.60, 0.022)])
    copa = _pieza("Planta", capa, "hoja",
                  esferas=[((0, 0, alto * 0.75), alto * 0.27),
                           ((0.12, 0.05, alto * 0.58), alto * 0.16),
                           ((-0.1, -0.08, alto * 0.66), alto * 0.14)])
    _situar([maceta, tronco, copa], centro, nivel, rotacion=0)
    return copa


# ------------------------------------------------------- iluminación interior

def _luz_puntual(nombre, posicion, fuerza, calida, radio=0.08):
    datos = bpy.data.lights.new(nombre, type="POINT")
    datos.energy = fuerza
    datos.shadow_soft_size = radio
    if calida:
        datos.color = (1.0, 0.83, 0.62)
    obj = bpy.data.objects.new(nombre, datos)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = posicion
    return obj


def luz_interior(posicion, fuerza=40, calida=True):
    """Luz puntual genérica en (x, y, z) — vatios aproximados en `fuerza`."""
    obj = _luz_puntual("Luz", posicion, fuerza, calida)
    print(f"✔ {obj.name} de {fuerza} W en {tuple(round(v, 1) for v in posicion)}")
    return obj


def lampara_colgante(posicion, altura_techo=2.7, descuelgue=0.9, nivel=0.0,
                     fuerza=70, capa=None):
    """Lámpara colgada del techo en (x, y); `altura_techo` es la altura libre de
    la estancia y `nivel` la cota de su suelo. Sobre una mesa, deja la pantalla
    a ~1,5 m del suelo (descuelgue = altura_techo - 1.5)."""
    techo = nivel + altura_techo
    z_pantalla = techo - descuelgue
    cuerpo = _pieza("Lampara", capa, "metal_negro",
                    cilindros=[(0, 0, z_pantalla, techo, 0.006),
                               (0, 0, z_pantalla - 0.24, z_pantalla, 0.17)])
    _situar([cuerpo], posicion, 0.0, rotacion=0)
    _luz_puntual("Lampara_luz", (posicion[0], posicion[1], z_pantalla - 0.30), fuerza, True)
    print(f"✔ {cuerpo.name} colgante a {z_pantalla - nivel:.2f} m del suelo")
    return cuerpo


def lampara_pie(centro, nivel=0.0, fuerza=50, capa=None):
    """Lámpara de pie (junto a un sofá o sillón); `centro` es su (x, y)."""
    base = _pieza("Lampara_pie", capa, "metal_negro",
                  cilindros=[(0, 0, 0, 0.03, 0.14), (0, 0, 0.03, 1.45, 0.015)])
    pantalla = _pieza("Lampara_pie_pantalla", capa, "tela_beige",
                      cilindros=[(0, 0, 1.45, 1.72, 0.19)])
    _situar([base, pantalla], centro, nivel, rotacion=0)
    _luz_puntual("Lampara_pie_luz", (centro[0], centro[1], nivel + 1.55), fuerza, True)
    return base


def _luz_foco(nombre, posicion, fuerza, color, apunta_arriba=False, apertura=100):
    datos = bpy.data.lights.new(nombre, type="SPOT")
    datos.energy = fuerza
    datos.color = color
    datos.spot_size = math.radians(apertura)
    datos.spot_blend = 0.9
    datos.shadow_soft_size = 0.05
    obj = bpy.data.objects.new(nombre, datos)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = posicion
    if apunta_arriba:
        obj.rotation_euler = (math.pi, 0.0, 0.0)  # los focos nacen apuntando hacia abajo (-Z)
    return obj


def foco_empotrado(posicion, altura_techo=2.7, nivel=0.0, fuerza=75, capa=None):
    """Downlight empotrado en el techo en (x, y): aro + punto de luz cálida.
    `altura_techo` es la altura libre de la estancia y `nivel` la cota de su
    suelo. En salones y cocinas modernos, colócalos en retícula cada 1,2-1,5 m:
    son los puntos de luz que se ven en el techo en los renders nocturnos."""
    z = nivel + altura_techo
    aro = _pieza("Foco", capa, "antracita", cilindros=[(0, 0, z - 0.02, z, 0.055)])
    emisivo = bpy.data.materials.get("Foco_emisivo") or material(
        "Foco_emisivo", color=(1.0, 0.84, 0.58), rugosidad=0.4, emision=6)
    disco = _nuevo_objeto(
        "Foco_disco", _malla_piezas("Foco_disco", cilindros=[(0, 0, z - 0.025, z - 0.014, 0.04)]),
        capa, emisivo)
    _situar([aro, disco], posicion, 0.0, 0)
    _luz_foco("Foco_luz", (posicion[0], posicion[1], z - 0.04), fuerza, (1.0, 0.83, 0.62))
    print(f"✔ Foco empotrado en ({posicion[0]:.1f}, {posicion[1]:.1f}), techo a {z:.2f} m")
    return aro


def foco_jardin(posicion, nivel=0.0, fuerza=40, capa=None):
    """Baliza de jardín que baña de luz cálida hacia ARRIBA lo que tenga encima
    o al lado (arbustos, árboles, fachadas). Clave en renders de atardecer/noche."""
    cuerpo = _pieza("Foco_jardin", capa, "antracita", cilindros=[(0, 0, 0, 0.14, 0.045)])
    _situar([cuerpo], posicion, nivel, 0)
    _luz_foco("Foco_jardin_luz", (posicion[0], posicion[1], nivel + 0.10),
              fuerza, (1.0, 0.86, 0.66), apunta_arriba=True, apertura=95)
    return cuerpo


# --------------------------------------------- estancias amuebladas completas
# Amueblan una estancia RECTANGULAR entera con reglas de interiorismo (piezas
# centradas, holguras de paso ≥ 0,6 m, decoración y luz). `origen` es la
# esquina INTERIOR suroeste de la estancia (cara vista de los muros), `ancho`
# va en X y `fondo` en Y; las paredes se nombran "S" (y mínima), "N", "E", "O".

_OPUESTA = {"S": "N", "N": "S", "E": "O", "O": "E"}


def _sobre_pared(origen, ancho, fondo, pared):
    """Sistema de coordenadas de una pared: devuelve (punto, rotacion, largo).
    `punto(u, d)` es el punto del suelo a distancia `u` de la esquina inicial de
    la pared y `d` hacia dentro de la estancia, tal que un mueble colocado ahí
    con `rotacion` ocupa [u, u + su_ancho] a lo largo de la pared."""
    x0, y0 = origen
    x1, y1 = x0 + ancho, y0 + fondo
    if pared == "S":
        return (lambda u, d=0.0: (x0 + u, y0 + d)), 0, ancho
    if pared == "E":
        return (lambda u, d=0.0: (x1 - d, y0 + u)), 90, fondo
    if pared == "N":
        return (lambda u, d=0.0: (x1 - u, y1 - d)), 180, ancho
    if pared == "O":
        return (lambda u, d=0.0: (x0 + d, y1 - u)), 270, fondo
    raise ValueError('pared debe ser "N", "S", "E" u "O"')


def dormitorio(origen, ancho, fondo, pared_cama="S", nivel=0.0, capa=None,
               ropa="tela_azul", madera="madera_clara", altura_techo=2.7):
    """Dormitorio completo: cama centrada en `pared_cama` (elige una pared SIN
    puerta ni ventana), mesitas si caben, armario, alfombra, cuadro y lámpara.
    Mínimo razonable: 2,6 × 2,6 m interiores."""
    punto, rot, largo = _sobre_pared(origen, ancho, fondo, pared_cama)
    profundo = fondo if pared_cama in ("S", "N") else ancho
    a_cama = 1.5 if largo >= 3.1 else (1.35 if largo >= 2.9 else 0.9)
    l_cama = 2.0 if profundo >= 3.0 else 1.9
    u = (largo - a_cama) / 2
    cama(punto(u), ancho=a_cama, largo=l_cama, rotacion=rot, nivel=nivel,
         capa=capa, ropa=ropa, madera=madera)
    if u >= 0.55:
        mesita_noche(punto(u - 0.50), rotacion=rot, nivel=nivel, capa=capa, material=madera)
        mesita_noche(punto(u + a_cama + 0.05), rotacion=rot, nivel=nivel, capa=capa, material=madera)
    cuadro(punto((largo - 0.9) / 2), ancho=0.9, alto=0.6, altura_centro=1.75,
           rotacion=rot, nivel=nivel, capa=capa)
    alfombra(punto(max(0.1, u - 0.6), l_cama - 1.2), ancho=min(a_cama + 1.2, largo - 0.2),
             fondo=1.7, rotacion=rot, nivel=nivel, capa=capa)
    # Armario: en la pared opuesta si queda pasillo ≥ 0,7 m; si no, en un lateral.
    if profundo - l_cama - 0.6 >= 0.7:
        punto2, rot2, largo2 = _sobre_pared(origen, ancho, fondo, _OPUESTA[pared_cama])
        a_arm = min(2.0, largo2 - 1.0)
        armario(punto2((largo2 - a_arm) / 2), ancho=a_arm, rotacion=rot2,
                nivel=nivel, capa=capa, material=madera)
    elif profundo - l_cama - 0.3 >= 1.0:
        lateral = {"S": "O", "N": "E", "E": "S", "O": "N"}[pared_cama]
        punto3, rot3, largo3 = _sobre_pared(origen, ancho, fondo, lateral)
        a_arm = min(1.6, largo3 - l_cama - 0.4)
        armario(punto3(largo3 - l_cama - 0.3 - a_arm), ancho=a_arm, rotacion=rot3,
                nivel=nivel, capa=capa, material=madera)
    else:
        print("· armario omitido: la estancia es demasiado pequeña")
    lampara_colgante((origen[0] + ancho / 2, origen[1] + fondo / 2),
                     altura_techo=altura_techo, nivel=nivel, capa=capa)
    print(f"✔ Dormitorio amueblado ({ancho:.1f} × {fondo:.1f} m, cama al {pared_cama})")


def salon(origen, ancho, fondo, pared_sofa="S", nivel=0.0, capa=None,
          tela="tela_gris", altura_techo=2.7):
    """Salón completo: sofá centrado en `pared_sofa`, alfombra y mesa de centro
    delante, mueble con televisor en la pared opuesta, sillón si hay sitio,
    estantería, planta, cuadro y lámparas. Mínimo razonable: 3,2 × 3,2 m."""
    punto, rot, largo = _sobre_pared(origen, ancho, fondo, pared_sofa)
    profundo = fondo if pared_sofa in ("S", "N") else ancho
    plazas = 3 if largo >= 3.4 else 2
    a_sofa = 0.7 * plazas + 0.4
    u = (largo - a_sofa) / 2
    sofa(punto(u, 0.06), plazas=plazas, rotacion=rot, nivel=nivel, capa=capa, tela=tela)
    cuadro(punto((largo - 1.2) / 2), ancho=1.2, alto=0.8, altura_centro=1.65,
           rotacion=rot, nivel=nivel, capa=capa)
    f_alf = min(2.0, profundo - 1.6)
    alfombra(punto(max(0.1, u - 0.3), 0.97), ancho=min(a_sofa + 0.6, largo - 0.2),
             fondo=f_alf, rotacion=rot, nivel=nivel, capa=capa, material="tela_beige")
    mesa(punto(u + a_sofa / 2 - 0.5, 1.30), ancho=1.0, fondo=0.55, alto=0.42,
         rotacion=rot, nivel=nivel, capa=capa)
    punto2, rot2, largo2 = _sobre_pared(origen, ancho, fondo, _OPUESTA[pared_sofa])
    mueble_tv = _pieza("Mueble_TV", capa, "madera", suave=0.008, cajas=[
        ((0, 0.02, 0.12), (1.8, 0.42, 0.45)),
        ((0.10, 0.06, 0), (0.16, 0.38, 0.12)), ((1.64, 0.06, 0), (1.70, 0.38, 0.12)),
    ])
    _situar([mueble_tv], punto2((largo2 - 1.8) / 2), nivel, rot2)
    pulgadas = 55 if profundo >= 3.4 else 43
    a_tv = pulgadas * 0.0254 * 0.87
    television(punto2((largo2 - a_tv) / 2, 0.06), pulgadas=pulgadas, altura=0.55,
               rotacion=rot2, nivel=nivel, capa=capa)
    if u >= 1.15:  # sillón en L a la izquierda del sofá, mirando a lo largo de la pared
        sillon(punto(u - 0.95, 2.15), rotacion=rot + 270, nivel=nivel, capa=capa)
    if largo - u - a_sofa >= 0.7:
        lampara_pie(punto(u + a_sofa + 0.35, 0.45), nivel=nivel, capa=capa)
    planta_decorativa(punto2(0.45, 0.45), nivel=nivel, capa=capa)
    lampara_colgante((origen[0] + ancho / 2, origen[1] + fondo / 2),
                     altura_techo=altura_techo, nivel=nivel, capa=capa)
    print(f"✔ Salón amueblado ({ancho:.1f} × {fondo:.1f} m, sofá al {pared_sofa})")


def bano(origen, ancho, fondo, pared_aparatos="S", nivel=0.0, capa=None,
         con_ducha=True, altura_techo=2.7):
    """Baño completo: ducha en la esquina inicial de `pared_aparatos`, inodoro y
    lavabo con espejo en línea, y foco de techo. Mínimo razonable: 1,6 × 1,5 m."""
    punto, rot, largo = _sobre_pared(origen, ancho, fondo, pared_aparatos)
    profundo = fondo if pared_aparatos in ("S", "N") else ancho
    u = 0.0
    if con_ducha and largo >= 2.3 and profundo >= 1.5:
        ducha(punto(0), rotacion=rot, nivel=nivel, capa=capa)
        u = 1.05
    elif con_ducha:
        print("· ducha omitida: no cabe con holgura (necesita pared ≥ 2,3 m)")
    inodoro(punto(u + 0.05), rotacion=rot, nivel=nivel, capa=capa)
    a_lav = min(0.9, largo - u - 0.75)
    if a_lav >= 0.5:
        lavabo(punto(u + 0.65), ancho=a_lav, rotacion=rot, nivel=nivel, capa=capa)
    else:
        punto2, rot2, largo2 = _sobre_pared(origen, ancho, fondo, _OPUESTA[pared_aparatos])
        lavabo(punto2((largo2 - 0.8) / 2), rotacion=rot2, nivel=nivel, capa=capa)
    foco_empotrado((origen[0] + ancho / 2, origen[1] + fondo / 2),
                   altura_techo=altura_techo, nivel=nivel, capa=capa)
    print(f"✔ Baño amueblado ({ancho:.1f} × {fondo:.1f} m)")


# ------------------------------------------------- exterior, paisaje y piscina

def piscina(origen, ancho=8.0, fondo=4.0, profundidad=1.5, borde=0.6, nivel=0.0,
            rotacion=0, luces=2, capa=None, material_borde="pavimento"):
    """Piscina enterrada con vaso alicatado, agua realista, coronación de borde
    y luces sumergidas. `origen` es la esquina (x, y) de la lámina de agua y
    `ancho`/`fondo` sus medidas en planta. Si existe un objeto "Terreno", le
    recorta sola el hueco. Combina de maravilla con cielo("atardecer")."""
    x0, y0 = origen
    e = 0.12          # espesor de las paredes del vaso
    b = max(borde, 0.15)
    z_fondo = -profundidad

    coronacion = _pieza("Piscina_borde", capa, material_borde, cajas=[
        ((-b, -b, -0.02), (ancho + b, 0, 0.04)),
        ((-b, fondo, -0.02), (ancho + b, fondo + b, 0.04)),
        ((-b, 0, -0.02), (0, fondo, 0.04)),
        ((ancho, 0, -0.02), (ancho + b, fondo, 0.04)),
    ])
    azulejo = bpy.data.materials.get("Piscina_azulejo") or material(
        "Piscina_azulejo", color=(0.42, 0.68, 0.72), rugosidad=0.15,
        textura="baldosa", escala=8)
    vaso = _nuevo_objeto("Piscina_vaso", _malla_cajas("Piscina_vaso", [
        ((-e, -e, z_fondo - e), (ancho + e, fondo + e, z_fondo)),
        ((-e, -e, z_fondo), (0, fondo + e, 0.0)),
        ((ancho, -e, z_fondo), (ancho + e, fondo + e, 0.0)),
        ((0, -e, z_fondo), (ancho, 0, 0.0)),
        ((0, fondo, z_fondo), (ancho, fondo + e, 0.0)),
    ]), capa, azulejo)
    agua_obj = _sin_sombra(_nuevo_objeto("Piscina_agua", _malla_cajas(
        "Piscina_agua", [((0.005, 0.005, z_fondo + 0.05), (ancho - 0.005, fondo - 0.005, -0.15))]),
        capa, "agua"))
    _situar([coronacion, vaso, agua_obj], origen, nivel, rotacion)

    ang = math.radians(rotacion)
    convertir = _local_a_mundo(x0, y0, ang)
    for i in range(max(0, int(luces))):
        u = (i + 1) * ancho / (int(luces) + 1)
        wx, wy = convertir(u, 0.35)
        foco = _luz_puntual("Piscina_luz", (wx, wy, nivel - 0.45), 90, calida=False, radio=0.06)
        foco.data.color = (0.72, 0.90, 1.0)

    cortador = _nuevo_objeto("Piscina_corte", _malla_cajas("Piscina_corte", [
        ((-e - 0.01, -e - 0.01, z_fondo - 0.3), (ancho + e + 0.01, fondo + e + 0.01, 0.5))]), None, None)
    _colocar(cortador, x0, y0, nivel, ang)
    cortador.display_type = "WIRE"
    cortador.hide_render = True
    terreno_obj = bpy.data.objects.get("Terreno")
    if terreno_obj is not None:
        modificador = terreno_obj.modifiers.new("Piscina_hueco", "BOOLEAN")
        if modificador is not None:
            modificador.operation = "DIFFERENCE"
            modificador.object = cortador
        recorte = " (hueco recortado en el terreno)"
    else:
        recorte = " (no hay 'Terreno': créalo antes si quieres el hueco integrado)"
    print(f"✔ Piscina de {ancho:.1f}×{fondo:.1f} m, prof. {profundidad:.1f} m, "
          f"{int(luces)} luz(es) sumergida(s){recorte}")
    return vaso


# Variantes de verde para que una masa de árboles no parezca de clones.
_VEG_VARIANTES = [
    (0.045, 0.085, 0.035),   # verde oscuro estándar
    (0.060, 0.100, 0.030),   # más claro y seco
    (0.030, 0.070, 0.050),   # más frío/azulado
]


def _mat_vegetacion(variante=0):
    """Follaje de exterior: oscuro y grumoso (las copas reales se auto-sombrean
    y en las fotos leen casi en silueta, no verde brillante). `variante` (0-2)
    elige un tono de verde distinto para dar variedad entre plantas."""
    variante = int(variante) % len(_VEG_VARIANTES)
    nombre = "Vegetacion" if variante == 0 else f"Vegetacion{variante}"
    return bpy.data.materials.get(nombre) or material(
        nombre, color=_VEG_VARIANTES[variante], rugosidad=0.95, textura="tela", escala=5)


def _mat_corteza():
    return bpy.data.materials.get("Corteza") or material(
        "Corteza", color=(0.16, 0.12, 0.09), rugosidad=0.95, textura="madera", escala=2)


def arbol(centro, alto=6.0, tipo="frondoso", nivel=0.0, capa=None, semilla=None):
    """Árbol de jardín en (x, y): "frondoso" (copa irregular) o "cipres"
    (columnar, para alinear junto a muros). Cada árbol varía solo su forma y su
    tono de verde (según `semilla`, o su posición si no la das) para que una
    hilera o un bosque no parezcan de clones. Los árboles enmarcan la casa y
    llenan el fondo del encuadre: sin ellos los renders parecen maquetas."""
    rnd = random.Random(semilla if semilla is not None
                        else f"{centro[0]:.2f},{centro[1]:.2f},{tipo}")
    def jit(v, frac):
        return v * (1.0 + rnd.uniform(-frac, frac))
    if tipo == "cipres":
        r = alto * 0.14
        esferas = [((0, 0, alto * f), r * (1.08 - f * 0.8))
                   for f in (0.18, 0.34, 0.50, 0.66, 0.82, 0.94)]
        alto_tronco = alto * 0.14
    else:
        copa = alto * 0.55
        rc = copa / 2
        zc = alto - rc
        base = [((0, 0, zc), rc),
                ((rc * 0.70, rc * 0.30, zc - rc * 0.45), rc * 0.62),
                ((-rc * 0.60, rc * 0.45, zc - rc * 0.35), rc * 0.58),
                ((rc * 0.20, -rc * 0.65, zc - rc * 0.50), rc * 0.55),
                ((-rc * 0.35, -rc * 0.40, zc + rc * 0.30), rc * 0.50),
                ((rc * 0.45, rc * 0.10, zc + rc * 0.42), rc * 0.45)]
        # Se altera la posición y el tamaño de cada masa de copa, no su altura.
        esferas = [((jit(x, 0.18), jit(y, 0.18), z), jit(rad, 0.12))
                   for (x, y, z), rad in base]
        alto_tronco = alto - copa * 0.75
    tronco = _pieza("Arbol_tronco", capa, _mat_corteza(),
                    cilindros=[(0, 0, 0, alto_tronco, max(0.07, alto * 0.028))])
    copa_obj = _pieza("Arbol", capa, _mat_vegetacion(rnd.randint(0, 2)), esferas=esferas)
    _situar([tronco, copa_obj], centro, nivel, 0)
    print(f"✔ {copa_obj.name}: {tipo} de {alto:.1f} m")
    return copa_obj


def arbusto(centro, alto=0.7, nivel=0.0, capa=None, semilla=None):
    """Arbusto redondeado en (x, y); en grupos de 2-3 junto a fachadas y muros
    (ponles un foco_jardin delante para el efecto de la foto nocturna). Varía
    solo su forma y verde según `semilla` (o su posición) para no clonarse."""
    rnd = random.Random(semilla if semilla is not None
                        else f"{centro[0]:.2f},{centro[1]:.2f}")
    obj = _pieza("Arbusto", capa, _mat_vegetacion(rnd.randint(0, 2)), esferas=[
        ((0, 0, alto * 0.55), alto * 0.50),
        ((alto * rnd.uniform(0.28, 0.46), alto * 0.15, alto * 0.42), alto * 0.36),
        ((-alto * rnd.uniform(0.24, 0.40), -alto * 0.20, alto * 0.46), alto * 0.33),
    ])
    _situar([obj], centro, nivel, 0)
    return obj


def seto(inicio, fin, alto=1.2, espesor=0.5, nivel=0.0, capa=None):
    """Seto vegetal recto entre dos puntos (x, y): cierra parcelas con verde."""
    x0, y0 = inicio
    x1, y1 = fin
    largo = math.hypot(x1 - x0, y1 - y0)
    if largo < 0.05:
        print("✘ seto ignorado: demasiado corto")
        return None
    obj = _nuevo_objeto("Seto", _malla_cajas(
        "Seto", [((0, -espesor / 2, 0), (largo, espesor / 2, alto))]), capa, _mat_vegetacion())
    _colocar(obj, x0, y0, nivel, math.atan2(y1 - y0, x1 - x0))
    print(f"✔ {obj.name}: {largo:.1f} m")
    return obj


def tumbona(origen, rotacion=0, nivel=0.0, capa=None, tela="tela_beige"):
    """Tumbona de piscina (0,7 × 1,95 m); el respaldo queda hacia el origen."""
    marco = _pieza("Tumbona", capa, "antracita", cajas=[
        ((0.03, 0.05, 0.18), (0.68, 1.95, 0.26)),
        ((0.05, 0.10, 0), (0.10, 0.16, 0.18)), ((0.61, 0.10, 0), (0.66, 0.16, 0.18)),
        ((0.05, 1.80, 0), (0.10, 1.86, 0.18)), ((0.61, 1.80, 0), (0.66, 1.86, 0.18)),
    ])
    escalones = [((0.05, 0.62, 0.26), (0.66, 1.93, 0.34))]
    for i in range(4):
        escalones.append(((0.05, 0.62 - (i + 1) * 0.155, 0.26 + i * 0.09),
                          (0.66, 0.62 - i * 0.155, 0.26 + (i + 1) * 0.09 + 0.02)))
    colchoneta = _pieza("Tumbona_colchoneta", capa, tela, cajas=escalones, suave=0.02)
    _situar([marco, colchoneta], origen, nivel, rotacion)
    print(f"✔ {marco.name}")
    return marco


def barbacoa(centro, nivel=0.0, capa=None):
    """Barbacoa de carbón tipo kettle en (x, y), para terrazas y jardines."""
    patas = [(math.cos(a) * 0.17, math.sin(a) * 0.17)
             for a in (math.pi / 2, math.pi * 7 / 6, math.pi * 11 / 6)]
    cuerpo = _pieza("Barbacoa", capa, "negro_mate",
                    cilindros=[(px, py, 0, 0.52, 0.015) for px, py in patas]
                    + [(0, 0, 0.52, 0.70, 0.27)],
                    esferas=[((0, 0, 0.70), 0.26)])
    pomo = _pieza("Barbacoa_pomo", capa, "acero", cilindros=[(0, 0, 0.94, 1.01, 0.02)])
    _situar([cuerpo, pomo], centro, nivel, 0)
    return cuerpo


# ------------------------------------------- fachada, parcela y paisajismo

def celosia(inicio, fin, alto=2.5, nivel=0.0, orientacion="vertical",
            separacion=0.12, espesor=0.04, capa=None, material="madera"):
    """Celosía / lamas de parasol entre dos puntos (x, y): tira de listones que
    tamiza el sol y da textura a la fachada (delante de ventanales, en porches o
    como valla-pantalla). `orientacion`: "vertical" (listones de pie) u
    "horizontal" (tumbados); `separacion` es la luz entre listones."""
    x0, y0 = inicio
    x1, y1 = fin
    largo = math.hypot(x1 - x0, y1 - y0)
    if largo < 0.05:
        print("✘ celosia ignorada: demasiado corta")
        return None
    lama = max(0.02, espesor)
    paso = lama + max(0.02, separacion)
    cajas = []
    if orientacion == "horizontal":
        for i in range(max(2, int(alto / paso))):
            z = i * paso
            cajas.append(((0, -lama / 2, z), (largo, lama / 2, z + lama)))
    else:
        for i in range(max(2, int(largo / paso))):
            x = i * paso
            cajas.append(((x, -lama / 2, 0), (x + lama, lama / 2, alto)))
    obj = _nuevo_objeto("Celosia", _malla_cajas("Celosia", cajas), capa, material)
    _colocar(obj, x0, y0, nivel, math.atan2(y1 - y0, x1 - x0))
    print(f"✔ {obj.name}: {largo:.1f} m, {len(cajas)} lamas {orientacion}es")
    return obj


def pergola(origen, ancho=4.0, fondo=3.0, altura=2.4, rotacion=0, nivel=0.0,
            capa=None, material="madera", lamas=True):
    """Pérgola de vigas sobre 4 pilares: sombra de terrazas, porches y accesos.
    `origen` es la esquina (x, y); ocupa `ancho`×`fondo` y `altura` de alto."""
    p = 0.10
    z = altura
    cajas = [((cx - p, cy - p, 0), (cx + p, cy + p, z))
             for cx, cy in ((0, 0), (ancho, 0), (0, fondo), (ancho, fondo))]
    cajas += [((0, -p, z - 0.12), (ancho, p, z)),
              ((0, fondo - p, z - 0.12), (ancho, fondo + p, z)),
              ((-p, 0, z - 0.12), (p, fondo, z)),
              ((ancho - p, 0, z - 0.12), (ancho + p, fondo, z))]
    if lamas:
        n = max(2, int(ancho / 0.35))
        for i in range(n + 1):
            x = min(i * 0.35, ancho)
            cajas.append(((x - 0.03, 0, z), (x + 0.03, fondo, z + 0.10)))
    obj = _nuevo_objeto("Pergola", _malla_cajas("Pergola", cajas), capa, material)
    _colocar(obj, origen[0], origen[1], nivel, math.radians(rotacion))
    print(f"✔ {obj.name}: {ancho:.1f}×{fondo:.1f} m, alto {altura:.1f} m")
    return obj


def valla(inicio, fin, alto=1.6, nivel=0.0, tipo="tablas", capa=None, material="madera"):
    """Valla/cerca recta entre dos puntos (x, y) para cerrar una parcela.
    tipo: "tablas" (listones verticales juntos, opaca) o "postes" (postes con
    dos travesaños, ligera)."""
    x0, y0 = inicio
    x1, y1 = fin
    largo = math.hypot(x1 - x0, y1 - y0)
    if largo < 0.05:
        print("✘ valla ignorada: demasiado corta")
        return None
    n_post = max(2, int(largo / 2.0) + 1)
    cajas = [((min(i * largo / (n_post - 1), largo) - 0.06, -0.06, 0),
              (min(i * largo / (n_post - 1), largo) + 0.06, 0.06, alto))
             for i in range(n_post)]
    if tipo == "tablas":
        for i in range(max(2, int(largo / 0.16))):
            x = i * 0.16
            cajas.append(((x, -0.02, 0.05), (x + 0.11, 0.02, alto - 0.05)))
    else:
        for zf in (alto * 0.35, alto * 0.75):
            cajas.append(((0, -0.03, zf - 0.04), (largo, 0.03, zf + 0.04)))
    obj = _nuevo_objeto("Valla", _malla_cajas("Valla", cajas), capa, material)
    _colocar(obj, x0, y0, nivel, math.atan2(y1 - y0, x1 - x0))
    print(f"✔ {obj.name}: {largo:.1f} m ({tipo})")
    return obj


def camino(inicio, fin, ancho=1.2, nivel=0.0, material="pavimento", capa=None):
    """Camino/sendero recto entre dos puntos (x, y): accesos y senderos de jardín.
    Se apoya sobre el terreno (cota 0)."""
    x0, y0 = inicio
    x1, y1 = fin
    largo = math.hypot(x1 - x0, y1 - y0)
    if largo < 0.05:
        print("✘ camino ignorado: demasiado corto")
        return None
    obj = _nuevo_objeto("Camino", _malla_cajas(
        "Camino", [((0, -ancho / 2, 0), (largo, ancho / 2, 0.04))]), capa, material)
    _colocar(obj, x0, y0, nivel, math.atan2(y1 - y0, x1 - x0))
    print(f"✔ {obj.name}: {largo:.1f} × {ancho:.1f} m")
    return obj


def palmera(centro, alto=7.0, nivel=0.0, capa=None):
    """Palmera en (x, y): tronco esbelto y corona de hojas. Da carácter
    mediterráneo/tropical a jardines y piscinas."""
    seg = 6
    cilindros = [(0, 0, alto * i / seg, alto * (i + 1) / seg,
                  max(0.06, 0.16 * (1 - i / (seg * 1.6)))) for i in range(seg)]
    tronco = _pieza("Palmera_tronco", capa, _mat_corteza(), cilindros=cilindros)
    corona = [((0, 0, alto + 0.1), alto * 0.10)]
    corona += [((math.cos(2 * math.pi * k / 7) * alto * 0.28,
                 math.sin(2 * math.pi * k / 7) * alto * 0.28, alto - 0.15), alto * 0.11)
               for k in range(7)]
    copa = _pieza("Palmera", capa, _mat_vegetacion(1), esferas=corona)
    _situar([tronco, copa], centro, nivel, 0)
    print(f"✔ {copa.name}: palmera de {alto:.1f} m")
    return copa


def farola(posicion, alto=4.0, nivel=0.0, fuerza=120, capa=None):
    """Farola de exterior en (x, y): poste con luminaria y luz cálida. Para
    accesos, caminos y calles; se enciende de noche/atardecer."""
    poste = _pieza("Farola", capa, "metal_negro",
                   cilindros=[(0, 0, 0, alto, 0.05)],
                   cajas=[((-0.14, -0.14, alto), (0.14, 0.14, alto + 0.18))])
    emisivo = bpy.data.materials.get("Farola_luz_mat") or material(
        "Farola_luz_mat", color=(1.0, 0.86, 0.6), rugosidad=0.4, emision=8)
    farol = _nuevo_objeto("Farola_farol", _malla_piezas(
        "Farola_farol", cajas=[((-0.11, -0.11, alto + 0.01), (0.11, 0.11, alto + 0.15))]),
        capa, emisivo)
    _situar([poste, farol], posicion, nivel, 0)
    _luz_puntual("Farola_luz", (posicion[0], posicion[1], nivel + alto + 0.05),
                 fuerza, True, radio=0.12)
    print(f"✔ {poste.name}: farola de {alto:.1f} m")
    return poste


def coche(origen, rotacion=0, nivel=0.0, color=(0.15, 0.16, 0.18), capa=None):
    """Coche sencillo aparcado, para dar escala y realismo al exterior. `origen`
    es la esquina trasera izquierda; mide ~4,4 × 1,8 m."""
    largo, ancho = 4.4, 1.8
    pintura = material(f"Coche_{len(bpy.data.materials)}", color=color,
                       rugosidad=0.25, metalico=0.6)
    cuerpo = _pieza("Coche", capa, pintura, cajas=[
        ((0.3, 0, 0.35), (largo - 0.3, ancho, 0.85)),
        ((1.2, 0.12, 0.82), (largo - 1.3, ancho - 0.12, 1.35)),
    ], suave=0.06)
    lunas = _pieza("Coche_lunas", capa, "vidrio",
                   cajas=[((1.25, 0.10, 0.85), (largo - 1.35, ancho - 0.10, 1.30))])
    ruedas = [((rx, ry, 0.0), (rx + 0.62, ry + 0.28, 0.52))
              for rx in (0.55, largo - 1.17) for ry in (-0.02, ancho - 0.26)]
    llantas = _pieza("Coche_ruedas", capa, "negro_mate", cajas=ruedas)
    _situar([cuerpo, lunas, llantas], origen, nivel, rotacion)
    print(f"✔ {cuerpo.name}: coche {largo:.1f} m")
    return cuerpo


def revisar_escena():
    """Control de calidad: revisa la escena y avisa de los fallos típicos de un
    render (sin cámara, sin luz cuando hay mobiliario, objetos sin material).
    Llámala antes de render() o de dar por terminado un proyecto y corrige lo
    que señale. Recuerda además poner cielo(...) para la luz ambiente."""
    objetos = list(bpy.data.objects)
    camaras = [o for o in objetos if o.type == "CAMERA"]
    luces = [o for o in objetos if o.type == "LIGHT"]
    mallas = [o for o in objetos if o.type == "MESH" and not o.hide_render
              and o.display_type != "WIRE"]
    muebles = ("Cama", "Sofa", "Sillon", "Mesa", "Cocina", "Comedor", "Armario",
               "Estanteria", "Lavabo", "Inodoro", "Ducha", "Banera", "Silla")
    hay_interior = any(o.name.startswith(muebles) for o in mallas)
    sin_material = [o.name for o in mallas
                    if not o.data.materials or all(m is None for m in o.data.materials)]
    avisos = []
    if not camaras:
        avisos.append("No hay cámara: añade camara(...) antes de render().")
    if not luces:
        avisos.append("Hay mobiliario pero NINGUNA luz: las estancias saldrán negras. "
                      "Ilumina cada estancia con techo." if hay_interior
                      else "No hay luces en la escena.")
    if sin_material:
        muestra = ", ".join(sin_material[:8]) + (" …" if len(sin_material) > 8 else "")
        avisos.append(f"{len(sin_material)} objeto(s) sin material (saldrán grises): {muestra}")
    print(f"🔎 Escena: {len(mallas)} objetos visibles, {len(luces)} luces, "
          f"{len(camaras)} cámara(s), {len(bpy.data.materials)} materiales.")
    if avisos:
        print("Puntos a corregir para un buen render:")
        for a in avisos:
            print("  • " + a)
    else:
        print("✔ Sin fallos críticos detectados: lista para renderizar.")
    return "revisado"


# --------------------------------------------------- cielo físico y render

# Presets de iluminación natural: elevación del sol, bruma (dust del cielo
# físico), intensidad del ambiente y color/fuerza del sol.
_MOMENTOS = {
    "amanecer":  {"elev": 9,   "bruma": 2.5, "ambiente": 0.5,  "sol": 2.5, "color": (1.0, 0.72, 0.50), "plano": (0.78, 0.66, 0.58)},
    "dia":       {"elev": 55,  "bruma": 1.0, "ambiente": 1.0,  "sol": 4.0, "color": (1.0, 0.98, 0.94), "plano": (0.55, 0.70, 0.90)},
    "tarde":     {"elev": 28,  "bruma": 1.8, "ambiente": 0.75, "sol": 3.2, "color": (1.0, 0.88, 0.70), "plano": (0.60, 0.68, 0.85)},
    "atardecer": {"elev": 4,   "bruma": 4.5, "ambiente": 0.22, "sol": 0.9, "color": (1.0, 0.55, 0.30), "plano": (0.45, 0.42, 0.52)},
    "anochecer": {"elev": -5,  "bruma": 3.0, "ambiente": 0.15, "sol": 0.0, "color": (0.70, 0.78, 1.0), "plano": (0.16, 0.20, 0.34)},
    "noche":     {"elev": -14, "bruma": 1.0, "ambiente": 0.05, "sol": 0.0, "color": (0.65, 0.75, 1.0), "plano": (0.015, 0.03, 0.07)},
}


def cielo(momento="dia", azimut=200, intensidad=None):
    """Cielo físico realista + sol sincronizado, según el momento del día:
    "amanecer", "dia", "tarde", "atardecer" (hora dorada/azul, la más
    fotogénica: interiores encendidos brillando tras el vidrio), "anochecer"
    o "noche". Sustituye al sol/cielo anterior, así que puedes cambiar de
    momento las veces que quieras antes de renderizar."""
    m = _MOMENTOS.get(momento)
    if m is None:
        print(f"✘ momento '{momento}' no reconocido (usa {', '.join(_MOMENTOS)}); aplico 'dia'")
        m = _MOMENTOS["dia"]
    mundo = bpy.context.scene.world or bpy.data.worlds.new("Mundo")
    bpy.context.scene.world = mundo
    mundo.use_nodes = True
    nt = mundo.node_tree
    nt.nodes.clear()
    salida = nt.nodes.new("ShaderNodeOutputWorld")
    fondo = nt.nodes.new("ShaderNodeBackground")
    nt.links.new(fondo.outputs["Background"], salida.inputs["Surface"])
    fondo.inputs["Strength"].default_value = m["ambiente"] if intensidad is None else intensidad
    try:
        tex = nt.nodes.new("ShaderNodeTexSky")
        for attr, valor in (("sky_type", "NISHITA"),
                            ("sun_disc", False),
                            ("sun_elevation", math.radians(m["elev"])),
                            ("sun_rotation", math.radians(90 - azimut)),
                            ("altitude", 0.0),
                            ("air_density", 1.0),
                            ("dust_density", m["bruma"])):
            if hasattr(tex, attr):
                try:
                    setattr(tex, attr, valor)
                except Exception:
                    pass
        nt.links.new(tex.outputs["Color"], fondo.inputs["Color"])
    except Exception:
        fondo.inputs["Color"].default_value = (*m["plano"], 1.0)

    if m["sol"] > 0:
        _crear_sol(m["elev"], azimut, m["sol"], m["color"])
    else:
        # Sin sol directo: una "luna" tenue y fría para que haya sombras suaves
        _crear_sol(35, azimut + 130, 0.05, m["color"])
    print(f"✔ Cielo de {momento} (sol a {m['elev']}°)")
    return mundo


CARPETA_RENDERS = Path.home() / ".buildai" / "renders"

_CALIDADES = {
    "borrador": {"resolucion": (1280, 720), "muestras": 48, "umbral": 0.10},
    "media":    {"resolucion": (1600, 900), "muestras": 160, "umbral": 0.03},
    "alta":     {"resolucion": (1920, 1080), "muestras": 448, "umbral": 0.01},
}


def _fijar(objeto, atributos, valor):
    """Asigna el primer atributo que exista (los nombres cambian entre versiones)."""
    for nombre in atributos:
        if hasattr(objeto, nombre):
            try:
                setattr(objeto, nombre, valor)
                return True
            except Exception:
                continue
    return False


def _activar_gpu(escena):
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        for tipo in ("OPTIX", "CUDA", "HIP", "ONEAPI", "METAL"):
            try:
                prefs.compute_device_type = tipo
            except Exception:
                continue
            for refresco in ("refresh_devices", "get_devices"):
                if hasattr(prefs, refresco):
                    try:
                        getattr(prefs, refresco)()
                        break
                    except Exception:
                        continue
            if any(d.type != "CPU" for d in prefs.devices):
                for d in prefs.devices:
                    d.use = True
                escena.cycles.device = "GPU"
                return tipo
    except Exception:
        pass
    return None


def _activar_resplandor(escena):
    """Halos suaves (bloom) alrededor de las luces, vía compositor.
    En Blender ≤ 4.x el compositor vive en escena.node_tree; desde 5.0 es un
    grupo de nodos aparte que hay que crear y asignar a compositing_node_group."""
    nt = None
    if hasattr(escena, "compositing_node_group"):
        nt = escena.compositing_node_group
        if nt is None:
            nt = bpy.data.node_groups.new("BuildAI Compositor", "CompositorNodeTree")
            escena.compositing_node_group = nt
    if nt is None:
        escena.use_nodes = True
        nt = getattr(escena, "node_tree", None)
    if nt is None:
        return
    if any(n.name == "BuildAI_Glare" for n in nt.nodes):
        return
    nt.nodes.clear()
    capa = nt.nodes.new("CompositorNodeRLayers")
    glare = nt.nodes.new("CompositorNodeGlare")
    glare.name = "BuildAI_Glare"
    # ≤ 4.x: el tipo/calidad son atributos del nodo; en 5.x son sockets de menú
    _fijar(glare, ("glare_type",), "BLOOM") or _fijar(glare, ("glare_type",), "FOG_GLOW")
    _fijar(glare, ("quality",), "HIGH")
    _fijar(glare, ("mix",), -0.72)
    _fijar(glare, ("threshold",), 2.0)
    _fijar(glare, ("size",), 8)
    for entrada, valores in (("Type", ("Bloom", "Fog Glow")), ("Quality", ("High",)),
                             ("Threshold", (2.0,)), ("Smoothness", (0.5,)),
                             ("Strength", (0.18,)), ("Size", (0.06,)),
                             ("Saturation", (1.0,))):
        e = _entrada(glare, entrada)
        if e is None:
            continue
        for valor in valores:
            try:
                e.default_value = valor
                break
            except Exception:
                continue
    try:
        salida = nt.nodes.new("CompositorNodeComposite")
    except Exception:
        try:
            nt.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
        except Exception:
            pass
        salida = nt.nodes.new("NodeGroupOutput")
    nt.links.new(capa.outputs["Image"], glare.inputs["Image"])
    nt.links.new(glare.outputs["Image"], salida.inputs[0])


def _vidrios_opacos_cycles():
    """El alpha reducido de los vidrios es un truco para el visor EEVEE; en
    Cycles apagaría los reflejos, así que se restaura a 1 durante el render."""
    tocados = []
    for mat in bpy.data.materials:
        if not mat.use_nodes:
            continue
        bsdf = next((n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
        if bsdf is None:
            continue
        trans = _entrada(bsdf, "Transmission Weight", "Transmission")
        alfa = _entrada(bsdf, "Alpha")
        if trans is not None and alfa is not None \
                and trans.default_value > 0.5 and alfa.default_value < 1.0:
            tocados.append((alfa, alfa.default_value))
            alfa.default_value = 1.0
    return tocados


def _auto_camara():
    """Encuadra todo lo construido (se usa si nadie colocó una cámara)."""
    puntos = []
    for obj in bpy.context.scene.objects:
        if obj.type != "MESH" or obj.hide_render:
            continue
        if obj.name.startswith(("Terreno", "Piscina_corte")):
            continue
        for esquina in obj.bound_box:
            puntos.append(obj.matrix_world @ Vector(esquina))
    if not puntos:
        return camara()
    minimo = Vector((min(p.x for p in puntos), min(p.y for p in puntos), min(p.z for p in puntos)))
    maximo = Vector((max(p.x for p in puntos), max(p.y for p in puntos), max(p.z for p in puntos)))
    centro = (minimo + maximo) / 2
    diagonal = max((maximo - minimo).length, 4.0)
    return camara(objetivo=(centro.x, centro.y, max(centro.z * 0.8, 1.0)),
                  distancia=diagonal * 0.9 + 5, azimut=225,
                  altura=max(2.0, centro.z + diagonal * 0.12), lente=35)


def render(ruta=None, calidad="media", ancho=None, alto=None):
    """Render fotorrealista con Cycles: activa GPU si la hay, denoise, tono AgX
    y halos de luz, y guarda un PNG que el usuario VE directamente en el chat.
    `calidad`: "borrador" (rápido, para comprobar encuadre), "media" o "alta".
    Antes de llamar: coloca camara(), cielo(...) y enciende las luces interiores
    (una casa apagada al atardecer sale muerta). Devuelve la ruta del archivo."""
    escena = bpy.context.scene
    perfil = _CALIDADES.get(calidad, _CALIDADES["media"])
    if escena.camera is None:
        _auto_camara()
    if not any(o.type == "LIGHT" and o.data.type == "SUN" for o in escena.objects):
        cielo("atardecer")
    escena.render.engine = "CYCLES"
    gpu = _activar_gpu(escena)
    ciclos = escena.cycles
    ciclos.samples = perfil["muestras"]
    _fijar(ciclos, ("use_adaptive_sampling",), True)
    _fijar(ciclos, ("adaptive_threshold",), perfil["umbral"])
    _fijar(ciclos, ("use_denoising",), True)
    _fijar(ciclos, ("max_bounces",), 12)
    _fijar(ciclos, ("diffuse_bounces",), 6)
    _fijar(ciclos, ("glossy_bounces",), 6)
    _fijar(ciclos, ("transmission_bounces",), 12)
    _fijar(ciclos, ("transparent_max_bounces",), 24)
    _fijar(ciclos, ("sample_clamp_indirect",), 10.0)
    _fijar(ciclos, ("caustics_reflective",), False)
    _fijar(ciclos, ("caustics_refractive",), False)
    _fijar(escena.view_settings, ("view_transform",), "AgX") \
        or _fijar(escena.view_settings, ("view_transform",), "Filmic")
    _fijar(escena.view_settings, ("look",), "AgX - Medium High Contrast")
    escena.render.resolution_x = ancho or perfil["resolucion"][0]
    escena.render.resolution_y = alto or perfil["resolucion"][1]
    escena.render.resolution_percentage = 100
    escena.render.image_settings.file_format = "PNG"
    try:
        _activar_resplandor(escena)
    except Exception as exc:
        print(f"(aviso: sin halos de luz en esta versión: {exc})")
    if ruta is None:
        CARPETA_RENDERS.mkdir(parents=True, exist_ok=True)
        ruta = str(CARPETA_RENDERS / time.strftime("render-%Y%m%d-%H%M%S.png"))
    escena.render.filepath = str(ruta)
    restaurar = _vidrios_opacos_cycles()
    inicio = time.time()
    try:
        bpy.ops.render.render(write_still=True)
    finally:
        for alfa, valor in restaurar:
            alfa.default_value = valor
    print(f"✔ Render {escena.render.resolution_x}×{escena.render.resolution_y} "
          f"en {time.time() - inicio:.0f} s (Cycles {'GPU ' + gpu if gpu else 'CPU'}, "
          f"{perfil['muestras']} muestras)")
    print(f"RENDER_GUARDADO: {ruta}")
    return str(ruta)
