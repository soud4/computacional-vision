"""Grafico de histograma de luminancia."""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import QSizePolicy, QVBoxLayout, QWidget

from ...core.modelos import Histograma
from .. import tema


class GraficoHistograma(QWidget):
    """Las 256 barras del histograma, dibujadas como area rellena."""

    def __init__(self, color: str = tema.TEXTO, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._valores: np.ndarray | None = None
        self._color = color
        self.setMinimumHeight(62)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(62)

    def fijar(self, histograma: Histograma | None) -> None:
        self._valores = None if histograma is None else histograma.valores
        self.update()

    def paintEvent(self, evento) -> None:
        pintor = QPainter(self)
        pintor.setRenderHint(QPainter.RenderHint.Antialiasing)
        caja = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)

        pintor.setPen(QPen(QColor(tema.BORDE), 1))
        pintor.setBrush(QColor(tema.HUNDIDO))
        pintor.drawRoundedRect(caja, tema.RADIO, tema.RADIO)

        if self._valores is None:
            return

        interior = caja.adjusted(3, 3, -3, -3)
        # 256 niveles en pocos pixeles no se distinguen: se agrupan en 64 barras,
        # tomando el maximo de cada grupo para no perder los picos finos.
        grupos = self._valores.reshape(64, 4).max(axis=1)
        ancho = interior.width() / 64

        degradado = QLinearGradient(0, interior.top(), 0, interior.bottom())
        degradado.setColorAt(0.0, tema.con_alfa(self._color, 0.95))
        degradado.setColorAt(1.0, tema.con_alfa(self._color, 0.35))
        pintor.setPen(Qt.PenStyle.NoPen)
        pintor.setBrush(degradado)

        for i, valor in enumerate(grupos):
            alto = float(valor) * interior.height()
            if alto < 0.6:
                continue
            pintor.drawRect(
                QRectF(interior.left() + i * ancho, interior.bottom() - alto, max(ancho - 1, 1), alto)
            )


class TarjetaHistograma(QWidget):
    """Un histograma con su titulo y sus dos metricas debajo."""

    def __init__(self, titulo: str, color: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        from .panel import etiqueta_mono, etiqueta_sec

        columna = QVBoxLayout(self)
        columna.setContentsMargins(0, 0, 0, 0)
        columna.setSpacing(5)

        self.titulo = etiqueta_sec(titulo, 11)
        self.titulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.grafico = GraficoHistograma(color, self)
        self.brillo = etiqueta_mono("Brillo —", 11, tema.TEXTO_SEC)
        self.contraste = etiqueta_mono("Contraste —", 11, tema.TEXTO_SEC)

        columna.addWidget(self.titulo)
        columna.addWidget(self.grafico)
        columna.addWidget(self.brillo)
        columna.addWidget(self.contraste)

    def fijar(self, histograma: Histograma | None) -> None:
        self.grafico.fijar(histograma)
        if histograma is None:
            self.brillo.setText("Brillo —")
            self.contraste.setText("Contraste —")
        else:
            self.brillo.setText(f"Brillo medio: {histograma.brillo_medio:.0f}")
            self.contraste.setText(f"Contraste: {histograma.contraste:.0f}")
