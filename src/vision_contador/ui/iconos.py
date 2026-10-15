"""Iconos dibujados con QPainter.

Se dibujan en codigo en lugar de incrustar archivos SVG para que la aplicacion
sea un solo paquete de Python sin recursos binarios, y para que cada icono tome
su color de la paleta del tema.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap, QPolygonF

from . import tema


def _lienzo(lado: int) -> tuple[QPixmap, QPainter]:
    pixmap = QPixmap(lado, lado)
    pixmap.fill(Qt.GlobalColor.transparent)
    pintor = QPainter(pixmap)
    pintor.setRenderHint(QPainter.RenderHint.Antialiasing)
    return pixmap, pintor


def camara_ojo(lado: int = 30, color: str = tema.TEXTO) -> QPixmap:
    """Camara con un ojo por objetivo: la marca de la aplicacion."""
    pixmap, pintor = _lienzo(lado)
    e = lado / 30.0

    cuerpo = QRectF(2 * e, 8 * e, 26 * e, 18 * e)
    pintor.setPen(QPen(QColor(color), 1.8 * e))
    pintor.setBrush(tema.con_alfa(color, 0.16))
    pintor.drawRoundedRect(cuerpo, 3 * e, 3 * e)

    # Joroba del visor.
    pintor.setBrush(tema.con_alfa(color, 0.16))
    pintor.drawRoundedRect(QRectF(9 * e, 4 * e, 9 * e, 5 * e), 1.5 * e, 1.5 * e)

    centro = QPointF(15 * e, 17 * e)
    pintor.setBrush(Qt.BrushStyle.NoBrush)
    pintor.drawEllipse(centro, 6 * e, 6 * e)
    pintor.setPen(Qt.PenStyle.NoPen)
    pintor.setBrush(QColor(color))
    pintor.drawEllipse(centro, 2.6 * e, 2.6 * e)
    pintor.end()
    return pixmap


def obturador(lado: int = 18, color: str = "#FFFFFF") -> QIcon:
    """Obturador de camara para el boton Capturar."""
    pixmap, pintor = _lienzo(lado)
    centro = QPointF(lado / 2, lado / 2)
    radio = lado / 2 - 1.5

    pintor.setPen(QPen(QColor(color), 1.6))
    pintor.setBrush(Qt.BrushStyle.NoBrush)
    pintor.drawEllipse(centro, radio, radio)
    pintor.setBrush(QColor(color))
    pintor.setPen(Qt.PenStyle.NoPen)
    pintor.drawEllipse(centro, radio * 0.46, radio * 0.46)
    pintor.end()
    return QIcon(pixmap)


def altavoz(lado: int = 16, color: str = tema.TEXTO) -> QIcon:
    """Altavoz con dos ondas, para el boton Reproducir."""
    pixmap, pintor = _lienzo(lado)
    e = lado / 16.0

    pintor.setPen(Qt.PenStyle.NoPen)
    pintor.setBrush(QColor(color))
    pintor.drawRect(QRectF(2 * e, 6 * e, 3 * e, 4 * e))
    # Cono del altavoz como triangulo.
    cono = QPolygonF(
        [QPointF(5 * e, 6 * e), QPointF(9 * e, 3 * e), QPointF(9 * e, 13 * e), QPointF(5 * e, 10 * e)]
    )
    pintor.drawPolygon(cono)

    pintor.setBrush(Qt.BrushStyle.NoBrush)
    pintor.setPen(QPen(QColor(color), 1.3 * e, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    for radio in (3.0, 5.0):
        pintor.drawArc(
            QRectF(9 * e - radio * e, 8 * e - radio * e, radio * 2 * e, radio * 2 * e),
            -55 * 16,
            110 * 16,
        )
    pintor.end()
    return QIcon(pixmap)


def escoba(lado: int = 15, color: str = tema.TEXTO_SEC) -> QIcon:
    """Icono de limpiar para la consola serial."""
    pixmap, pintor = _lienzo(lado)
    e = lado / 15.0
    pintor.setPen(QPen(QColor(color), 1.4 * e, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    pintor.drawLine(QPointF(4 * e, 11 * e), QPointF(10 * e, 4 * e))
    pintor.setPen(QPen(QColor(color), 1.2 * e, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    for i in range(3):
        x = (3 + i * 2) * e
        pintor.drawLine(QPointF(x, 12.5 * e), QPointF(x + 1.5 * e, 10 * e))
    pintor.end()
    return QIcon(pixmap)


def camara(lado: int = 16, color: str = tema.TEXTO_SEC) -> QIcon:
    """Camara de video: el chip de estado de la fuente en la barra superior."""
    pixmap, pintor = _lienzo(lado)
    e = lado / 16.0
    pintor.setPen(QPen(QColor(color), 1.4 * e))
    pintor.setBrush(Qt.BrushStyle.NoBrush)
    pintor.drawRect(QRectF(2 * e, 5 * e, 9 * e, 7 * e))
    # Objetivo a la derecha, como una camara de cine vista de perfil.
    pintor.drawPolygon(
        QPolygonF(
            [
                QPointF(11.5 * e, 7.5 * e),
                QPointF(14.5 * e, 5.5 * e),
                QPointF(14.5 * e, 11.5 * e),
                QPointF(11.5 * e, 9.5 * e),
            ]
        )
    )
    pintor.end()
    return QIcon(pixmap)


def placa(lado: int = 16, color: str = tema.TEXTO_SEC) -> QIcon:
    """Circuito integrado con patas: la placa actuadora."""
    pixmap, pintor = _lienzo(lado)
    e = lado / 16.0
    pintor.setPen(QPen(QColor(color), 1.4 * e))
    pintor.setBrush(Qt.BrushStyle.NoBrush)
    pintor.drawRect(QRectF(4 * e, 4 * e, 8 * e, 8 * e))
    pintor.setPen(QPen(QColor(color), 1.2 * e, Qt.PenStyle.SolidLine, Qt.PenCapStyle.FlatCap))
    for i in range(3):
        y = (5.5 + i * 2.5) * e
        pintor.drawLine(QPointF(1.5 * e, y), QPointF(4 * e, y))
        pintor.drawLine(QPointF(12 * e, y), QPointF(14.5 * e, y))
    pintor.end()
    return QIcon(pixmap)


def modelo(lado: int = 16, color: str = tema.TEXTO_SEC) -> QIcon:
    """Rejilla de nodos conectados: el modelo de deteccion."""
    pixmap, pintor = _lienzo(lado)
    e = lado / 16.0
    nodos = [
        QPointF(3 * e, 4 * e), QPointF(3 * e, 12 * e),
        QPointF(8 * e, 8 * e),
        QPointF(13 * e, 4 * e), QPointF(13 * e, 12 * e),
    ]
    pintor.setPen(QPen(tema.con_alfa(color, 0.6), 1.1 * e))
    for extremo in (nodos[0], nodos[1], nodos[3], nodos[4]):
        pintor.drawLine(nodos[2], extremo)
    pintor.setPen(Qt.PenStyle.NoPen)
    pintor.setBrush(QColor(color))
    for nodo in nodos:
        pintor.drawEllipse(nodo, 1.7 * e, 1.7 * e)
    pintor.end()
    return QIcon(pixmap)


def imagen(lado: int = 16, color: str = tema.TEXTO) -> QIcon:
    """Fotografia con una montana: subir una imagen de archivo."""
    pixmap, pintor = _lienzo(lado)
    e = lado / 16.0
    pintor.setPen(QPen(QColor(color), 1.4 * e))
    pintor.setBrush(Qt.BrushStyle.NoBrush)
    pintor.drawRect(QRectF(2.5 * e, 3.5 * e, 11 * e, 9 * e))
    pintor.setBrush(QColor(color))
    pintor.setPen(Qt.PenStyle.NoPen)
    pintor.drawEllipse(QPointF(6 * e, 6.8 * e), 1.3 * e, 1.3 * e)
    pintor.drawPolygon(
        QPolygonF(
            [
                QPointF(3.5 * e, 12.5 * e),
                QPointF(7 * e, 8.5 * e),
                QPointF(10 * e, 12.5 * e),
            ]
        )
    )
    pintor.drawPolygon(
        QPolygonF(
            [
                QPointF(8 * e, 12.5 * e),
                QPointF(10.5 * e, 9.5 * e),
                QPointF(13 * e, 12.5 * e),
            ]
        )
    )
    pintor.end()
    return QIcon(pixmap)


def flecha_abajo(lado: int = 15, color: str = tema.TEXTO_SEC) -> QIcon:
    """Flecha hacia abajo: seguir la ultima linea de la consola."""
    pixmap, pintor = _lienzo(lado)
    e = lado / 15.0
    pintor.setPen(QPen(QColor(color), 1.5 * e, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
                       Qt.PenJoinStyle.RoundJoin))
    pintor.drawLine(QPointF(7.5 * e, 3 * e), QPointF(7.5 * e, 11 * e))
    pintor.drawPolyline([QPointF(4 * e, 7.5 * e), QPointF(7.5 * e, 11 * e), QPointF(11 * e, 7.5 * e)])
    pintor.end()
    return QIcon(pixmap)
