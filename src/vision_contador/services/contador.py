"""Conteo de objetos por clase."""

from __future__ import annotations

from collections import Counter

from ..core.modelos import ConteoClase, Deteccion
from .lexico import nombre_es


def filtrar(detecciones: list[Deteccion], confianza_minima: float) -> list[Deteccion]:
    """Descarta las detecciones que no llegan al umbral de confianza."""
    return [d for d in detecciones if d.confianza >= confianza_minima]


def contar(detecciones: list[Deteccion]) -> list[ConteoClase]:
    """Agrupa por clase y devuelve los conteos.

    El orden es por cantidad descendente y, a igualdad, el de la primera
    aparicion en la lista de detecciones. Desempatar por orden alfabetico seria
    mas simple, pero reordenaria la frase hablada respecto de como el detector
    recorrio la escena; asi la lista y la frase siguen el mismo orden que las
    cajas dibujadas.
    """
    nombres = [nombre_es(d.clase) for d in detecciones]
    cuenta = Counter(nombres)
    aparicion = {nombre: i for i, nombre in enumerate(reversed(nombres))}
    ordenado = sorted(
        cuenta.items(), key=lambda par: (-par[1], -aparicion[par[0]])
    )
    return [ConteoClase(clase=clase, cantidad=cantidad) for clase, cantidad in ordenado]


def total(conteos: list[ConteoClase]) -> int:
    return sum(c.cantidad for c in conteos)
