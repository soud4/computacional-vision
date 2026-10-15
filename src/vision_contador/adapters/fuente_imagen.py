"""Fuente de video que entrega siempre la misma imagen ya cargada.

Sirve para procesar una fotografia guardada en lugar de la camara: repetir un
caso dificil, preparar la demostracion sin montar la mesa o comparar el efecto
del preprocesamiento sobre una imagen conocida.

La decodificacion del archivo no se hace aqui: este adaptador recibe el arreglo
RGB ya listo. Asi ``adapters`` no depende de Qt ni de OpenCV para algo que la
interfaz ya sabe hacer (``ui/imagen_qt.desde_archivo``).
"""

from __future__ import annotations

import numpy as np

from ..core.modelos import Imagen
from ..ports.camara import FuenteVideo


class FuenteImagen(FuenteVideo):
    """Una imagen fija disfrazada de camara."""

    def __init__(self, imagen: Imagen, nombre: str = "imagen") -> None:
        self._imagen = np.ascontiguousarray(imagen[..., :3].astype(np.uint8))
        self.nombre = nombre
        self._abierta = False
        #: El visor conserva el ultimo cuadro pintado, asi que la imagen se
        #: entrega una sola vez por apertura: repintar treinta veces por segundo
        #: algo que no se mueve solo gastaria CPU.
        self._pendiente = False

    # --- Ciclo de vida -----------------------------------------------------
    def abrir(self) -> None:
        self._abierta = True
        self._pendiente = True

    def cerrar(self) -> None:
        self._abierta = False

    # --- Lectura -----------------------------------------------------------
    def leer_cuadro(self) -> Imagen | None:
        if not self._abierta or not self._pendiente:
            return None
        self._pendiente = False
        return self._imagen

    def capturar_estable(self) -> Imagen:
        if not self._abierta:
            self.abrir()
        return self._imagen.copy()

    # --- Estado ------------------------------------------------------------
    @property
    def tamano(self) -> tuple[int, int]:
        """Ancho y alto de la imagen, en pixeles."""
        alto, ancho = self._imagen.shape[:2]
        return ancho, alto

    @property
    def fps(self) -> float:
        return 0.0

    @property
    def disponible(self) -> bool:
        return self._abierta
