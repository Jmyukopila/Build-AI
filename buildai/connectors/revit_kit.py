# -*- coding: utf-8 -*-
"""Kit de construccion BIM para Revit (via pyRevit).

Este archivo NO se importa en la app: su codigo fuente se antepone a cada
ejecucion de `revit_ejecutar_python`, de modo que el modelo de IA dispone de
funciones de alto nivel EN METROS que envuelven la API de Revit (que trabaja
en pies) y localizan solas los tipos y familias cargados.

El entorno de ejecucion (definido en la extension BuildAI de pyRevit) aporta:
`doc`, `uidoc`, `DB` (Autodesk.Revit.DB), `revit` y `salida` (lista de texto
que se devuelve al agente). Ya hay una transaccion abierta: nada de crear
transacciones propias. Debe funcionar con IronPython 2.7 y CPython, y con
Revit 2014 en adelante (por eso los fallbacks por version y ningun f-string).
"""

_PIES_POR_METRO = 1.0 / 0.3048


def _a_pies(metros):
    return float(metros) * _PIES_POR_METRO


def _a_metros(pies):
    return float(pies) / _PIES_POR_METRO


def xyz(x, y, z=0.0):
    """Punto DB.XYZ a partir de coordenadas en METROS."""
    return DB.XYZ(_a_pies(x), _a_pies(y), _a_pies(z))


def imprimir(texto):
    salida.append(u"{}".format(texto))


def _elementos(clase=None, categoria=None, solo_tipos=False):
    col = DB.FilteredElementCollector(doc)
    if clase is not None:
        col = col.OfClass(clase)
    if categoria is not None:
        col = col.OfCategory(categoria)
    if solo_tipos:
        col = col.WhereElementIsElementType()
    elif clase is None:
        col = col.WhereElementIsNotElementType()
    return list(col)


# ------------------------------------------------------------------ niveles

def niveles():
    """Lista los niveles existentes (nombre y cota en metros) y los devuelve
    ordenados de abajo arriba."""
    lista = sorted(_elementos(clase=DB.Level), key=lambda n: n.Elevation)
    for n in lista:
        imprimir(u"Nivel '{}' en cota {:.2f} m".format(n.Name, _a_metros(n.Elevation)))
    if not lista:
        imprimir(u"No hay niveles en el documento.")
    return lista


def nivel(altura, nombre=None):
    """Devuelve el nivel situado en `altura` (metros); si no existe, lo crea.
    Usalo SIEMPRE antes de construir cada planta: nivel(0), nivel(3), ..."""
    pies = _a_pies(altura)
    for n in _elementos(clase=DB.Level):
        if abs(n.Elevation - pies) < 0.01:
            return n
    try:
        nuevo = DB.Level.Create(doc, pies)          # Revit 2016+
    except AttributeError:
        nuevo = doc.Create.NewLevel(pies)           # Revit 2014-2015
    if nombre:
        try:
            nuevo.Name = nombre
        except Exception:
            pass  # nombre duplicado: se queda el automatico
    imprimir(u"Nivel creado en cota {:.2f} m ('{}')".format(altura, nuevo.Name))
    return nuevo


# -------------------------------------------------------------------- muros

def tipo_muro(nombre=None):
    """Primer tipo de muro basico cargado (o el que contenga `nombre`)."""
    tipos = _elementos(clase=DB.WallType)
    if nombre:
        for t in tipos:
            if nombre.lower() in DB.Element.Name.GetValue(t).lower():
                return t
    for t in tipos:
        try:
            if t.Kind == DB.WallKind.Basic:
                return t
        except Exception:
            return t
    raise Exception(u"No hay tipos de muro en el documento (usa una plantilla de arquitectura).")


