"""Del plano normalizado al código de cada programa.

Cada constructor devuelve el código que se envía por la herramienta de
ejecución del conector correspondiente (la misma que usa la IA a mano), de
modo que la reconstrucción hereda su kit, sus unidades y su manejo de errores:

- Blender  → kit de construcción (`muro`, `forjado`…), en metros.
- AutoCAD  → Python por COM con `acad`, `doc`, `ms`, `punto`, `puntos`; lee
             INSUNITS del dibujo para escribir en sus unidades (mm, cm o m).
- SketchUp → Ruby con medidas `.m` (la API trabaja en pulgadas).
- Revit    → kit BIM (`nivel`, `muro`, `suelo`…): muros, suelos, puertas,
             ventanas y habitaciones nativas. Python 2/3 compatible.

Los datos (puntos, huecos, contornos) se incrustan como literales y el código
recorre esas listas: así el código generado es corto y no crece con una línea
de API por cada elemento.
"""

import json
import math
import re

PROGRAMAS = ("blender", "autocad", "sketchup", "revit")


def _material_suelo(nombre):
    """Acabado de suelo verosímil según el nombre de la estancia."""
    n = nombre.lower()
    if re.search(r"cocin|ba[nñ]o|aseo|lavader|tendedero|despensa", n):
        return "baldosa"
    if re.search(r"terraza|porche|patio|garaje|exterior", n):
        return "pavimento"
    return "parquet"


def _capa(planta):
    return f"Plano - {planta['nombre']}"


def _r(valor):
    """Número redondeado al milímetro para incrustarlo en el código generado."""
    return round(float(valor), 4)


def _pt(p):
    return (_r(p[0]), _r(p[1]))


# ------------------------------------------------------------------ Blender

def a_blender(plano, reemplazar=False):
    bloques = []
    for planta in plano["plantas"]:
        capa = _capa(planta)
        muros = [
            {
                "nombre": f"Muro {m['id']}",
                "inicio": _pt(m["inicio"]),
                "fin": _pt(m["fin"]),
                "espesor": _r(m["espesor"]),
                "huecos": [
                    {k: h[k] for k in ("tipo", "a", "ancho", "alto", "antepecho")}
                    for h in m["huecos"]
                ],
            }
            for m in planta["muros"]
        ]
        suelos = [
            {
                "nombre": f"Suelo {e['nombre']}",
                "contorno": [_pt(p) for p in e["contorno"]],
                "material": _material_suelo(e["nombre"]),
            }
            for e in planta["estancias"]
        ]
        bloques.append(
            f"""
_capa = {capa!r}
if {bool(reemplazar)!r}:
    _col = bpy.data.collections.get(_capa)
    if _col is not None:
        for _o in list(_col.objects):
            bpy.data.objects.remove(_o, do_unlink=True)
coleccion(_capa)
_nivel, _alto = {_r(planta['nivel'])!r}, {_r(planta['altura'])!r}
for _m in {muros!r}:
    muro(_m["inicio"], _m["fin"], alto=_alto, espesor=_m["espesor"], nivel=_nivel,
         huecos=_m["huecos"], material="blanco", capa=_capa, nombre=_m["nombre"])
forjado({[_pt(p) for p in planta['huella']]!r}, nivel=_nivel, espesor=0.3,
        material="hormigon", capa=_capa, nombre="Solera")
# Acabado de cada estancia: 2 cm sobre la solera, dentro de los muros.
for _s in {suelos!r}:
    forjado(_s["contorno"], nivel=_nivel + 0.02, espesor=0.02, material=_s["material"],
            capa=_capa, nombre=_s["nombre"])
print("✔ " + _capa + ": {len(muros)} muros y {len(suelos)} suelos de estancia")
"""
        )
    return "".join(bloques)


# ------------------------------------------------------------------ AutoCAD

