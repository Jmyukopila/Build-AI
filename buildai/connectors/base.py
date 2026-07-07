"""Base común de los conectores.

Un conector expone:
  - disponible(): ¿el programa está abierto y responde?
  - herramientas(): lista de herramientas para el agente de IA
    [{nombre, descripcion, parametros(JSON Schema)}]
  - ejecutar(nombre, argumentos): ejecuta la herramienta y devuelve texto
"""

MAX_SALIDA = 12000  # caracteres máximos devueltos al modelo


def recortar(texto: str, limite: int = MAX_SALIDA) -> str:
    texto = str(texto)
    if len(texto) > limite:
        return texto[:limite] + f"\n... (salida recortada, {len(texto)} caracteres en total)"
    return texto


class Conector:
    id = ""
    nombre = ""
    icono = ""
    ayuda = ""  # instrucciones de conexión mostradas al usuario

    def disponible(self) -> bool:
        raise NotImplementedError

    def herramientas(self) -> list:
        raise NotImplementedError

    def ejecutar(self, nombre: str, argumentos: dict) -> str:
        raise NotImplementedError
