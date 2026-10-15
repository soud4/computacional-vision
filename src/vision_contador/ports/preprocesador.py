"""Puerto del preprocesamiento de imagen."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..core.modelos import EtapaPreproc, Imagen, ParametrosPreproc


class ResultadoPreproc:
    """Las imagenes intermedias de la cadena y que etapas se aplicaron.

    ``etapas`` siempre trae las siete claves de :class:`EtapaPreproc`, aunque una
    etapa omitida devuelva la misma imagen que la anterior. Asi el desplegable
    del panel PREPROCESADA nunca se queda sin imagen que mostrar.
    """

    __slots__ = ("aplicadas", "etapas")

    def __init__(
        self,
        etapas: dict[EtapaPreproc, Imagen],
        aplicadas: dict[EtapaPreproc, bool],
    ) -> None:
        self.etapas = etapas
        self.aplicadas = aplicadas

    @property
    def final(self) -> Imagen:
        return self.etapas[EtapaPreproc.RESULTADO]


class Preprocesador(ABC):
    """Aplica la cadena de tecnicas de PDI a la imagen capturada."""

    @abstractmethod
    def procesar(self, imagen: Imagen, params: ParametrosPreproc) -> ResultadoPreproc:
        """Devuelve todas las etapas intermedias y cuales se aplicaron de verdad.

        En modo adaptativo una etapa puede quedar marcada como omitida aunque su
        casilla este activada, porque el histograma no la requeria.
        """