def _geometria_carpinterias(planta):
    """Puertas (hoja + arco de giro) y ventanas (caras + vidrio) en planta, en metros."""
    hojas, arcos, ventanas = [], [], []
    for m in planta["muros"]:
        (x0, y0), (x1, y1) = m["inicio"], m["fin"]
        largo = math.hypot(x1 - x0, y1 - y0) or 1e-9
        ux, uy = (x1 - x0) / largo, (y1 - y0) / largo
        nx, ny = -uy, ux
        e2 = m["espesor"] / 2
        for h in m["huecos"]:
            ax, ay = x0 + ux * h["a"], y0 + uy * h["a"]
            bx, by = ax + ux * h["ancho"], ay + uy * h["ancho"]
            if h["tipo"] == "puerta":
                lado = 1.0
                if h.get("abre_hacia"):
                    px, py = h["abre_hacia"]
                    lado = 1.0 if (px - ax) * nx + (py - ay) * ny >= 0 else -1.0
                # Bisagra en la cara del lado hacia el que abre; la hoja dibujada
                # abierta a 90° y el arco de giro hasta la otra jamba.
                hx, hy = ax + nx * e2 * lado, ay + ny * e2 * lado
                r = h["ancho"]
                hojas.append(((_r(hx), _r(hy)), (_r(hx + nx * lado * r), _r(hy + ny * lado * r))))
                angulo_muro = math.atan2(uy, ux)
                angulo_hoja = math.atan2(ny * lado, nx * lado)
                # AutoCAD dibuja los arcos en sentido antihorario de inicio a fin.
                if ux * (ny * lado) - uy * (nx * lado) > 0:
                    inicio, fin = angulo_muro, angulo_hoja
                else:
                    inicio, fin = angulo_hoja, angulo_muro
                arcos.append(((_r(hx), _r(hy)), _r(r), _r(inicio), _r(fin)))
            elif h["tipo"] in ("ventana", "ventanal"):
                for desfase in (-e2, 0.0, e2):
                    ventanas.append((
                        (_r(ax + nx * desfase), _r(ay + ny * desfase)),
                        (_r(bx + nx * desfase), _r(by + ny * desfase)),
                    ))
    return hojas, arcos, ventanas


