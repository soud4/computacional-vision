"""Generacion de la frase en espanol y de las dos filas de la LCD."""

from __future__ import annotations

from ..core.modelos import ConteoClase
from .lexico import entrada

#: Numerales en palabras. Por encima de veinte se usa la cifra, que al oido
#: funciona igual de bien y evita arrastrar un conversor completo.
_NUMEROS = {
    1: ("un", "una"),
    2: ("dos", "dos"),
    3: ("tres", "tres"),
    4: ("cuatro", "cuatro"),
    5: ("cinco", "cinco"),
    6: ("seis", "seis"),
    7: ("siete", "siete"),
    8: ("ocho", "ocho"),
    9: ("nueve", "nueve"),
    10: ("diez", "diez"),
    11: ("once", "once"),
    12: ("doce", "doce"),
    13: ("trece", "trece"),
    14: ("catorce", "catorce"),
    15: ("quince", "quince"),
    16: ("dieciséis", "dieciséis"),
    17: ("diecisiete", "diecisiete"),
    18: ("dieciocho", "dieciocho"),
    19: ("diecinueve", "diecinueve"),
    20: ("veinte", "veinte"),
}

SIN_OBJETOS = "No se detectaron objetos en la imagen"


def _numeral(cantidad: int, femenino: bool) -> str:
    palabras = _NUMEROS.get(cantidad)
    if palabras is None:
        return str(cantidad)
    return palabras[1 if femenino else 0]


def sintagma(conteo: ConteoClase) -> str:
    """Un grupo nominal con concordancia: 'una botella', 'dos celulares'."""
    ent = entrada(conteo.clase)
    numeral = _numeral(conteo.cantidad, ent.femenino)
    sustantivo = ent.singular if conteo.cantidad == 1 else ent.plural
    return f"{numeral} {sustantivo}"


def _enumerar(partes: list[str]) -> str:
    """Une con comas y una 'y' final, como se dice en voz alta."""
    if not partes:
        return ""
    if len(partes) == 1:
        return partes[0]
    return f"{', '.join(partes[:-1])} y {partes[-1]}"


def generar(conteos: list[ConteoClase]) -> str:
    """La frase que se reproduce por los parlantes.

    Un solo objeto lleva el verbo en singular ('Se detectó una botella'); varios,
    en plural.
    """
    if not conteos:
        return SIN_OBJETOS
    total = sum(c.cantidad for c in conteos)
    verbo = "Se detectó" if total == 1 else "Se detectaron"
    return f"{verbo} {_enumerar([sintagma(c) for c in conteos])}"


def fila_lcd_total(conteos: list[ConteoClase]) -> str:
    """Primera fila de la LCD: 'Total: 4 objetos' (16 caracteres como maximo)."""
    total = sum(c.cantidad for c in conteos)
    if total == 0:
        return "Sin objetos"
    sustantivo = "objeto" if total == 1 else "objetos"
    return f"Total: {total} {sustantivo}"[:16]


def fila_lcd_detalle(conteos: list[ConteoClase], columnas: int = 16) -> str:
    """Segunda fila de la LCD: abreviaturas que entren en 16 caracteres.

    La pantalla tiene 16 columnas fisicas, asi que ``Bot1 Taz1 Cel1 Lib1`` (19)
    no cabe. Se prueban abreviaturas de 3, 2 y 1 letra y se usa la mas larga que
    quepa entera; si ni con una letra alcanza, se recortan las clases menos
    numerosas y la ultima posicion indica cuantas quedaron fuera.
    """
    if not conteos:
        return ""

    for ancho in (3, 2, 1):
        linea = " ".join(
            f"{entrada(c.clase).abreviatura[:ancho]}{c.cantidad}" for c in conteos
        )
        if len(linea) <= columnas:
            return linea

    piezas: list[str] = []
    for i, conteo in enumerate(conteos):
        pieza = f"{entrada(conteo.clase).abreviatura[:1]}{conteo.cantidad}"
        sufijo = f" +{len(conteos) - i - 1}" if i + 1 < len(conteos) else ""
        if len(" ".join([*piezas, pieza])) + len(sufijo) > columnas:
            return " ".join([*piezas, f"+{len(conteos) - i}"])[:columnas]
        piezas.append(pieza)
    return " ".join(piezas)[:columnas]
