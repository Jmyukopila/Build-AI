"""Conector con AutoCAD mediante automatización COM (no requiere plugin)."""

import contextlib
import io
import time

from .. import entregables
from .base import Conector, recortar


# El ProgID sin versión resuelve a la instalación registrada (AutoCAD 2004-2026).
# Los versionados cubren registros incompletos: 25≈2025-26, 24≈2021-24, 23≈2019-20,
# 22≈2018, 21≈2017, 20≈2015-16, 19≈2013-14, 18≈2010-12.
_PROG_IDS = ("AutoCAD.Application",) + tuple(
    f"AutoCAD.Application.{n}" for n in range(25, 17, -1)
)


def _obtener_acad():
    import pythoncom
    import win32com.client

    pythoncom.CoInitialize()
    ultimo_error = None
    for prog_id in _PROG_IDS:
        try:
            return win32com.client.GetActiveObject(prog_id)
        except Exception as exc:
            ultimo_error = exc
    raise ultimo_error


_ESPERA_MAXIMA = 45   # segundos que se le dan a AutoCAD para escribir el archivo
_INTERVALO_SONDEO = 0.5  # cada cuánto se mira si el archivo ya está completo


def _esperar_archivo(ruta, segundos=None):
    """SendCommand vuelve antes de que AutoCAD haya terminado de escribir: hay que
    esperar a que el archivo exista y deje de crecer."""
    limite = time.time() + (_ESPERA_MAXIMA if segundos is None else segundos)
    tamano_previo = -1
    estable = 0
    while time.time() < limite:
        time.sleep(_INTERVALO_SONDEO)
        if not ruta.exists():
            continue
        tamano = ruta.stat().st_size
        estable = estable + 1 if tamano == tamano_previo and tamano > 0 else 0
        tamano_previo = tamano
        if estable >= 2:
            return True
    return False


def _conjunto_vacio(doc):
    """SelectionSet vacío: doc.Export lo exige aunque para DXF no lo use."""
    nombre = "BUILDAI_EXPORT"
    for i in range(doc.SelectionSets.Count):
        if doc.SelectionSets.Item(i).Name == nombre:
            doc.SelectionSets.Item(i).Delete()
            break
    return doc.SelectionSets.Add(nombre)


