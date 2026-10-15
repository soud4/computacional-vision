"""Camara simulada: entrega la escena sintetica como si fuera una webcam."""

from __future__ import annotations

import time

from ..core.modelos import Imagen
from ..ports.camara import FuenteVideo
from . import escena_demo

#: Exposicion de la toma. Por debajo de 1 la mesa queda mal iluminada, que es el
#: caso que el preprocesamiento tiene que corregir.
EXPOSICION = 0.52


class CamaraMock(FuenteVideo):
    """Genera cuadros con grano y temblor leves para que el video se vea vivo."""

    def __init__(self, fps: int = 30, exposicion: float = EXPOSICION) -> None:
        self._fps = fps
        self._exposicion = exposicion
        self._abierta = False
        self._contador = 0
        self._ultimo = 0.0
        self._foto: Imagen | None = None

    def abrir(self) -> None:
        self._abierta = True
        self._ultimo = time.perf_counter()
        # El ciclo de cuadros se construye en la primera lectura, que ocurre ya
        # en el hilo de la camara: generarlo aqui congelaria el arranque.

    def cerrar(self) -> None:
        self._abierta = False

    def leer_cuadro(self) -> Imagen | None:
        if not self._abierta:
            return None
        self._contador += 1
        ciclo = escena_demo.cuadros_vivos(self._exposicion)
        return ciclo[self._contador % len(ciclo)]

    def capturar_estable(self) -> Imagen:
        if not self._abierta:
            self.abrir()
        # La camara real descarta aqui varios cuadros del bufer; la simulada
        # imita esa pausa para que la secuencia tenga el mismo ritmo.
        time.sleep(0.12)
        if self._foto is None:
            self._foto = escena_demo.generar(semilla=101, exposicion=self._exposicion)
        return self._foto

    @property
    def fps(self) -> float:
        return float(self._fps)

    @property
    def disponible(self) -> bool:
        return self._abierta
