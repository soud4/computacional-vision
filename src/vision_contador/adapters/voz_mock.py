"""Voz simulada: no reproduce audio, solo deja constancia de la frase."""

from __future__ import annotations

from ..ports.voz import SintetizadorVoz


class VozMock(SintetizadorVoz):
    """Guarda lo ultimo que se habria dicho, para poder comprobarlo en las pruebas."""

    def __init__(self) -> None:
        self.ultima_frase: str = ""
        self.reproducciones = 0

    def decir(self, frase: str) -> None:
        self.ultima_frase = frase
        self.reproducciones += 1

    def detener(self) -> None:
        pass

    @property
    def descripcion(self) -> str:
        return "simulada · sin audio"