def muro(inicio, fin, nivel_base, altura=2.7, tipo=None, estructural=False):
    """Muro recto entre dos puntos (x, y) EN METROS sobre `nivel_base`
    (objeto devuelto por nivel()). Devuelve el muro creado; guardalo si vas
    a insertarle puertas o ventanas."""
    linea = DB.Line.CreateBound(
        DB.XYZ(_a_pies(inicio[0]), _a_pies(inicio[1]), nivel_base.Elevation),
        DB.XYZ(_a_pies(fin[0]), _a_pies(fin[1]), nivel_base.Elevation),
    )
    t = tipo if tipo is not None else tipo_muro()
    obj = DB.Wall.Create(doc, linea, t.Id, nivel_base.Id, _a_pies(altura),
                         0.0, False, bool(estructural))
    imprimir(u"Muro de {:.2f} m en nivel '{}'".format(_a_metros(linea.Length), nivel_base.Name))
    return obj


# ---------------------------------------------------------- suelos y techos

def _tipo_suelo():
    tipos = _elementos(clase=DB.FloorType)
    if not tipos:
        raise Exception(u"No hay tipos de suelo en el documento.")
    return tipos[0]


def suelo(contorno, nivel_base, tipo=None):
    """Suelo/forjado con planta poligonal: `contorno` es una lista de (x, y)
    en metros (3 puntos o mas, sin repetir el primero al final)."""
    t = tipo if tipo is not None else _tipo_suelo()
    n = len(contorno)
    if n < 3:
        raise Exception(u"El contorno del suelo necesita al menos 3 puntos.")
    try:
        # Revit 2022+: Floor.Create con CurveLoop
        lazo = DB.CurveLoop()
        for i in range(n):
            a = contorno[i]
            b = contorno[(i + 1) % n]
            lazo.Append(DB.Line.CreateBound(
                DB.XYZ(_a_pies(a[0]), _a_pies(a[1]), nivel_base.Elevation),
                DB.XYZ(_a_pies(b[0]), _a_pies(b[1]), nivel_base.Elevation)))
        from System.Collections.Generic import List
        lazos = List[DB.CurveLoop]()
        lazos.Add(lazo)
        obj = DB.Floor.Create(doc, lazos, t.Id, nivel_base.Id)
    except (AttributeError, ImportError):
        # Versiones anteriores: NewFloor con CurveArray
        curvas = DB.CurveArray()
        for i in range(n):
            a = contorno[i]
            b = contorno[(i + 1) % n]
            curvas.Append(DB.Line.CreateBound(
                DB.XYZ(_a_pies(a[0]), _a_pies(a[1]), nivel_base.Elevation),
                DB.XYZ(_a_pies(b[0]), _a_pies(b[1]), nivel_base.Elevation)))
        obj = doc.Create.NewFloor(curvas, False)
        try:
            obj.get_Parameter(DB.BuiltInParameter.LEVEL_PARAM).Set(nivel_base.Id)
        except Exception:
            pass
    imprimir(u"Suelo de {} lados en nivel '{}'".format(n, nivel_base.Name))
    return obj


# ------------------------------------------------- familias e instancias

_CATEGORIAS = {
    "puertas": "OST_Doors",
    "ventanas": "OST_Windows",
    "mobiliario": "OST_Furniture",
    "pilares": "OST_Columns",
    "luminarias": "OST_LightingFixtures",
    "aparatos": "OST_PlumbingFixtures",
}


def _simbolos(categoria):
    cat = getattr(DB.BuiltInCategory, _CATEGORIAS.get(categoria, categoria))
    return _elementos(clase=DB.FamilySymbol, categoria=cat)


def familias(categoria="puertas"):
    """Lista las familias cargadas de una categoria: "puertas", "ventanas",
    "mobiliario", "pilares", "luminarias" o "aparatos" (sanitarios).
    Consultala antes de colocar: asi eliges un tipo que exista de verdad."""
    encontradas = _simbolos(categoria)
    for s in encontradas:
        imprimir(u"{} : {}".format(s.Family.Name, DB.Element.Name.GetValue(s)))
    if not encontradas:
        imprimir(u"No hay familias de {} cargadas en el documento.".format(categoria))
    return encontradas