def a_autocad(plano):
    plantas = []
    desfase_x = 0.0
    for planta in plano["plantas"]:
        xs = [p[0] for p in planta["huella"]]
        ys = [p[1] for p in planta["huella"]]
        hojas, arcos, ventanas = _geometria_carpinterias(planta)
        inclinados = []
        for m in planta["muros"]:
            if m["ortogonal"]:
                continue
            (x0, y0), (x1, y1) = m["inicio"], m["fin"]
            largo = math.hypot(x1 - x0, y1 - y0) or 1e-9
            nx, ny = -(y1 - y0) / largo * m["espesor"] / 2, (x1 - x0) / largo * m["espesor"] / 2
            inclinados.append([
                _pt((x0 + nx, y0 + ny)), _pt((x1 + nx, y1 + ny)),
                _pt((x1 - nx, y1 - ny)), _pt((x0 - nx, y0 - ny)),
            ])
        plantas.append({
            "nombre": planta["nombre"],
            # Cada planta se dibuja a la derecha de la anterior, como en una
            # lámina de plantas, para que no se superpongan.
            "dx": _r(desfase_x),
            "lineas": [[_pt(a), _pt(b)] for a, b in planta["lineas_planta"]],
            "macizos": [list(r) for r in planta["macizos"]],
            "inclinados": inclinados,
            "hojas": hojas,
            "arcos": arcos,
            "ventanas": ventanas,
            "estancias": [
                [e["nombre"], _pt(e["centro"]), e["superficie"]] for e in planta["estancias"]
            ],
            "caja": [_r(min(xs)), _r(min(ys)), _r(max(xs)), _r(max(ys))],
        })
        desfase_x += (max(xs) - min(xs)) + 5.0

    return f"""
import math
_PLANTAS = {plantas!r}
# Unidades del dibujo: 4 = mm, 5 = cm, 6 = m (1 y 2: pulgadas y pies). Sin
# unidades definidas (0) se asume mm, lo habitual en planos de arquitectura.
_INSUNITS = int(doc.GetVariable("INSUNITS"))
_U = {{1: 39.3701, 2: 3.28084, 4: 1000.0, 5: 100.0, 6: 1.0}}.get(_INSUNITS, 1000.0)
try:
    doc.SetVariable("DIMSCALE", 50.0 * _U / 1000.0)  # cotas legibles a 1:50
except Exception:
    pass

def _capa(nombre, color):
    try:
        capa = doc.Layers.Item(nombre)
    except Exception:
        capa = doc.Layers.Add(nombre)
    capa.color = color
    return nombre

def _p(x, y, dx):
    return punto((x + dx) * _U, y * _U)

def _sombrear(capa, rects, dx):
    # Relleno sólido de los muros cortados (poché). Si esta versión de AutoCAD
    # no admite crear sombreados por COM, el plano sigue completo sin él.
    try:
        import pythoncom
        import win32com.client
    except ImportError:
        return 0
    hechos = 0
    for x0, y0, x1, y1 in rects:
        borde = ms.AddLightWeightPolyline(puntos([((x0 + dx) * _U, y0 * _U), ((x1 + dx) * _U, y0 * _U),
                                                  ((x1 + dx) * _U, y1 * _U), ((x0 + dx) * _U, y1 * _U)]))
        borde.Closed = True
        borde.Layer = capa
        try:
            # Sombreado no asociativo: así se puede borrar el borde auxiliar y no
            # quedan líneas dobles sobre las de la capa de muros.
            sombreado = ms.AddHatch(0, "SOLID", False)
            sombreado.AppendOuterLoop(win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_DISPATCH, [borde]))
            sombreado.Evaluate()
            sombreado.Layer = capa
            hechos += 1
        except Exception:
            borde.Delete()
            return hechos
        borde.Delete()
    return hechos

for _pl in _PLANTAS:
    _dx = _pl["dx"]
    _pref = _pl["nombre"] + " - "
    c_muros = _capa(_pref + "Muros", 7)
    c_relleno = _capa(_pref + "Muros relleno", 8)
    c_puertas = _capa(_pref + "Puertas", 30)
    c_ventanas = _capa(_pref + "Ventanas", 4)
    c_textos = _capa(_pref + "Estancias", 2)
    c_cotas = _capa(_pref + "Cotas", 1)
    for (a, b) in _pl["lineas"]:
        ms.AddLine(_p(a[0], a[1], _dx), _p(b[0], b[1], _dx)).Layer = c_muros
    for contorno in _pl["inclinados"]:
        pl = ms.AddLightWeightPolyline(puntos([((x + _dx) * _U, y * _U) for x, y in contorno]))
        pl.Closed = True
        pl.Layer = c_muros
    _rellenos = _sombrear(c_relleno, _pl["macizos"], _dx)
    for (a, b) in _pl["hojas"]:
        ms.AddLine(_p(a[0], a[1], _dx), _p(b[0], b[1], _dx)).Layer = c_puertas
    for (c, r, ini, fin) in _pl["arcos"]:
        ms.AddArc(_p(c[0], c[1], _dx), r * _U, ini, fin).Layer = c_puertas
    for (a, b) in _pl["ventanas"]:
        ms.AddLine(_p(a[0], a[1], _dx), _p(b[0], b[1], _dx)).Layer = c_ventanas
    for (nombre, c, sup) in _pl["estancias"]:
        alto_txt = 0.2 * _U
        t = ms.AddText(nombre.upper(), _p(c[0] - 0.07 * len(nombre), c[1] + 0.05, _dx), alto_txt)
        t.Layer = c_textos
        rotulo = ("%.2f m²" % sup).replace(".", ",")
        t = ms.AddText(rotulo, _p(c[0] - 0.05 * len(rotulo), c[1] - 0.3, _dx), alto_txt * 0.75)
        t.Layer = c_textos
    x0, y0, x1, y1 = _pl["caja"]
    try:
        ms.AddDimAligned(_p(x0, y0, _dx), _p(x1, y0, _dx), _p((x0 + x1) / 2, y0 - 1.0, _dx)).Layer = c_cotas
        ms.AddDimAligned(_p(x0, y0, _dx), _p(x0, y1, _dx), _p(x0 - 1.0, (y0 + y1) / 2, _dx)).Layer = c_cotas
    except Exception as exc:
        print("Aviso: no se pudieron crear las cotas generales (%s)" % exc)
    print("%s: %d líneas de muro, %d puertas, %d ventanas, %d estancias, %d rellenos"
          % (_pl["nombre"], len(_pl["lineas"]), len(_pl["arcos"]),
             len(_pl["ventanas"]) // 3, len(_pl["estancias"]), _rellenos))
acad.ZoomExtents()
print("Dibujado en unidades INSUNITS=%d (1 m = %g unidades)" % (_INSUNITS, _U))
"""


# ----------------------------------------------------------------- SketchUp

def _rb(valor):
    """Número en Ruby con unidad métrica: `4.1.m`. Paréntesis para los negativos."""
    v = _r(valor)
    return f"({v}).m" if v < 0 else f"{v}.m"


def _rb_punto(x, y, z):
    return f"Geom::Point3d.new({_rb(x)}, {_rb(y)}, {_rb(z)})"


