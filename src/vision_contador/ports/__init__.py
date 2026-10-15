"""Puertos: las interfaces abstractas del sistema.

Cada puerto describe *que* necesita el nucleo de un recurso externo, sin decir
*como* se consigue. Por cada puerto hay al menos dos adaptadores en
``vision_contador.adapters``: uno simulado y uno real.
"""

from .camara import FuenteVideo
from .detector import Detector
from .enlace_arduino import EnlaceArduino, EscuchaArduino
from .preprocesador import Preprocesador
from .voz import SintetizadorVoz

__all__ = [
    "Detector",
    "EnlaceArduino",
    "EscuchaArduino",
    "FuenteVideo",
    "Preprocesador",
    "SintetizadorVoz",
]