def _buscar_simbolo(categoria, nombre=None):
    candidatos = _simbolos(categoria)
    if not candidatos:
        raise Exception(
            u"No hay familias de {} cargadas: dile al usuario que cargue una "
            u"(Insertar > Cargar familia) o usa otra solucion.".format(categoria))
    if nombre:
        buscado = nombre.lower()
        for s in candidatos:
            if buscado in DB.Element.Name.GetValue(s).lower() or buscado in s.Family.Name.lower():
                return s
    return candidatos[0]


def _activar(simbolo):
    try:
        if not simbolo.IsActive:
            simbolo.Activate()
            doc.Regenerate()
    except Exception:
        pass
    return simbolo


def puerta(muro_obj, a, nivel_base, tipo=None):
    """Puerta insertada en `muro_obj` a `a` metros del arranque del muro.
    `tipo` filtra por nombre de familia/tipo (p. ej. "0.80")."""
    simbolo = _activar(_buscar_simbolo("puertas", tipo))
    curva = muro_obj.Location.Curve
    t = min(max(_a_pies(a) / curva.Length, 0.0), 1.0)
    punto = curva.Evaluate(t, True)
    obj = doc.Create.NewFamilyInstance(
        DB.XYZ(punto.X, punto.Y, nivel_base.Elevation), simbolo, muro_obj,
        nivel_base, DB.Structure.StructuralType.NonStructural)
    imprimir(u"Puerta '{}' colocada".format(DB.Element.Name.GetValue(simbolo)))
    return obj


def ventana(muro_obj, a, nivel_base, antepecho=0.9, tipo=None):
    """Ventana en `muro_obj` a `a` metros del arranque, con `antepecho` en metros."""
    simbolo = _activar(_buscar_simbolo("ventanas", tipo))
    curva = muro_obj.Location.Curve
    t = min(max(_a_pies(a) / curva.Length, 0.0), 1.0)
    punto = curva.Evaluate(t, True)
    obj = doc.Create.NewFamilyInstance(
        DB.XYZ(punto.X, punto.Y, nivel_base.Elevation), simbolo, muro_obj,
        nivel_base, DB.Structure.StructuralType.NonStructural)
    try:
        obj.get_Parameter(DB.BuiltInParameter.INSTANCE_SILL_HEIGHT_PARAM).Set(_a_pies(antepecho))
    except Exception:
        pass
    imprimir(u"Ventana '{}' colocada (antepecho {:.2f} m)".format(
        DB.Element.Name.GetValue(simbolo), antepecho))
    return obj


def colocar(categoria, posicion, nivel_base, rotacion=0, tipo=None):
    """Instancia de familia suelta (mobiliario, luminarias, aparatos, pilares)
    en (x, y) metros sobre `nivel_base`; `rotacion` en grados."""
    import math as _math
    simbolo = _activar(_buscar_simbolo(categoria, tipo))
    punto = DB.XYZ(_a_pies(posicion[0]), _a_pies(posicion[1]), nivel_base.Elevation)
    obj = doc.Create.NewFamilyInstance(
        punto, simbolo, nivel_base, DB.Structure.StructuralType.NonStructural)
    if rotacion:
        eje = DB.Line.CreateBound(punto, DB.XYZ(punto.X, punto.Y, punto.Z + 1.0))
        DB.ElementTransformUtils.RotateElement(doc, obj.Id, eje, _math.radians(rotacion))
    imprimir(u"{} '{}' colocado en ({:.2f}, {:.2f})".format(
        categoria, DB.Element.Name.GetValue(simbolo), posicion[0], posicion[1]))
    return obj


def pilar(posicion, nivel_base, rotacion=0, tipo=None):
    """Pilar en (x, y) metros sobre `nivel_base` (usa la primera familia de
    pilar cargada, o la que contenga `tipo`)."""
    return colocar("pilares", posicion, nivel_base, rotacion, tipo)


def borrar(elemento):
    """Elimina un elemento (objeto o ElementId). Solo con permiso del usuario."""
    el_id = elemento if isinstance(elemento, DB.ElementId) else elemento.Id
    doc.Delete(el_id)
    imprimir(u"Elemento eliminado.")