def _ruby_texto(texto):
    """Literal de cadena Ruby seguro, entre comillas SIMPLES.

    Con comillas dobles Ruby interpola `#{...}`: un nombre de estancia leído de
    un DXF ajeno como "#{system('...')}" se ejecutaría. Entre comillas simples
    solo hay que escapar la barra y la propia comilla.
    """
    return "'" + str(texto).replace("\\", "\\\\").replace("'", "\\'") + "'"


def a_sketchup(plano, reemplazar=False):
    lineas = [
        "model = Sketchup.active_model",
        "model.start_operation('BuildAI: reconstruir plano', true)",
        "ents = model.active_entities",
        "mat_muro = model.materials['BuildAI Muro'] || model.materials.add('BuildAI Muro')",
        "mat_muro.color = Sketchup::Color.new(236, 233, 226)",
        "mat_vidrio = model.materials['BuildAI Vidrio'] || model.materials.add('BuildAI Vidrio')",
        "mat_vidrio.color = Sketchup::Color.new(150, 190, 215)",
        "mat_vidrio.alpha = 0.35",
        "suelos = {'parquet' => [176, 132, 90], 'baldosa' => [214, 210, 200], 'pavimento' => [160, 158, 150]}",
        "",
        "# Muro = su cara lateral con los huecos recortados, extruida su espesor:",
        "# así cada muro es un sólido limpio con los huecos pasantes.",
        "def ba_muro(ents, nombre, capa, mat, cara, huecos, normal, espesor)",
        "  g = ents.add_group",
        "  g.name = nombre",
        "  g.layer = capa",
        "  e = g.entities",
        "  e.add_face(cara)",
        "  huecos.each { |h| f = e.add_face(h); f.erase! if f && f.valid? }",
        "  f = e.grep(Sketchup::Face).max_by(&:area)",
        "  f.reverse! if f.normal.dot(normal) < 0",
        "  f.pushpull(espesor)",
        "  g.material = mat",
        "  g",
        "end",
        "",
    ]
    for planta in plano["plantas"]:
        capa = _capa(planta)
        z0 = planta["nivel"]
        z1 = planta["nivel"] + planta["altura"]
        lineas.append(f"capa = model.layers[{_ruby_texto(capa)}] || model.layers.add({_ruby_texto(capa)})")
        if reemplazar:
            lineas.append("ents.grep(Sketchup::Group).select { |g| g.layer == capa }.each(&:erase!)")
        for m in planta["muros"]:
            (x0, y0), (x1, y1) = m["inicio"], m["fin"]
            largo = math.hypot(x1 - x0, y1 - y0) or 1e-9
            ux, uy = (x1 - x0) / largo, (y1 - y0) / largo
            nx, ny = -uy, ux
            e2 = m["espesor"] / 2
            # La cara se dibuja en el plano del lado -normal y se extruye hacia +normal.
            bx0, by0 = x0 - nx * e2, y0 - ny * e2
            bx1, by1 = x1 - nx * e2, y1 - ny * e2
            cara = [_rb_punto(bx0, by0, z0), _rb_punto(bx1, by1, z0),
                    _rb_punto(bx1, by1, z1), _rb_punto(bx0, by0, z1)]
            huecos, vidrios = [], []
            for h in m["huecos"]:
                ha, hb = h["a"], h["a"] + h["ancho"]
                hz0, hz1 = z0 + h["antepecho"], z0 + h["antepecho"] + h["alto"]
                pa = (bx0 + ux * ha, by0 + uy * ha)
                pb = (bx0 + ux * hb, by0 + uy * hb)
                huecos.append("[" + ", ".join([
                    _rb_punto(pa[0], pa[1], hz0), _rb_punto(pb[0], pb[1], hz0),
                    _rb_punto(pb[0], pb[1], hz1), _rb_punto(pa[0], pa[1], hz1),
                ]) + "]")
                if h["tipo"] in ("ventana", "ventanal"):
                    va = (pa[0] + nx * e2, pa[1] + ny * e2)
                    vb = (pb[0] + nx * e2, pb[1] + ny * e2)
                    vidrios.append("[" + ", ".join([
                        _rb_punto(va[0], va[1], hz0), _rb_punto(vb[0], vb[1], hz0),
                        _rb_punto(vb[0], vb[1], hz1), _rb_punto(va[0], va[1], hz1),
                    ]) + "]")
            lineas.append(
                f"g = ba_muro(ents, {_ruby_texto('Muro ' + m['id'])}, capa, mat_muro, "
                f"[{', '.join(cara)}], [{', '.join(huecos)}], "
                f"Geom::Vector3d.new({_r(nx)}, {_r(ny)}, 0), {_rb(m['espesor'])})"
            )
            for v in vidrios:
                lineas.append(f"vf = g.entities.add_face({v}); vf.material = mat_vidrio; vf.back_material = mat_vidrio")
        huella = ", ".join(_rb_punto(x, y, z0) for x, y in planta["huella"])
        lineas += [
            "g = ents.add_group; g.name = 'Solera'; g.layer = capa",
            f"f = g.entities.add_face([{huella}])",
            "f.reverse! if f.normal.z < 0",
            "f.pushpull(-0.3.m)",
        ]
        for e in planta["estancias"]:
            contorno = ", ".join(_rb_punto(x, y, z0 + 0.005) for x, y in e["contorno"])
            color = {"parquet": "parquet", "baldosa": "baldosa", "pavimento": "pavimento"}[_material_suelo(e["nombre"])]
            cx, cy = e["centro"]
            lineas += [
                f"g = ents.add_group; g.name = {_ruby_texto('Suelo ' + e['nombre'])}; g.layer = capa",
                f"f = g.entities.add_face([{contorno}])",
                "f.reverse! if f.normal.z < 0",
                f"m = model.materials[{_ruby_texto('BuildAI ' + color)}] || model.materials.add({_ruby_texto('BuildAI ' + color)})",
                f"m.color = Sketchup::Color.new(*suelos[{_ruby_texto(color)}]); f.material = m",
                f"ents.add_text({_ruby_texto(e['nombre'] + ' ' + str(e['superficie']).replace('.', ',') + ' m²')}, "
                f"{_rb_punto(cx, cy, z0 + 0.01)})",
            ]
        lineas.append(
            f"puts {_ruby_texto(capa + ': ' + str(len(planta['muros'])) + ' muros, ' + str(len(planta['estancias'])) + ' estancias')}"
        )
    lineas += [
        "model.commit_operation",
        "Sketchup.send_action('viewZoomExtents:')",
        "'Plano reconstruido'",
    ]
    return "\n".join(lineas) + "\n"