class ConectorAutoCAD(Conector):
    id = "autocad"
    nombre = "AutoCAD"
    icono = "autocad"
    ayuda = (
        "1. Abre AutoCAD con un dibujo (no hace falta instalar nada).\n"
        "2. BuildAI se conecta automáticamente por Windows (COM). Funciona con "
        "AutoCAD completo 2004 o posterior; AutoCAD LT no está soportado.\n"
        "3. Si el punto sigue en rojo, comprueba que AutoCAD y BuildAI se "
        "ejecutan con el mismo usuario (ambos normales o ambos como administrador)."
    )

    def disponible(self) -> bool:
        try:
            acad = _obtener_acad()
            return acad.Documents.Count >= 0
        except Exception:
            return False

    def herramientas(self) -> list:
        return [
            {
                "nombre": "autocad_informacion",
                "descripcion": (
                    "Devuelve información del dibujo activo de AutoCAD: nombre, "
                    "capas y recuento de entidades del espacio modelo."
                ),
                "parametros": {"type": "object", "properties": {}, "required": []},
            },
            {
                "nombre": "autocad_ejecutar_python",
                "descripcion": (
                    "Ejecuta código Python que controla AutoCAD por COM. Variables ya "
                    "disponibles: `acad` (AutoCAD.Application), `doc` (documento activo), "
                    "`ms` (espacio modelo). Los puntos se pasan como VARIANT: usa las "
                    "funciones auxiliares ya definidas `punto(x, y, z=0)` para un punto y "
                    "`puntos([(x1,y1), (x2,y2), …])` para la lista plana que exigen las "
                    "polilíneas. Usa print() para devolver información.\n\n"
                    "Unidades: las del dibujo activo (consulta doc.GetVariable('INSUNITS'): "
                    "4=milímetros, 6=metros; en plantas de arquitectura lo habitual es mm).\n"
                    "Método de trabajo para planos profesionales:\n"
                    "- Crea capas por función y asigna cada entidad: "
                    "capa = doc.Layers.Add('Muros'); entidad.Layer = 'Muros'.\n"
                    "- Muros en planta: polilíneas con "
                    "ms.AddLightWeightPolyline(puntos([(0,0), (5000,0), …])) — una línea "
                    "por cara del muro, o cierra el contorno con pl.Closed = True.\n"
                    "- Líneas y círculos: ms.AddLine(punto(...), punto(...)), "
                    "ms.AddCircle(punto(centro), radio). Puertas: arco de abatimiento con "
                    "ms.AddArc(punto(eje), radio, angulo_inicial, angulo_final) en radianes.\n"
                    "- Mobiliario y carpinterías repetidas: define un bloque una vez "
                    "(bloque = doc.Blocks.Add(punto(0,0), 'Cama150'); dibuja dentro con "
                    "bloque.AddLine(...)) e insértalo con "
                    "ms.InsertBlock(punto(x,y,0), 'Cama150', 1, 1, 1, rotacion_radianes).\n"
                    "- Textos y cotas: ms.AddText('COCINA', punto(x,y), altura_texto), "
                    "ms.AddDimAligned(punto(p1), punto(p2), punto(posicion_linea_cota)). "
                    "Ajusta la escala de las cotas al plano: doc.SetVariable('DIMSCALE', 50) "
                    "para 1:50 (100 para 1:100) ANTES de acotar, y pon textos con altura "
                    "legible a esa escala (p. ej. 2.5 × escala en mm).\n"
                    "- Colores por capa: capa.color = 1 (rojo) … 7 (blanco); asigna espesores "
                    "conceptuales usando colores distintos para muros (grueso) y mobiliario (fino).\n"
                    "- Al terminar una zona, encuadra con acad.ZoomExtents()."
                ),
                "parametros": {
                    "type": "object",
                    "properties": {
                        "codigo": {
                            "type": "string",
                            "description": "Código Python a ejecutar (acad, doc, ms y punto() disponibles).",
                        }
                    },
                    "required": ["codigo"],
                },
            },
            {
                "nombre": "autocad_comando",
                "descripcion": (
                    "Envía una orden de línea de comandos o AutoLISP a AutoCAD, como si "
                    "se escribiera en su barra de comandos. Termina cada orden con un "
                    "espacio o salto de línea para ejecutarla."
                ),
                "parametros": {
                    "type": "object",
                    "properties": {
                        "orden": {
                            "type": "string",
                            "description": "Orden a enviar, p. ej. '_ZOOM _E ' o una expresión AutoLISP.",
                        }
                    },
                    "required": ["orden"],
                },
            },
            {
                "nombre": "autocad_exportar",
                "descripcion": (
                    "Exporta el dibujo activo a un archivo profesional que el usuario "
                    "puede descargar y abrir en cualquier programa de CAD. El dibujo "
                    "abierto no se toca ni cambia de nombre: siempre se escribe una copia.\n"
                    "Formatos: 'dwg' (formato nativo de AutoCAD, el que piden estudios y "
                    "constructoras), 'dxf' (intercambio abierto, lo lee cualquier CAD) y "
                    "'pdf' (para imprimir o enviar a cliente; usa la configuración de "
                    "trazado del dibujo).\n"
                    "Termina el dibujo ANTES de exportar: la copia refleja el estado "
                    "actual del modelo, no se actualiza sola después."
                ),
                "parametros": {
                    "type": "object",
                    "properties": {
                        "formato": {
                            "type": "string",
                            "enum": ["dwg", "dxf", "pdf"],
                            "description": "Formato del archivo a generar.",
                        },
                        "nombre": {
                            "type": "string",
                            "description": (
                                "Nombre descriptivo para el archivo, p. ej. "
                                "'planta-baja'. Si se omite se usa el del dibujo."
                            ),
                        },
                    },
                    "required": ["formato"],
                },
            },
        ]

    def ejecutar(self, nombre: str, argumentos: dict) -> str:
        try:
            acad = _obtener_acad()
            if acad.Documents.Count == 0:
                return "ERROR: AutoCAD está abierto pero no hay ningún dibujo abierto."
            doc = acad.ActiveDocument
            ms = doc.ModelSpace
        except Exception as exc:
            return f"ERROR: no se pudo conectar con AutoCAD ({exc}). ¿Está abierto?"

        if nombre == "autocad_informacion":
            try:
                capas = [doc.Layers.Item(i).Name for i in range(doc.Layers.Count)]
                return recortar(
                    f"Dibujo: {doc.Name}\n"
                    f"Entidades en espacio modelo: {ms.Count}\n"
                    f"Capas ({len(capas)}): {', '.join(capas)}"
                )
            except Exception as exc:
                return f"ERROR leyendo el dibujo: {exc}"

        if nombre == "autocad_comando":
            try:
                orden = argumentos.get("orden", "")
                if not orden.endswith(("\n", " ")):
                    orden += "\n"
                doc.SendCommand(orden)
                return "Orden enviada a AutoCAD."
            except Exception as exc:
                return f"ERROR enviando la orden: {exc}"

        if nombre == "autocad_exportar":
            return _exportar(doc, argumentos)

        # autocad_ejecutar_python
        import pythoncom
        import win32com.client

        def punto(x, y, z=0.0):
            return win32com.client.VARIANT(
                pythoncom.VT_ARRAY | pythoncom.VT_R8, (float(x), float(y), float(z))
            )

        def puntos(lista):
            """Lista plana de coordenadas 2D, formato de AddLightWeightPolyline."""
            plano = []
            for p in lista:
                plano.extend((float(p[0]), float(p[1])))
            return win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, plano)

        entorno = {"acad": acad, "doc": doc, "ms": ms, "punto": punto, "puntos": puntos}
        salida = io.StringIO()
        try:
            with contextlib.redirect_stdout(salida):
                exec(argumentos.get("codigo", ""), entorno)  # noqa: S102 — propósito del conector
        except Exception as exc:
            return f"ERROR ejecutando el código: {type(exc).__name__}: {exc}\nSalida previa:\n{recortar(salida.getvalue())}"
        return recortar(salida.getvalue() or "Código ejecutado correctamente (sin salida).")


