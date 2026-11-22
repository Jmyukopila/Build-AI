"""Limpieza y validación de las claves de API que pega el usuario.

Una clave copiada de una web, un PDF, un correo o un chat trae a menudo
basura que no se ve: espacios de anchura cero, espacios duros, saltos de
línea, comillas o el "Bearer " de un ejemplo de documentación. Sin limpiar,
cada caso fallaba de una forma distinta y confusa: un carácter invisible hacía
reventar httpx con un error de codificación ("Error inesperado"), un salto de
línea se reintentaba 5 veces como si fuera un corte de red y las comillas
acababan en un "clave no válida" que el usuario no entendía.
"""

import re

# Caracteres invisibles habituales al copiar y pegar: anchura cero, BOM,
# espacio duro, espacios tipográficos y marcas de dirección de texto.
_INVISIBLES = re.compile("[​‌‍⁠﻿  -   　‎‏‪-‮]")
_COMILLAS = "\"'`“”‘’«»"
# Solo nombres de variable de entorno de clave (OPENAI_API_KEY=…): una regla más
# amplia recortaría claves legítimas que terminan en "==".
_ASIGNACION = re.compile(r"^(?:export\s+)?[A-Z_][A-Z0-9_]*(?:KEY|TOKEN)[A-Z0-9_]*\s*=\s*")

# Prefijos característicos de cada proveedor, para avisar si una clave se ha
# guardado en el proveedor equivocado (el error más común al configurar).
_PREFIJOS = (
    ("sk-ant-", "anthropic"),
    ("sk-or-", "openrouter"),
    ("AIza", "gemini"),
    ("sk-", "openai"),  # el último: sk-ant- y sk-or- también empiezan por sk-
)
_NOMBRES = {
    "anthropic": "Anthropic (Claude)",
    "openrouter": "OpenRouter",
    "gemini": "Google (Gemini)",
    "openai": "OpenAI (GPT)",
}


class ClaveInvalida(ValueError):
    """La clave contiene algo que ningún proveedor acepta."""


def limpiar(texto: str) -> str:
    """Devuelve la clave sin la basura típica de copiar y pegar.

    Lanza ClaveInvalida si, ya limpia, sigue teniendo caracteres que no pueden
    ir en una cabecera HTTP (letras con tilde, espacios en medio…).
    """
    clave = _INVISIBLES.sub("", str(texto or "")).strip()
    # Quien copia de la documentación o de un .env trae a veces la línea entera.
    clave = _ASIGNACION.sub("", clave).strip()
    if clave.lower().startswith("bearer "):
        clave = clave[7:].strip()
    clave = clave.strip(_COMILLAS).strip()
    if not clave:
        return ""
    if any(c.isspace() for c in clave):
        raise ClaveInvalida(
            "La clave tiene espacios o saltos de línea en medio. Cópiala de nuevo "
            "entera, de una sola vez, desde la página del proveedor."
        )
    if not clave.isascii() or not clave.isprintable():
        raise ClaveInvalida(
            "La clave contiene caracteres que no pueden ser de una clave (tildes, "
            "símbolos especiales…). Probablemente se coló texto al copiarla: "
            "cópiala de nuevo desde la página del proveedor."
        )
    return clave


def proveedor_probable(clave: str):
    """El proveedor al que parece pertenecer la clave por su prefijo, o None."""
    for prefijo, proveedor in _PREFIJOS:
        if clave.startswith(prefijo):
            return proveedor
    return None


def aviso_proveedor(clave: str, proveedor: str):
    """Texto de aviso si la clave parece de otro proveedor; None si encaja.

    Solo se avisa entre proveedores cuyos prefijos se conocen: OpenCode Zen y
    otros no tienen un formato reconocible y no se juzgan.
    """
    probable = proveedor_probable(clave)
    if probable is None or probable == proveedor or proveedor not in _NOMBRES:
        return None
    return (
        f"Esta clave parece de {_NOMBRES[probable]}, pero la has guardado en "
        f"{_NOMBRES[proveedor]}. Elige el proveedor correcto en la lista."
    )
