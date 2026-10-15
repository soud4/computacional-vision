"""Adaptadores: las implementaciones concretas de cada puerto.

Por cada puerto hay una implementacion simulada, que no necesita hardware ni
red, y una real. La fabrica de ``vision_contador.fabrica`` decide cual se usa
segun ``[general].modo`` de la configuracion.

Los enlaces con las placas estan partidos en dos: ``enlace_lineas`` tiene el
protocolo, y ``enlace_serie`` y ``enlace_tcp`` solo el medio por el que viaja.
"""

from .arduino_mock import ArduinoMock
from .camara_mock import CamaraMock
from .detector_mock import DetectorMock
from .fuente_conmutable import FuenteConmutable
from .fuente_imagen import FuenteImagen
from .preproc_numpy import PreprocesadorNumpy
from .voz_mock import VozMock

__all__ = [
    "ArduinoMock",
    "CamaraMock",
    "DetectorMock",
    "FuenteConmutable",
    "FuenteImagen",
    "PreprocesadorNumpy",
    "VozMock",
]
