"""Puerto del detector de objetos."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..core.modelos import Deteccion, Imagen


class ResultadoDeteccion:
    """Lo que devuelve un detector: las cajas y cuanto tardo."""

    __slots__ = ("detecciones", "modelo", "ms")

    def __init__(self, detecciones: list[Deteccion], ms: int, modelo: str) -> None:
        self.detecciones = detecciones
        self.ms = ms
        self.modelo = modelo


class Detector(ABC):
    """Detecta y clasifica objetos en una imagen.

    Las tres implementaciones (simulada, YOLO local y API en la nube) son
    intercambiables desde ``config/default.toml`` sin tocar la interfaz.
    """

    @abstractmethod
    def cargar(self) -> None:
        """Carga los pesos o abre la sesion. Puede tardar varios segundos."""

    @abstractmethod
    def detectar(self, imagen: Imagen, confianza_minima: float) -> ResultadoDeteccion:
        """Devuelve las detecciones que superan el umbral de confianza."""

    @property
    @abstractmethod
    def nombre(self) -> str:
        """Nombre que se muestra en la barra superior: 'YOLO11n'."""

    @property
    @abstractmethod
    def listo(self) -> bool:
        """True si ``cargar`` ya termino con exito."""


class DetectorNoDisponible(RuntimeError):
    """No se pudieron cargar los pesos o la API no respondio."""