# -------------------------------------------------------------------- Revit

def a_revit(plano):
    datos = []
    for planta in plano["plantas"]:
        datos.append({
            "nombre": planta["nombre"],
            "nivel": _r(planta["nivel"]),
            "altura": _r(planta["altura"]),
            "muros": [
                {
                    "id": m["id"],
                    # Revit une solo los muros por su eje: se le dan los ejes, no
                    # los extremos de obra que usan Blender y SketchUp.
                    "inicio": _pt(m["eje_inicio"]),
                    "fin": _pt(m["eje_fin"]),
                    "espesor": _r(m["espesor"]),
                    "huecos": [
                        [h["tipo"], h["centro_eje"], h["ancho"], h["alto"], h["antepecho"]]
                        for h in m["huecos"]
                    ],
                }
                for m in planta["muros"]
            ],
            "huella": [_pt(p) for p in planta["huella"]],
            "estancias": [[e["nombre"], _pt(e["centro"])] for e in planta["estancias"]],
        })
    # Sin f-strings ni u"" con formato moderno: el código corre también en
    # IronPython 2.7. Los datos van como JSON para no depender de repr().
    return u'''
import json as _json
_PLANTAS = _json.loads(%s)

def _tipo_por_espesor(espesor):
    mejor = None
    for t in _elementos(clase=DB.WallType):
        try:
            if t.Kind != DB.WallKind.Basic:
                continue
            d = abs(_a_metros(t.Width) - espesor)
        except Exception:
            continue
        if mejor is None or d < mejor[0]:
            mejor = (d, t)
    return mejor[1] if mejor else None

def _ancho_simbolo(s):
    for nombre in ("DOOR_WIDTH", "WINDOW_WIDTH", "FAMILY_WIDTH_PARAM"):
        try:
            p = s.get_Parameter(getattr(DB.BuiltInParameter, nombre))
            if p is not None and p.AsDouble() > 0:
                return _a_metros(p.AsDouble())
        except Exception:
            pass
    return None

def _simbolo_por_ancho(categoria, ancho):
    mejor = None
    for s in _simbolos(categoria):
        a = _ancho_simbolo(s)
        d = abs(a - ancho) if a is not None else 99.0
        if mejor is None or d < mejor[0]:
            mejor = (d, s)
    return mejor[1] if mejor else None

def _hueco_libre(muro_obj, centro, ancho, z0, z1, nivel_base):
    curva = muro_obj.Location.Curve
    p0 = curva.GetEndPoint(0)
    d = (curva.GetEndPoint(1) - p0).Normalize()
    a = p0 + d * _a_pies(centro - ancho / 2.0)
    b = p0 + d * _a_pies(centro + ancho / 2.0)
    doc.Create.NewOpening(muro_obj,
                          DB.XYZ(a.X, a.Y, nivel_base.Elevation + _a_pies(z0)),
                          DB.XYZ(b.X, b.Y, nivel_base.Elevation + _a_pies(z1)))

_resumen = []
for _pl in _PLANTAS:
    _nivel = nivel(_pl["nivel"], _pl["nombre"])
    _cuentas = {"muros": 0, "puertas": 0, "ventanas": 0, "huecos": 0, "habitaciones": 0}
    _sin_familia = set()
    _tipos = {}
    for _m in _pl["muros"]:
        _e = _m["espesor"]
        if _e not in _tipos:
            _tipos[_e] = _tipo_por_espesor(_e)
        _w = muro(_m["inicio"], _m["fin"], _nivel, altura=_pl["altura"], tipo=_tipos[_e])
        _cuentas["muros"] += 1
        for (_tipo, _centro, _ancho, _alto, _ante) in _m["huecos"]:
            _cat = "puertas" if _tipo == "puerta" else "ventanas"
            _s = _simbolo_por_ancho(_cat, _ancho) if _tipo != "paso" else None
            try:
                if _s is None:
                    if _tipo != "paso":
                        _sin_familia.add(_cat)
                    _hueco_libre(_w, _centro, _ancho, _ante, _ante + _alto, _nivel)
                    _cuentas["huecos"] += 1
                    continue
                _activar(_s)
                _pt = _w.Location.Curve.Evaluate(min(max(_a_pies(_centro) / _w.Location.Curve.Length, 0.0), 1.0), True)
                _obj = doc.Create.NewFamilyInstance(DB.XYZ(_pt.X, _pt.Y, _nivel.Elevation), _s, _w, _nivel,
                                                    DB.Structure.StructuralType.NonStructural)
                if _cat == "ventanas":
                    try:
                        _obj.get_Parameter(DB.BuiltInParameter.INSTANCE_SILL_HEIGHT_PARAM).Set(_a_pies(_ante))
                    except Exception:
                        pass
                _cuentas[_cat] += 1
            except Exception as _exc:
                imprimir(u"Aviso: hueco en el muro {} no colocado ({})".format(_m["id"], _exc))
    try:
        suelo(_pl["huella"], _nivel)
    except Exception as _exc:
        imprimir(u"Aviso: no se pudo crear el suelo ({})".format(_exc))
    doc.Regenerate()
    for (_nombre, _c) in _pl["estancias"]:
        try:
            _hab = doc.Create.NewRoom(_nivel, DB.UV(_a_pies(_c[0]), _a_pies(_c[1])))
            _hab.get_Parameter(DB.BuiltInParameter.ROOM_NAME).Set(_nombre)
            _cuentas["habitaciones"] += 1
        except Exception as _exc:
            imprimir(u"Aviso: habitacion '{}' no creada ({})".format(_nombre, _exc))
    for _cat in sorted(_sin_familia):
        imprimir(u"No hay familias de {} cargadas: esos huecos quedan como aberturas libres.".format(_cat))
    imprimir(u"{}: {} muros, {} puertas, {} ventanas, {} aberturas libres, {} habitaciones".format(
        _pl["nombre"], _cuentas["muros"], _cuentas["puertas"], _cuentas["ventanas"],
        _cuentas["huecos"], _cuentas["habitaciones"]))
''' % repr(json.dumps(datos, ensure_ascii=True))


def generar(programa, plano, reemplazar=False):
    """Código para `programa` a partir de un plano normalizado."""
    if programa == "blender":
        return a_blender(plano, reemplazar)
    if programa == "autocad":
        return a_autocad(plano)
    if programa == "sketchup":
        return a_sketchup(plano, reemplazar)
    if programa == "revit":
        return a_revit(plano)
    raise ValueError(f"Programa desconocido: {programa}")
