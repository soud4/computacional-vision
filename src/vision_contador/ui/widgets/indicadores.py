"""Puntos de estado, pildora de la barra superior e insignias."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QWidget

from .. import tema


class PuntoEstado(QWidget):
    """Circulo de color de 8 px, opcionalmente con halo o parpadeo."""

    def __init__(
        self, color: str = tema.OK, diametro: int = 8, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._color = QColor(color)
        self._diametro = diametro
        self._halo = False
        self._visible_parpadeo = True
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._alternar)
        self.setFixedSize(diametro + 6, diametro + 6)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    def fijar_color(self, color: str, halo: bool = False) -> None:
        self._color = QColor(color)
        self._halo = halo
        self.update()

    def parpadear(self, activo: bool, ms: int = 520) -> None:
        if activo:
            self._timer.start(ms)
        else:
            self._timer.stop()
            self._visible_parpadeo = True
            self.update()

    def _alternar(self) -> None:
        self._visible_parpadeo = not self._visible_parpadeo
        self.update()

    def paintEvent(self, evento) -> None:
        pintor = QPainter(self)
        pintor.setRenderHint(QPainter.RenderHint.Antialiasing)
        centro = QRectF(self.rect()).center()
        r = self._diametro / 2

        if self._halo and self._visible_parpadeo:
            halo = QColor(self._color)
            halo.setAlphaF(0.22)
            pintor.setBrush(halo)
            pintor.setPen(Qt.PenStyle.NoPen)
            pintor.drawEllipse(centro, r + 3.5, r + 3.5)

        color = QColor(self._color)
        if not self._visible_parpadeo:
            color.setAlphaF(0.22)
        pintor.setBrush(color)
        pintor.setPen(Qt.PenStyle.NoPen)
        pintor.drawEllipse(centro, r, r)


class PildoraEstado(QWidget):
    """Indicador grande y central de la barra superior.

    Sin tono que distinga los estados, cada severidad se dibuja con su propia
    forma: punto lleno cuando todo esta listo, arco giratorio mientras se
    procesa y aspa cuando hay un error.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._color = QColor(tema.OK)
        self._texto = ""
        self._severidad = "ok"
        self._girando = False
        self._angulo = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._girar)
        self.setFixedHeight(34)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.setFont(tema.Fuentes.cuerpo(13, negrita=True))

    def fijar(self, texto: str, severidad: str) -> None:
        self._texto = texto
        self._severidad = severidad
        self._color = QColor(tema.SEVERIDAD.get(severidad, tema.OK))
        girar = severidad == "procesando"
        if girar and not self._girando:
            self._timer.start(45)
        elif not girar and self._girando:
            self._timer.stop()
        self._girando = girar
        self.updateGeometry()
        self.update()

    def _girar(self) -> None:
        self._angulo = (self._angulo + 12) % 360
        self.update()

    def sizeHint(self) -> QSize:
        ancho = self.fontMetrics().horizontalAdvance(self._texto) + 56
        return QSize(max(ancho, 140), 34)

    def paintEvent(self, evento) -> None:
        pintor = QPainter(self)
        pintor.setRenderHint(QPainter.RenderHint.Antialiasing)
        caja = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)

        fondo = QColor(self._color)
        fondo.setAlphaF(0.10)
        pintor.setPen(Qt.PenStyle.NoPen)
        pintor.setBrush(fondo)
        pintor.drawRoundedRect(caja, tema.RADIO, tema.RADIO)
        # Una barra a la izquierda en lugar de un marco alrededor: marca el
        # estado sin encerrar el texto. Se recorta con la misma curva que la
        # caja para que no sobresalga por la esquina.
        recorte = QPainterPath()
        recorte.addRoundedRect(caja, tema.RADIO, tema.RADIO)
        pintor.save()
        pintor.setClipPath(recorte)
        pintor.setBrush(self._color)
        pintor.drawRect(QRectF(caja.left(), caja.top(), 3, caja.height()))
        pintor.restore()

        cx, cy = caja.left() + 22, caja.center().y()
        if self._girando:
            # Arco de 280 grados girando: el indicador de trabajo en curso.
            pintor.setBrush(Qt.BrushStyle.NoBrush)
            pintor.setPen(QPen(self._color, 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            arco = QRectF(cx - 6, cy - 6, 12, 12)
            pintor.drawArc(arco, -self._angulo * 16, 280 * 16)
        elif self._severidad == "error":
            pintor.setPen(QPen(self._color, 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            pintor.drawLine(QPointF(cx - 4, cy - 4), QPointF(cx + 4, cy + 4))
            pintor.drawLine(QPointF(cx + 4, cy - 4), QPointF(cx - 4, cy + 4))
        else:
            pintor.setPen(Qt.PenStyle.NoPen)
            pintor.setBrush(self._color)
            pintor.drawEllipse(QRectF(cx - 4, cy - 4, 8, 8))

        pintor.setPen(QColor(tema.TEXTO))
        pintor.setFont(self.font())
        pintor.drawText(
            caja.adjusted(36, 0, -14, 0),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            self._texto,
        )


class IndicadorPequeno(QWidget):
    """Punto de color mas etiqueta: 'Cámara: activa'."""

    def __init__(
        self, etiqueta: str, color: str = tema.OK, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        fila = QHBoxLayout(self)
        fila.setContentsMargins(0, 0, 0, 0)
        fila.setSpacing(2)

        self.punto = PuntoEstado(color, 7, self)
        self.texto = QLabel(etiqueta, self)
        self.texto.setObjectName("TextoSecundario")
        self.texto.setFont(tema.Fuentes.cuerpo(12))
        fila.addWidget(self.punto)
        fila.addWidget(self.texto)

    def fijar(self, etiqueta: str, color: str) -> None:
        self.texto.setText(etiqueta)
        self.punto.fijar_color(color)


class ChipIndicador(QWidget):
    """Icono mas punto de estado, con el detalle en el tooltip.

    Reemplaza en la barra superior a las etiquetas de texto del tipo
    "Cámara: activa": el icono dice de que se habla y el punto, como esta; el
    texto completo se consulta pasando el raton por encima.
    """

    def __init__(
        self,
        icono: QIcon,
        titulo: str,
        color: str = tema.TEXTO_SEC,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._titulo = titulo

        fila = QHBoxLayout(self)
        fila.setContentsMargins(6, 0, 6, 0)
        fila.setSpacing(4)

        self.icono = QLabel(self)
        self.icono.setPixmap(icono.pixmap(QSize(16, 16)))
        self.icono.setFixedSize(16, 16)
        self.punto = PuntoEstado(color, 6, self)

        fila.addWidget(self.icono)
        fila.addWidget(self.punto)
        self.fijar("—", color)

    def fijar(self, detalle: str, color: str) -> None:
        self.punto.fijar_color(color)
        self.setToolTip(f"{self._titulo}: {detalle}")


class Insignia(QLabel):
    """Etiqueta rectangular pequena: 'Sem. 6', '4 objetos', 'Aplicada'."""

    def __init__(
        self,
        texto: str,
        color: str = tema.TEXTO_SEC,
        mono: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(texto, parent)
        self.setFont(
            tema.Fuentes.monoespaciada(11) if mono else tema.Fuentes.cuerpo(11)
        )
        self.fijar_color(color)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def fijar_color(self, color: str) -> None:
        fondo = QColor(color)
        fondo.setAlphaF(0.13)
        self.setStyleSheet(
            f"color: {color};"
            f" background-color: rgba({fondo.red()},{fondo.green()},{fondo.blue()},36);"
            f" border: none; border-radius: {tema.RADIO_CHICO}px; padding: 2px 6px;"
        )


class Led(QWidget):
    """LED fisico de la protoboard: circulo con brillo cuando esta encendido."""

    def __init__(
        self, color: str, diametro: int = 34, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._color = QColor(color)
        self._encendido = False
        self._diametro = diametro
        self.setFixedSize(diametro + 18, diametro + 18)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    def encender(self, encendido: bool) -> None:
        if self._encendido != encendido:
            self._encendido = encendido
            self.update()

    @property
    def encendido(self) -> bool:
        return self._encendido

    def paintEvent(self, evento) -> None:
        pintor = QPainter(self)
        pintor.setRenderHint(QPainter.RenderHint.Antialiasing)
        centro = QRectF(self.rect()).center()
        r = self._diametro / 2

        if self._encendido:
            # Dos halos concentricos imitan la difusion de la capsula de plastico.
            for radio, alfa in ((r + 9, 0.10), (r + 4, 0.20)):
                halo = QColor(self._color)
                halo.setAlphaF(alfa)
                pintor.setBrush(halo)
                pintor.setPen(Qt.PenStyle.NoPen)
                pintor.drawEllipse(centro, radio, radio)
            cuerpo = QColor(self._color)
            borde = QColor(self._color).lighter(130)
        else:
            cuerpo = QColor(self._color).darker(330)
            borde = QColor(tema.BORDE)

        pintor.setBrush(cuerpo)
        pintor.setPen(QPen(borde, 1))
        pintor.drawEllipse(centro, r, r)

        if self._encendido:
            brillo = QColor(255, 255, 255, 110)
            pintor.setBrush(brillo)
            pintor.setPen(Qt.PenStyle.NoPen)
            pintor.drawEllipse(
                QRectF(centro.x() - r * 0.45, centro.y() - r * 0.6, r * 0.5, r * 0.36)
            )


class LedConNombre(QWidget):
    """LED con su nombre debajo, como en la tarjeta ESTADO DE LOS LEDS."""

    def __init__(
        self, nombre: str, color: str, diametro: int = 34, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        from PySide6.QtWidgets import QVBoxLayout

        columna = QVBoxLayout(self)
        columna.setContentsMargins(0, 0, 0, 0)
        columna.setSpacing(2)
        columna.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self.led = Led(color, diametro, self)
        self.etiqueta = QLabel(nombre, self)
        self.etiqueta.setObjectName("TextoSecundario")
        self.etiqueta.setFont(tema.Fuentes.cuerpo(12))
        self.etiqueta.setAlignment(Qt.AlignmentFlag.AlignCenter)

        columna.addWidget(self.led, 0, Qt.AlignmentFlag.AlignHCenter)
        columna.addWidget(self.etiqueta)

    def encender(self, encendido: bool) -> None:
        self.led.encender(encendido)
        color = tema.TEXTO if encendido else tema.TEXTO_SEC
        self.etiqueta.setStyleSheet(f"color: {color}; background: transparent;")
