"""Pestana Resultados: conteo, frase, histogramas y estado de los LEDs."""

from __future__ import annotations

from typing import ClassVar

from PySide6.QtCore import QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ...core.modelos import ConteoClase, Led, ResultadoCaptura
from .. import iconos, tema
from ..widgets.histograma import TarjetaHistograma
from ..widgets.indicadores import LedConNombre
from ..widgets.panel import Tarjeta, etiqueta_sec, separador


class MarcaClase(QWidget):
    """Muestra del gris y del trazo con que se dibuja esa clase en DETECCIÓN.

    Sirve de icono y de leyenda a la vez: repite la misma pareja de gris y
    trazo que el rectangulo sobre la imagen, que es lo que permite saber cual
    de las cajas corresponde a esta fila.
    """

    def __init__(self, color: str, trazo: Qt.PenStyle, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._color = color
        self._trazo = trazo
        self.setFixedSize(16, 14)

    def paintEvent(self, evento) -> None:
        pintor = QPainter(self)
        caja = QRectF(self.rect()).adjusted(1, 1.5, -1, -1.5)
        pintor.setRenderHint(QPainter.RenderHint.Antialiasing)
        pintor.setPen(QPen(QColor(self._color), 1.6, self._trazo))
        pintor.setBrush(tema.con_alfa(self._color, 0.16))
        pintor.drawRoundedRect(caja, 3, 3)


class FilaConteo(QWidget):
    """Una clase de la lista: marca de color, nombre y cantidad grande."""

    def __init__(
        self,
        conteo: ConteoClase,
        color: str,
        trazo: Qt.PenStyle,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        fila = QHBoxLayout(self)
        fila.setContentsMargins(0, 3, 0, 3)
        fila.setSpacing(10)

        nombre = QLabel(conteo.clase, self)
        nombre.setFont(tema.Fuentes.cuerpo(13))
        cantidad = QLabel(str(conteo.cantidad), self)
        cantidad.setFont(tema.Fuentes.monoespaciada(18, negrita=True))
        cantidad.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        cantidad.setStyleSheet(f"color: {tema.TEXTO}; background: transparent;")

        fila.addWidget(MarcaClase(color, trazo, self))
        fila.addWidget(nombre, 1)
        fila.addWidget(cantidad)


class BloqueCarga(QFrame):
    """Rectangulo gris que ocupa el sitio de un dato mientras se procesa."""

    def __init__(self, ancho: int = 0, alto: int = 14, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(alto)
        if ancho:
            self.setFixedWidth(ancho)
        else:
            self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setStyleSheet(
            f"background-color: {tema.CONTROL}; border: none;"
            f" border-radius: {tema.RADIO_CHICO}px;"
        )


class TarjetaConteo(Tarjeta):
    """CONTEO POR CLASE: la lista y la fila de total."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("CONTEO POR CLASE", parent=parent)
        self._lista = QVBoxLayout()
        self._lista.setContentsMargins(0, 0, 0, 0)
        self._lista.setSpacing(2)
        self.cuerpo.addLayout(self._lista)
        self.cuerpo.addWidget(separador())

        self.total = QFrame(self)
        fila = QHBoxLayout(self.total)
        fila.setContentsMargins(10, 7, 10, 7)
        self._texto_total = QLabel("Total: — objetos", self.total)
        self._texto_total.setFont(tema.Fuentes.cuerpo(13, negrita=True))
        fila.addWidget(self._texto_total)
        fila.addStretch(1)
        self.total.setStyleSheet(
            f"QFrame {{ background-color: {tema.CONTROL}; border: none;"
            f" border-radius: {tema.RADIO}px; }}"
            f" QLabel {{ color: {tema.TEXTO}; background: transparent; }}"
        )
        self.cuerpo.addWidget(self.total)

    def _vaciar(self) -> None:
        while self._lista.count():
            item = self._lista.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def mostrar(self, conteos: list[ConteoClase]) -> None:
        self._vaciar()
        clases = sorted({c.clase for c in conteos})
        for conteo in conteos:
            indice = clases.index(conteo.clase)
            self._lista.addWidget(
                FilaConteo(
                    conteo,
                    tema.COLORES_CAJA[indice % len(tema.COLORES_CAJA)],
                    tema.TRAZOS_CAJA[indice % len(tema.TRAZOS_CAJA)],
                    self,
                )
            )
        total = sum(c.cantidad for c in conteos)
        sustantivo = "objeto" if total == 1 else "objetos"
        self._texto_total.setText(f"Total: {total} {sustantivo}")

    def mostrar_carga(self) -> None:
        self._vaciar()
        for _ in range(4):
            fila = QWidget(self)
            caja = QHBoxLayout(fila)
            caja.setContentsMargins(0, 4, 0, 4)
            caja.setSpacing(10)
            caja.addWidget(BloqueCarga(14, 14, fila))
            caja.addWidget(BloqueCarga(0, 12, fila), 1)
            caja.addWidget(BloqueCarga(22, 16, fila))
            self._lista.addWidget(fila)
        self._texto_total.setText("Total: — objetos")

    def limpiar(self) -> None:
        self._vaciar()
        self._texto_total.setText("Total: — objetos")


class TarjetaFrase(Tarjeta):
    """FRASE GENERADA: el texto entre comillas y el boton de reproducir."""

    reproducir = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("FRASE GENERADA", parent=parent)

        self.texto = QLabel("—", self)
        self.texto.setWordWrap(True)
        self.texto.setFont(tema.Fuentes.cuerpo(14))
        self.texto.setStyleSheet(f"color: {tema.TEXTO}; background: transparent;")
        self.texto.setMinimumHeight(40)

        self.carga = BloqueCarga(0, 14, self)
        self.carga.setVisible(False)

        fila = QHBoxLayout()
        fila.setSpacing(10)
        self.boton = QPushButton("Reproducir", self)
        self.boton.setIcon(iconos.altavoz(16))
        self.boton.setIconSize(QSize(16, 16))
        self.boton.setCursor(Qt.CursorShape.PointingHandCursor)
        self.boton.clicked.connect(self.reproducir)
        self.detalle = etiqueta_sec("Voz: —", 11)
        fila.addWidget(self.boton)
        fila.addWidget(self.detalle, 1)

        self.cuerpo.addWidget(self.texto)
        self.cuerpo.addWidget(self.carga)
        self.cuerpo.addLayout(fila)

    def mostrar(self, frase: str, detalle_voz: str) -> None:
        self.carga.setVisible(False)
        self.texto.setVisible(True)
        self.texto.setText(f"«{frase}»")
        self.detalle.setText(f"Voz: {detalle_voz}")
        self.boton.setEnabled(True)

    def mostrar_carga(self) -> None:
        self.texto.setVisible(False)
        self.carga.setVisible(True)
        self.boton.setEnabled(False)

    def limpiar(self) -> None:
        self.carga.setVisible(False)
        self.texto.setVisible(True)
        self.texto.setText("—")
        self.boton.setEnabled(False)


class TarjetaHistogramas(Tarjeta):
    """HISTOGRAMA DE LUMINANCIA: antes y despues, uno al lado del otro."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("HISTOGRAMA DE LUMINANCIA", parent=parent)
        fila = QHBoxLayout()
        fila.setSpacing(12)
        self.antes = TarjetaHistograma("Antes", tema.TEXTO_SEC, self)
        self.despues = TarjetaHistograma("Después", tema.TEXTO, self)
        fila.addWidget(self.antes, 1)
        fila.addWidget(self.despues, 1)
        self.cuerpo.addLayout(fila)

    def mostrar(self, resultado: ResultadoCaptura) -> None:
        self.antes.fijar(resultado.histograma_antes)
        self.despues.fijar(resultado.histograma_despues)

    def limpiar(self) -> None:
        self.antes.fijar(None)
        self.despues.fijar(None)


class TarjetaLeds(Tarjeta):
    """ESTADO DE LOS LEDS: reflejo de lo que esta encendido en la protoboard."""

    #: Los LEDs conservan el color del componente real: son el espejo de lo
    #: que esta encendido en la protoboard, no una decoracion de la interfaz.
    COLORES: ClassVar[dict[Led, str]] = {
        Led.AMARILLO: tema.LED_AMARILLO,
        Led.VERDE: tema.LED_VERDE,
        Led.ROJO: tema.LED_ROJO,
    }

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("ESTADO DE LOS LEDS", parent=parent)
        fila = QHBoxLayout()
        fila.setSpacing(0)
        self.leds: dict[Led, LedConNombre] = {}
        for led in Led:
            widget = LedConNombre(led.etiqueta, self.COLORES[led], 32, self)
            self.leds[led] = widget
            fila.addStretch(1)
            fila.addWidget(widget)
        fila.addStretch(1)
        self.cuerpo.addLayout(fila)

    def mostrar(self, encendidos: dict[Led, bool]) -> None:
        for led, widget in self.leds.items():
            widget.encender(encendidos.get(led, False))


class TabResultados(QWidget):
    """La pestana completa."""

    reproducir = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        columna = QVBoxLayout(self)
        columna.setContentsMargins(12, 12, 12, 12)
        columna.setSpacing(12)

        self.conteo = TarjetaConteo(self)
        self.frase = TarjetaFrase(self)
        self.histogramas = TarjetaHistogramas(self)
        self.leds = TarjetaLeds(self)
        self.frase.reproducir.connect(self.reproducir)

        for tarjeta in (self.conteo, self.frase, self.histogramas, self.leds):
            columna.addWidget(tarjeta)
        columna.addStretch(1)

        self.limpiar()

    def mostrar(self, resultado: ResultadoCaptura, detalle_voz: str) -> None:
        self.conteo.mostrar(resultado.conteos)
        self.frase.mostrar(resultado.frase, detalle_voz)
        self.histogramas.mostrar(resultado)

    def mostrar_carga(self) -> None:
        self.conteo.mostrar_carga()
        self.frase.mostrar_carga()

    def limpiar(self) -> None:
        self.conteo.limpiar()
        self.frase.limpiar()
        self.histogramas.limpiar()
