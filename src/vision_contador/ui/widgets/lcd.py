"""Representacion de una pantalla LCD 16x2 con caracteres de matriz de puntos."""

from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from .. import tema

COLUMNAS = 16
FILAS = 2

#: Verde amarillento retroiluminado, el de las LCD HD44780 mas comunes.
FONDO = "#8FB63A"
FONDO_CELDA = "#9CC247"
TINTA = "#16240A"
MARCO = "#1A1A1A"   # el marco del modulo, neutro; la pantalla conserva su verde


class PantallaLcd(QWidget):
    """Dibuja las 16x2 celdas con su rejilla, como la pantalla fisica."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._filas = ["", ""]
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(96)

    def fijar(self, fila1: str = "", fila2: str = "") -> None:
        """Las filas se recortan a 16 caracteres, como en el hardware."""
        self._filas = [fila1[:COLUMNAS], fila2[:COLUMNAS]]
        self.update()

    @property
    def filas(self) -> list[str]:
        return list(self._filas)

    def sizeHint(self) -> QSize:
        return QSize(380, 96)

    def paintEvent(self, evento) -> None:
        pintor = QPainter(self)
        pintor.setRenderHint(QPainter.RenderHint.Antialiasing)
        marco = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)

        pintor.setPen(QPen(QColor(tema.HUNDIDO), 1))
        pintor.setBrush(QColor(MARCO))
        pintor.drawRoundedRect(marco, tema.RADIO, tema.RADIO)

        area = marco.adjusted(9, 9, -9, -9)
        pintor.setPen(Qt.PenStyle.NoPen)
        pintor.setBrush(QColor(FONDO))
        pintor.drawRoundedRect(area, tema.RADIO_CHICO, tema.RADIO_CHICO)

        ancho_celda = area.width() / COLUMNAS
        alto_celda = area.height() / FILAS

        fuente = QFont("Consolas")
        fuente.setStyleHint(QFont.StyleHint.Monospace)
        fuente.setPixelSize(int(alto_celda * 0.56))
        fuente.setWeight(QFont.Weight.Bold)
        pintor.setFont(fuente)

        for fila in range(FILAS):
            texto = self._filas[fila].ljust(COLUMNAS)
            for columna in range(COLUMNAS):
                celda = QRectF(
                    area.left() + columna * ancho_celda,
                    area.top() + fila * alto_celda,
                    ancho_celda,
                    alto_celda,
                ).adjusted(1, 2, -1, -2)
                # La celda apagada se ve apenas mas clara que el fondo, igual que
                # la matriz de puntos de una LCD real con la luz encendida.
                pintor.setPen(Qt.PenStyle.NoPen)
                pintor.setBrush(QColor(FONDO_CELDA))
                pintor.drawRect(celda)

                caracter = texto[columna]
                if caracter != " ":
                    pintor.setPen(QColor(TINTA))
                    pintor.drawText(celda, Qt.AlignmentFlag.AlignCenter, caracter)
