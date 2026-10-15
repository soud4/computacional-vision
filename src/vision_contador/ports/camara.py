"""Puerto de la fuente de video."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..core.modelos import Imagen


class FuenteVideo(ABC):
    """De donde salen los cuadros de video y la foto de la captura."""

    @abstractmethod
    def abrir(self) -> None:
        """Reserva la camara. Lanza ``CamaraNoDisponible`` si no se puede."""

    @abstractmethod
    def leer_cuadro(self) -> Imagen | None:
        """Devuelve el siguiente cuadro para el panel VIDEO EN VIVO, o None."""

    @abstractmethod
    def capturar_estable(self) -> Imagen:
        """Toma la foto definitiva.

        La implementacion real descarta primero varios cuadros del bufer: la
        camara entrega imagenes viejas y sin ese descarte se fotografia la
        escena anterior al pulsador.
        """

    @abstractmethod
    def cerrar(self) -> None:
        """Libera la camara."""

    @property
    @abstractmethod
    def fps(self) -> float:
        """Cuadros por segundo que se estan entregando de verdad."""

    @property
    @abstractmethod
    def disponible(self) -> bool:
        """True si la camara esta abierta y entregando cuadros."""


class CamaraNoDisponible(RuntimeError):
    """No se pudo abrir la camara o dejo de entregar cuadros."""
