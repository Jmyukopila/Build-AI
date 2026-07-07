"""Agente de BuildAI: bucle de conversación con uso de herramientas.

El agente recibe el mensaje del usuario, consulta al modelo de IA y ejecuta
las herramientas de los conectores (Blender, AutoCAD, SketchUp, Revit) hasta
que el modelo da una respuesta final. Emite eventos para que la interfaz
muestre el progreso en tiempo real.
"""

from . import config as cfg
from .connectors import CONECTORES, buscar_herramienta
from .providers import crear_proveedor, ErrorProveedor

MAX_PASOS = 60
MAX_HISTORIAL = 120  # entradas; al superarlo se olvidan los turnos más antiguos

# Límites de tamaño de los resultados de herramientas. Sin ellos, una tarea
# larga desborda el contexto de los modelos gratuitos/locales y cada petición
# se vuelve más pesada (y más propensa a límites de uso).
MAX_RESULTADO = 8000          # caracteres conservados de un resultado recién ejecutado
RESULTADO_ANTIGUO_MAX = 600   # a lo que se comprime un resultado ya viejo
ENTRADAS_SIN_COMPRIMIR = 24   # entradas recientes cuyos resultados no se tocan

SISTEMA_BASE = """Eres BuildAI, un asistente de IA experto en arquitectura para arquitectos.
Trabajas en español, con un tono claro y cercano, para personas que NO saben
programar: nunca les pidas que escriban código ni uses jerga técnica al
explicarte.

## Tu base de conocimiento de arquitectura

Estas son tus referencias de diseño: aplícalas siempre como tu criterio experto
en vez de otros valores que puedas recordar de tu entrenamiento (para ser
consistente sin importar qué modelo de IA seas en cada momento). Son valores
de referencia habituales (aprox. según el Código Técnico de la Edificación
español y estándares internacionales de uso común); varían según el país y la
normativa local, así que en un proyecto real que vaya a construirse, recuerda
avisar de que hay que verificarlos con la normativa vigente del lugar.

Programa y dimensiones habituales (vivienda):
- Altura libre entre forjados: 2,50–2,70 m (en pasillos puede bajar a 2,20 m).
- Espesores: muro exterior 20–30 cm (con aislamiento), muro de carga interior
  15–20 cm, tabique divisorio sin carga 7–12 cm.
- Puertas: paso libre 70–80 cm en habitaciones, 80–90 cm en entrada principal y
  accesos accesibles; alto estándar 200–210 cm.
- Ventanas: antepecho a 90–100 cm del suelo en dormitorios/salones; superficie
  de iluminación ≈ 1/10 de la superficie útil de la estancia, ventilación ≈ 1/20.
- Superficies mínimas orientativas: dormitorio individual ≥ 6 m², doble ≥ 10 m²;
  salón-comedor ≥ 14–16 m²; cocina ≥ 5–7 m²; baño completo ≥ 3,5 m².
- Cocina: encimera a 85–90 cm de alto, con ≥ 60 cm de fondo libre de paso frente
  a los muebles.

Circulación y accesibilidad:
- Pasillos: ancho mínimo 90–100 cm (120 cm si debe cruzar una silla de ruedas).
- Escaleras: huella 28–30 cm, contrahuella 17–18 cm (cómodo: 2×contrahuella +
  huella ≈ 62–64 cm); ancho mínimo 100–110 cm; pasamanos a 90–110 cm de alto.
- Rampas accesibles: pendiente máxima 8–10 % en tramos cortos (6 % en tramos
  largos); ancho mínimo 120 cm.
- Accesibilidad en silla de ruedas: puertas con 80 cm libres mínimo y espacio de
  giro de 150 cm de diámetro en baños/estancias accesibles.

Estructura (órdenes de magnitud; nunca sustituye un cálculo estructural real):
- Luces habituales sin apoyos intermedios: forjado de hormigón 4–6 m; vigas de
  madera o acero hasta 6–8 m, con canto aproximado de luz/12 a luz/20 según
  material y carga.
- Cubiertas inclinadas: pendiente a dos aguas habitual 25–35 % (≈14–19°) en teja
  cerámica; cubiertas planas con pendiente mínima 1–2 % para evacuar el agua.
- Para cualquier dimensionado estructural definitivo, indica que lo debe validar
  un ingeniero o arquitecto colegiado: tú das órdenes de magnitud de diseño, no
  cálculo estructural certificable.

Confort y diseño bioclimático:
- Hemisferio norte: orienta estancias principales (salón, dormitorios) a
  sur/sureste para aprovechar el sol de invierno; cocina/baños pueden ir a
  norte/este. En hemisferio sur, invierte la orientación. Si no sabes el
  hemisferio y la orientación importa para la tarea, pregúntalo.
- Ventilación cruzada: aberturas en fachadas opuestas o en ángulo, no solo en
  una misma pared.
- Aleros/voladizos de 60–90 cm protegen huecos sur del sol alto de verano sin
  bloquear el sol bajo de invierno.

Convenciones de dibujo y BIM al usar los programas:
- Organiza por capas/función (muros, puertas, ventanas, acotación, textos,
  mobiliario) con nombres claros y consistentes.
- Acotación: cotas generales por fachada + cotas parciales de huecos.
- Escala habitual de planos de vivienda: 1:50 o 1:100 (1:200 para conjuntos).
- Si el usuario no da medidas para un elemento en 3D/2D, usa por defecto: muro
  exterior 20 cm de espesor y 2,70 m de alto, puerta interior 80×205 cm, salvo
  que el contexto pida otra cosa.

Cuando apliques un valor por defecto de esta lista (porque el usuario no dio
una medida concreta), dilo brevemente al resumir el resultado, para que el
usuario sepa qué asumiste y pueda corregirlo.

## Herramientas

Puedes controlar programas de arquitectura mediante herramientas. Programas
conectados ahora mismo: {programas}.

Normas de trabajo:
- Antes de modificar un modelo o dibujo, consulta su estado con la herramienta
  de información correspondiente.
- Haz los cambios en pasos pequeños y verifica el resultado tras cada paso.
- Usa unidades métricas (metros o milímetros según el programa) salvo que el
  usuario indique otra cosa.
- Si una herramienta devuelve ERROR, lee el mensaje, corrige el código y
  reintenta (máximo 3 intentos); si no lo consigues, explica el problema en
  lenguaje sencillo.
- Si el usuario pide algo de un programa que no está conectado, dile con qué
  programas puedes trabajar ahora y cómo conectar el que falta (hay un botón
  de ayuda junto a cada programa en la barra lateral).
- Al terminar, resume en 2-3 frases qué has hecho, sin tecnicismos.
- Nunca borres trabajo del usuario sin confirmárselo antes."""


