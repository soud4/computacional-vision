"""Detector simulado: devuelve las cajas conocidas de la escena de demostracion."""

from __future__ import annotations

import time

from ..core.modelos import Deteccion, Imagen
from ..ports.detector import Detector, ResultadoDeteccion
from .escena_demo import CAJAS

#: Confianzas del diseno. Son fijas a proposito: la demostracion tiene que dar
#: siempre el mismo resultado para poder compararla con el mockup.
CONFIANZAS = {
    "bottle": 0.91,
    "cup": 0.87,
    "cell phone": 0.94,
    "book": 0.78,
}

#: Lo que tarda un YOLO11n en una laptop sin GPU, aproximadamente.
MS_INFERENCIA = 182


class DetectorMock(Detector):
    """Simula una pasada de YOLO sobre la escena de demostracion."""

    def __init__(self, nombre: str = "YOLO11n", ms: int = MS_INFERENCIA) -> None:
        self._nombre = nombre
        self._ms = ms
        self._listo = False
        #: Permite forzar el caso "sin detecciones" desde los atajos de la demo.
        self.sin_detecciones = False

    def cargar(self) -> None:
        time.sleep(0.05)
        self._listo = True

    def detectar(self, imagen: Imagen, confianza_minima: float) -> ResultadoDeteccion:
        if not self._listo:
            self.cargar()
        time.sleep(self._ms / 1000.0)

        if self.sin_detecciones:
            return ResultadoDeteccion([], self._ms, self._nombre)

        alto, ancho = imagen.shape[:2]
        escala_x = ancho / 1280.0
        escala_y = alto / 720.0
        detecciones = [
            Deteccion(
                clase=clase,
                confianza=CONFIANZAS[clase],
                caja=_escalar(CAJAS[clase], escala_x, escala_y),
            )
            for clase in CAJAS
            if CONFIANZAS[clase] >= confianza_minima
        ]
        return ResultadoDeteccion(detecciones, self._ms, self._nombre)

    @property
    def nombre(self) -> str:
        return self._nombre

    @property
    def listo(self) -> bool:
        return self._listo


def _escalar(caja, ex: float, ey: float):
    from ..core.modelos import Rect

    return Rect(
        int(caja.x * ex), int(caja.y * ey), int(caja.ancho * ex), int(caja.alto * ey)
    )
