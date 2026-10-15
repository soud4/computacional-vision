"""Fuente de video que se puede cambiar en caliente.

La ventana construye una sola vez sus dependencias y guarda la camara en
``Dependencias.camara``; el hilo de video lee de esa misma instancia desde su
propio hilo. Para poder pasar de la webcam a una imagen de archivo o a la camara
del celular sin reiniciar nada, lo que se guarda es esta envoltura: la fuente de
verdad vive dentro y se sustituye bajo cerrojo.
"""

from __future__ import annotations

import threading

from ..core.modelos import Imagen
from ..ports.camara import FuenteVideo


class FuenteConmutable(FuenteVideo):
    """Delega en la fuente activa y permite reemplazarla."""

    def __init__(self, fuente: FuenteVideo) -> None:
        self._fuente = fuente
        #: La fuente con la que arranco la aplicacion, para poder volver a ella
        #: sin reconstruirla.
        self.original = fuente
        self._cerrojo = threading.RLock()

    # --- Conmutacion -------------------------------------------------------
    @property
    def activa(self) -> FuenteVideo:
        with self._cerrojo:
            return self._fuente

    def cambiar(self, nueva: FuenteVideo) -> None:
        """Abre ``nueva`` y, solo si abre bien, descarta la anterior.

        El orden importa: si se cerrara primero la fuente actual y la nueva
        fallara al abrir, la aplicacion se quedaria sin ninguna.
        """
        with self._cerrojo:
            if nueva is self._fuente:
                return
            nueva.abrir()
            anterior = self._fuente
            self._fuente = nueva
            if anterior is not nueva:
                anterior.cerrar()

    # --- Puerto ------------------------------------------------------------
    def abrir(self) -> None:
        with self._cerrojo:
            self._fuente.abrir()

    def cerrar(self) -> None:
        with self._cerrojo:
            self._fuente.cerrar()

    def leer_cuadro(self) -> Imagen | None:
        with self._cerrojo:
            return self._fuente.leer_cuadro()

    def capturar_estable(self) -> Imagen:
        with self._cerrojo:
            return self._fuente.capturar_estable()

    @property
    def fps(self) -> float:
        with self._cerrojo:
            return self._fuente.fps

    @property
    def disponible(self) -> bool:
        with self._cerrojo:
            return self._fuente.disponible