def _exportar(doc, argumentos: dict) -> str:
    formato = str(argumentos.get("formato", "")).lower().strip()
    if formato not in ("dwg", "dxf", "pdf"):
        return "ERROR: formato no soportado. Usa 'dwg', 'dxf' o 'pdf'."
    base = argumentos.get("nombre") or str(doc.Name).rsplit(".", 1)[0]
    ruta = entregables.ruta_para(base, formato)

    try:
        if formato == "dwg":
            # -WBLOCK escribe una copia completa del dibujo. Se descarta SaveAs a
            # propósito: renombraría el dibujo que el usuario tiene abierto.
            # El prefijo '_' fuerza los nombres de orden en inglés en AutoCAD
            # localizado, y '.' evita órdenes redefinidas por el usuario.
            doc.SendCommand(f'_.-WBLOCK\n{ruta}\n*\n')
            if not _esperar_archivo(ruta):
                return (
                    "ERROR: AutoCAD no llegó a escribir el DWG. Suele pasar si quedó "
                    "una orden a medias en su línea de comandos: pulsa Esc en AutoCAD "
                    "y vuelve a intentarlo."
                )
        elif formato == "dxf":
            doc.Export(str(ruta), "DXF", _conjunto_vacio(doc))
        else:
            doc.Plot.PlotToFile(str(ruta), "DWG To PDF.pc3")
            if not _esperar_archivo(ruta):
                return (
                    "ERROR: no se generó el PDF. Comprueba que el dibujo tiene una "
                    "presentación con área de trazado definida."
                )
    except Exception as exc:
        return f"ERROR exportando a {formato.upper()}: {exc}"

    if not ruta.is_file():
        return f"ERROR: AutoCAD no generó el archivo {formato.upper()}."
    return (
        f"Exportado a {formato.upper()} ({ruta.stat().st_size} bytes).\n"
        f"{entregables.MARCA} {ruta}"
    )