def _sistema(conectados: list) -> str:
    if conectados:
        nombres = ", ".join(c.nombre for c in conectados)
    else:
        nombres = "ninguno (puedes conversar y aconsejar, pero no tocar modelos)"
    return SISTEMA_BASE.format(programas=nombres)


def _herramientas(conectados: list) -> list:
    lista = []
    for conector in conectados:
        lista.extend(conector.herramientas())
    return lista


def _recortar_historial(historial: list) -> None:
    """Olvida los turnos más antiguos cuando la conversación crece demasiado.

    Se corta siempre al inicio de un turno de usuario: partir un turno dejaría
    llamadas a herramientas sin su resultado y el proveedor rechazaría la petición.
    """
    while len(historial) > MAX_HISTORIAL:
        corte = next(
            (i for i in range(1, len(historial)) if historial[i]["tipo"] == "usuario"),
            None,
        )
        if corte is None:
            break
        del historial[:corte]


def _comprimir_resultados(historial: list) -> None:
    """Recorta resultados de herramienta antiguos para no agotar el contexto.

    Se conservan íntegras las últimas entradas (las que el modelo necesita para
    el paso actual); lo demás ya fue procesado y basta con un extracto.
    """
    for m in historial[:-ENTRADAS_SIN_COMPRIMIR]:
        if m["tipo"] == "resultado" and len(m["contenido"]) > RESULTADO_ANTIGUO_MAX:
            m["contenido"] = (
                m["contenido"][:RESULTADO_ANTIGUO_MAX]
                + "\n… (resultado antiguo recortado; consulta de nuevo el programa si necesitas el detalle)"
            )


