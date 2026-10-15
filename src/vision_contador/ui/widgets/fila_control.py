"""Fila de deslizador con etiqueta y valor numerico a la derecha."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QSlider, QVBoxLayout, QWidget

from .. import tema
from .panel import etiqueta_mono, etiqueta_sec


class FilaDeslizador(QWidget):
    """Un parametro: nombre arriba a la izquierda, valor arriba a la derecha.

    El deslizador de Qt solo maneja enteros, asi que los valores con decimales
    se guardan multiplicados por ``escala`` y se dividen al leerlos.
    """

    valor_cambiado = Signal(float)

    def __init__(
        self,
        nombre: str,
        minimo: float,
        maximo: float,
        valor: float,
        paso: float = 0.01,
        formato: Callable[[float], str] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._escala = round(1 / paso)
        self._formato = formato or (lambda v: f"{v:.2f}")

        columna = QVBoxLayout(self)
        columna.setContentsMargins(0, 0, 0, 0)
        columna.setSpacing(4)

        cabecera = QHBoxLayout()
        cabecera.setContentsMargins(0, 0, 0, 0)
        self.nombre = etiqueta_sec(nombre, 12)
        self.valor = etiqueta_mono(self._formato(valor), 12, tema.TEXTO)
        cabecera.addWidget(self.nombre)
        cabecera.addStretch(1)
        cabecera.addWidget(self.valor)

        self.deslizador = QSlider(Qt.Orientation.Horizontal, self)
        self.deslizador.setMinimum(round(minimo * self._escala))
        self.deslizador.setMaximum(round(maximo * self._escala))
        self.deslizador.setSingleStep(1)
        self.deslizador.setValue(round(valor * self._escala))
        self.deslizador.valueChanged.connect(self._al_mover)

        columna.addLayout(cabecera)
        columna.addWidget(self.deslizador)

    def _al_mover(self, crudo: int) -> None:
        valor = crudo / self._escala
        self.valor.setText(self._formato(valor))
        self.valor_cambiado.emit(valor)

    def valor_actual(self) -> float:
        return self.deslizador.value() / self._escala

    def fijar_valor(self, valor: float) -> None:
        self.deslizador.setValue(round(valor * self._escala))


class FilaDiscreta(FilaDeslizador):
    """Deslizador que solo admite unos pocos valores, como el kernel 3/5/7."""

    def __init__(
        self,
        nombre: str,
        opciones: list[int],
        valor: int,
        formato: Callable[[float], str] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        self._opciones = opciones
        indice = opciones.index(valor) if valor in opciones else 0
        super().__init__(
            nombre, 0, len(opciones) - 1, indice, paso=1,
            formato=formato or (lambda v: str(opciones[int(v)])),
            parent=parent,
        )
        self.deslizador.setPageStep(1)
        self.deslizador.setTickPosition(QSlider.TickPosition.NoTicks)

    def valor_actual(self) -> int:  # type: ignore[override]
        return self._opciones[int(self.deslizador.value())]

    def fijar_valor(self, valor: float) -> None:
        entero = int(valor)
        if entero in self._opciones:
            self.deslizador.setValue(self._opciones.index(entero))
