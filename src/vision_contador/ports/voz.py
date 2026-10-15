"""Puerto de la sintesis de voz."""

from __future__ import annotations

from abc import ABC, abstractmethod


class SintetizadorVoz(ABC):
    """Convierte la frase generada en audio y la reproduce por los parlantes."""

    @abstractmethod
    def decir(self, frase: str) -> None:
        """Reproduce la frase. No bloquea el hilo que la llama.

        Las implementaciones cachean el audio por frase: en el aula la misma
        frase se repite mucho y no conviene depender de la red en cada captura.
        """

    @abstractmethod
    def detener(self) -> None:
        """Corta la reproduccion en curso."""

    @property
    @abstractmethod
    def descripcion(self) -> str:
        """Texto para la etiqueta de la tarjeta: 'edge-tts · desde cache'."""