def ejecutar_turno(historial: list, mensaje_usuario: str, emitir, cancelado=None) -> None:
    """Procesa un turno completo del usuario.

    `emitir(evento: dict)` recibe eventos:
      {"tipo": "estado", "texto"}         — qué está haciendo el agente
      {"tipo": "herramienta", "programa", "nombre", "detalle"}
      {"tipo": "respuesta", "texto"}      — texto final del asistente
      {"tipo": "error", "texto"}
    `cancelado()` (opcional) devuelve True si el usuario pidió detener la tarea;
    se comprueba entre pasos para no dejar herramientas sin resultado.
    El historial se modifica in situ (formato neutro de providers.base).
    """
    configuracion = cfg.cargar()
    try:
        proveedor = crear_proveedor(configuracion)
    except ErrorProveedor as exc:
        emitir({"tipo": "error", "texto": str(exc)})
        return
    # El proveedor avisa por aquí de esperas y reintentos (429, cortes…)
    proveedor.notificar = lambda texto: emitir({"tipo": "estado", "texto": texto})

    conectados = [c for c in CONECTORES if c.disponible()]
    sistema = _sistema(conectados)
    herramientas = _herramientas(conectados)

    historial.append({"tipo": "usuario", "texto": mensaje_usuario})
    _recortar_historial(historial)

    for _ in range(MAX_PASOS):
        if cancelado and cancelado():
            emitir({"tipo": "respuesta", "texto": "He detenido la tarea donde me lo pediste. Los pasos ya completados se mantienen."})
            return
        _comprimir_resultados(historial)
        emitir({"tipo": "estado", "texto": "Pensando…"})
        try:
            respuesta = proveedor.conversar(sistema, historial, herramientas)
        except ErrorProveedor as exc:
            emitir({"tipo": "error", "texto": str(exc)})
            return
        except Exception as exc:  # error inesperado: no tumbar el servidor
            emitir({"tipo": "error", "texto": f"Error inesperado del proveedor: {exc}"})
            return

        historial.append(
            {
                "tipo": "asistente",
                "texto": respuesta.texto,
                "llamadas": respuesta.llamadas,
                "_raw": respuesta.raw,
            }
        )

        if not respuesta.llamadas:
            emitir({"tipo": "respuesta", "texto": respuesta.texto or "(sin respuesta)"})
            return

        if respuesta.texto:
            # Comentario intermedio del modelo mientras trabaja
            emitir({"tipo": "respuesta", "texto": respuesta.texto})

        for llamada in respuesta.llamadas:
            encontrada = buscar_herramienta(llamada.nombre)
            if encontrada is None:
                resultado = f"ERROR: la herramienta '{llamada.nombre}' no existe."
                programa = "?"
            else:
                conector, _ = encontrada
                programa = conector.nombre
                emitir(
                    {
                        "tipo": "herramienta",
                        "programa": programa,
                        "nombre": llamada.nombre,
                        "detalle": str(llamada.argumentos.get("codigo") or llamada.argumentos.get("orden") or "")[:400],
                    }
                )
                try:
                    resultado = conector.ejecutar(llamada.nombre, llamada.argumentos)
                except Exception as exc:
                    resultado = f"ERROR inesperado ejecutando la herramienta: {exc}"
            if len(resultado) > MAX_RESULTADO:
                resultado = (
                    resultado[:MAX_RESULTADO]
                    + "\n… (salida recortada por ser demasiado larga)"
                )
            historial.append(
                {
                    "tipo": "resultado",
                    "id": llamada.id,
                    "nombre": llamada.nombre,
                    "contenido": resultado,
                }
            )

    # Límite de pasos alcanzado: no es un fallo, es una pausa de seguridad.
    # El historial queda completo (cada herramienta con su resultado), así que
    # el usuario puede reanudar la tarea exactamente donde quedó.
    aviso = (
        f"He completado {MAX_PASOS} pasos y la tarea aún no ha terminado, "
        "así que hago una pausa de seguridad. Todo lo avanzado se conserva: "
        "escribe «continúa» y sigo justo donde lo dejé."
    )
    historial.append({"tipo": "asistente", "texto": aviso, "llamadas": [], "_raw": None})
    emitir({"tipo": "respuesta", "texto": aviso})
