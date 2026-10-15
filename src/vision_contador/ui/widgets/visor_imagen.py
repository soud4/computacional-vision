"""Visor de imagen con superposiciones dibujadas sobre el cuadro.

Los cuatro paneles de la cuadricula 2x2 son este mismo widget con distintas
superposiciones activadas: el indicador EN VIVO y los FPS, el rectangulo
discontinuo de la region de interes, las cajas de deteccion con su etiqueta, las
insignias de la esquina y la cortina de "Ejecutando YOLO…".
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRect, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QSizePolicy, QWidget

from ...core.modelos import Deteccion, Imagen, Rect
from .. import tema
from ..imagen_qt import a_pixmap

#: Proporcion de los visores, como la de la camara.
PROPORCION = 4 / 3


class VisorImagen(QWidget):
    """Dibuja una imagen ajustada a la caja y encima sus anotaciones."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(220, 150)

        self._pixmap: QPixmap | None = None
        self._tam_imagen: tuple[int, int] = (1280, 720)
        self._marcador = "Sin imagen"

        self._roi: Rect | None = None
        self._referencia_roi: tuple[int, int] = (1280, 720)
        self._etiqueta_roi = "Región de interés"
        self._detecciones: list[Deteccion] = []
        self._insignias: list[tuple[str, str]] = []
        self._esquina = ""
        self._pie = ""
        self._en_vivo = False
        self._fps = 0.0
        self._ocupado = False
        self._texto_ocupado = ""
        self._atenuar = 0.0

        self._visible_vivo = True
        self._parpadeo = QTimer(self)
        self._parpadeo.timeout.connect(self._alternar_vivo)

        self._fase_progreso = 0.0
        self._animacion = QTimer(self)
        self._animacion.timeout.connect(self._avanzar_progreso)

    # --- API ---------------------------------------------------------------
    def fijar_imagen(self, imagen: Imagen | None) -> None:
        if imagen is None:
            self._pixmap = None
        else:
            self._pixmap = a_pixmap(imagen)
            alto, ancho = imagen.shape[:2]
            self._tam_imagen = (ancho, alto)
        self.update()

    def fijar_marcador(self, texto: str) -> None:
        """Texto que se muestra mientras no hay imagen."""
        self._marcador = texto
        self.update()

    def fijar_roi(
        self,
        roi: Rect | None,
        etiqueta: str = "Región de interés",
        referencia: tuple[int, int] = (1280, 720),
    ) -> None:
        """La region viene en coordenadas de ``referencia``.

        El cuadro que se esta mostrando puede tener otra resolucion -el video en
        vivo va a la mitad- asi que el rectangulo se reescala al pintarlo en vez
        de suponer que ambas coinciden.
        """
        self._roi = roi
        self._referencia_roi = referencia
        self._etiqueta_roi = etiqueta
        self.update()

    def fijar_detecciones(self, detecciones: list[Deteccion]) -> None:
        self._detecciones = detecciones
        self.update()

    def fijar_insignias(self, insignias: list[tuple[str, str]]) -> None:
        """Lista de (texto, color) para la esquina inferior izquierda."""
        self._insignias = insignias
        self.update()

    def fijar_esquina(self, texto: str) -> None:
        """Texto de la esquina superior izquierda, como la hora de la captura."""
        self._esquina = texto
        self.update()

    def fijar_pie(self, texto: str) -> None:
        """Texto de la esquina inferior derecha, como la resolucion."""
        self._pie = texto
        self.update()

    def fijar_en_vivo(self, activo: bool, fps: float = 0.0) -> None:
        self._en_vivo = activo
        self._fps = fps
        if activo and not self._parpadeo.isActive():
            self._parpadeo.start(620)
        elif not activo:
            self._parpadeo.stop()
            self._visible_vivo = True
        self.update()

    def fijar_ocupado(self, ocupado: bool, texto: str = "Ejecutando YOLO…") -> None:
        """Cortina atenuada con barra de progreso indeterminada."""
        self._ocupado = ocupado
        self._texto_ocupado = texto
        if ocupado:
            self._animacion.start(28)
        else:
            self._animacion.stop()
        self.update()

    def fijar_atenuacion(self, factor: float) -> None:
        """Oscurece la imagen sin cortina de texto, de 0 a 1."""
        self._atenuar = max(0.0, min(1.0, factor))
        self.update()

    # --- Interno -----------------------------------------------------------
    def _alternar_vivo(self) -> None:
        self._visible_vivo = not self._visible_vivo
        self.update()

    def _avanzar_progreso(self) -> None:
        self._fase_progreso = (self._fase_progreso + 0.022) % 1.0
        self.update()

    def _caja_imagen(self) -> QRectF:
        """Rectangulo donde cabe la imagen respetando la proporcion."""
        disponible = QRectF(self.rect())
        ancho_img, alto_img = self._tam_imagen
        proporcion = ancho_img / alto_img if alto_img else PROPORCION

        ancho = disponible.width()
        alto = ancho / proporcion
        if alto > disponible.height():
            alto = disponible.height()
            ancho = alto * proporcion
        return QRectF(
            disponible.center().x() - ancho / 2,
            disponible.center().y() - alto / 2,
            ancho,
            alto,
        )

    def _a_widget(self, caja: Rect, destino: QRectF) -> QRectF:
        """Pasa coordenadas de la imagen a coordenadas del widget."""
        ancho_img, alto_img = self._tam_imagen
        ex = destino.width() / ancho_img
        ey = destino.height() / alto_img
        return QRectF(
            destino.left() + caja.x * ex,
            destino.top() + caja.y * ey,
            caja.ancho * ex,
            caja.alto * ey,
        )

    # --- Dibujo ------------------------------------------------------------
    def _pintar_fondo(self, pintor: QPainter) -> None:
        """Fondo del visor, con las esquinas de abajo redondeadas.

        El visor ocupa el cuerpo del panel, justo debajo de su cabecera: arriba
        es recto y abajo tiene que seguir la curva del panel, o asomarian dos
        picos cuadrados sobre el borde redondeado.
        """
        radio = tema.RADIO_PANEL - 1
        caja = QRectF(self.rect())
        camino = QPainterPath()
        camino.moveTo(caja.topLeft())
        camino.lineTo(caja.topRight())
        camino.lineTo(caja.right(), caja.bottom() - radio)
        camino.quadTo(caja.bottomRight(), QPointF(caja.right() - radio, caja.bottom()))
        camino.lineTo(caja.left() + radio, caja.bottom())
        camino.quadTo(caja.bottomLeft(), QPointF(caja.left(), caja.bottom() - radio))
        camino.closeSubpath()
        pintor.fillPath(camino, QColor(tema.HUNDIDO))

    def paintEvent(self, evento) -> None:
        pintor = QPainter(self)
        pintor.setRenderHint(QPainter.RenderHint.Antialiasing)
        pintor.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        self._pintar_fondo(pintor)
        destino = self._caja_imagen()

        if self._pixmap is None:
            if self._ocupado:
                self._pintar_cortina(pintor, destino)
                return
            pintor.setPen(QColor(tema.TEXTO_SEC))
            pintor.setFont(tema.Fuentes.cuerpo(12))
            pintor.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self._marcador)
            return

        pintor.drawPixmap(destino.toRect(), self._pixmap)

        if self._atenuar > 0:
            velo = QColor(tema.HUNDIDO)
            velo.setAlphaF(self._atenuar)
            pintor.fillRect(destino, velo)

        if self._roi is not None:
            self._pintar_roi(pintor, destino)
        if self._detecciones:
            self._pintar_detecciones(pintor, destino)
        if self._en_vivo:
            self._pintar_en_vivo(pintor, destino)
        if self._esquina:
            self._pintar_marca(pintor, destino, self._esquina, superior=True)
        if self._pie:
            self._pintar_marca(pintor, destino, self._pie, superior=False)
        if self._insignias:
            self._pintar_insignias(pintor, destino)
        if self._ocupado:
            self._pintar_cortina(pintor, destino)

    def _pintar_roi(self, pintor: QPainter, destino: QRectF) -> None:
        ref_ancho, ref_alto = self._referencia_roi
        img_ancho, img_alto = self._tam_imagen
        ex, ey = img_ancho / ref_ancho, img_alto / ref_alto
        roi = Rect(
            round(self._roi.x * ex),
            round(self._roi.y * ey),
            round(self._roi.ancho * ex),
            round(self._roi.alto * ey),
        )
        caja = self._a_widget(roi, destino)
        lapiz = QPen(QColor(tema.TEXTO), 1.6)
        lapiz.setStyle(Qt.PenStyle.DashLine)
        lapiz.setDashPattern([6, 4])
        pintor.setPen(lapiz)
        pintor.setBrush(Qt.BrushStyle.NoBrush)
        pintor.drawRect(caja)

        pintor.setFont(tema.Fuentes.cuerpo(10))
        metrica = pintor.fontMetrics()
        ancho = metrica.horizontalAdvance(self._etiqueta_roi) + 10
        etiqueta = QRectF(caja.left(), caja.top() - 17, ancho, 15)
        if etiqueta.top() < destino.top():
            etiqueta.moveTop(caja.top() + 3)
        pintor.setPen(Qt.PenStyle.NoPen)
        pintor.setBrush(tema.con_alfa(tema.ACENTO, 0.85))
        pintor.drawRoundedRect(etiqueta, tema.RADIO_CHICO, tema.RADIO_CHICO)
        pintor.setPen(QColor(tema.tinta_sobre(tema.ACENTO)))
        pintor.drawText(etiqueta, Qt.AlignmentFlag.AlignCenter, self._etiqueta_roi)

    def _pintar_detecciones(self, pintor: QPainter, destino: QRectF) -> None:
        pintor.setFont(tema.Fuentes.cuerpo(11, negrita=True))
        metrica = pintor.fontMetrics()
        # El color se asigna por clase, no por indice, para que la botella
        # conserve su color aunque cambie el orden de las detecciones.
        clases = sorted({d.clase for d in self._detecciones})

        for deteccion in self._detecciones:
            indice = clases.index(deteccion.clase)
            gris = tema.COLORES_CAJA[indice % len(tema.COLORES_CAJA)]
            trazo = tema.TRAZOS_CAJA[indice % len(tema.TRAZOS_CAJA)]
            color = QColor(gris)
            caja = self._a_widget(deteccion.caja, destino)

            # Dos clases seguidas pueden caer en grises parecidos, asi que lo
            # que de verdad las separa es el tipo de trazo del rectangulo.
            pintor.setPen(QPen(color, 2, trazo))
            pintor.setBrush(Qt.BrushStyle.NoBrush)
            pintor.drawRect(caja)

            texto = deteccion.etiqueta
            ancho = metrica.horizontalAdvance(texto) + 12
            alto = metrica.height() + 4
            etiqueta = QRectF(caja.left() - 1, caja.top() - alto - 1, ancho, alto)
            if etiqueta.top() < destino.top():
                etiqueta.moveTop(caja.top() + 1)
            pintor.setPen(Qt.PenStyle.NoPen)
            pintor.setBrush(color)
            pintor.drawRoundedRect(etiqueta, tema.RADIO_CHICO, tema.RADIO_CHICO)
            pintor.setPen(QColor(tema.tinta_sobre(gris)))
            pintor.drawText(etiqueta, Qt.AlignmentFlag.AlignCenter, texto)

    def _pintar_en_vivo(self, pintor: QPainter, destino: QRectF) -> None:
        pintor.setFont(tema.Fuentes.monoespaciada(10, negrita=True))
        metrica = pintor.fontMetrics()
        texto_fps = f"{self._fps:.0f} FPS"
        ancho_fps = metrica.horizontalAdvance(texto_fps) + 12
        alto = 18

        caja_fps = QRectF(destino.right() - ancho_fps - 8, destino.top() + 8, ancho_fps, alto)
        pintor.setPen(Qt.PenStyle.NoPen)
        pintor.setBrush(QColor(0, 0, 0, 150))
        pintor.drawRoundedRect(caja_fps, tema.RADIO_CHICO, tema.RADIO_CHICO)
        pintor.setPen(QColor(tema.TEXTO))
        pintor.drawText(caja_fps, Qt.AlignmentFlag.AlignCenter, texto_fps)

        ancho_vivo = metrica.horizontalAdvance("EN VIVO") + 24
        caja_vivo = QRectF(caja_fps.left() - ancho_vivo - 6, caja_fps.top(), ancho_vivo, alto)
        pintor.setPen(Qt.PenStyle.NoPen)
        pintor.setBrush(QColor(0, 0, 0, 150))
        pintor.drawRoundedRect(caja_vivo, tema.RADIO_CHICO, tema.RADIO_CHICO)

        punto = QColor(tema.TEXTO)
        if not self._visible_vivo:
            punto.setAlphaF(0.25)
        pintor.setBrush(punto)
        pintor.drawEllipse(QPointF(caja_vivo.left() + 10, caja_vivo.center().y()), 3.5, 3.5)
        pintor.setPen(QColor(tema.TEXTO))
        pintor.drawText(
            caja_vivo.adjusted(18, 0, -4, 0),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            "EN VIVO",
        )

    def _pintar_marca(
        self, pintor: QPainter, destino: QRectF, texto: str, superior: bool
    ) -> None:
        pintor.setFont(tema.Fuentes.monoespaciada(10))
        metrica = pintor.fontMetrics()
        ancho = metrica.horizontalAdvance(texto) + 12
        alto = 18
        if superior:
            caja = QRectF(destino.left() + 8, destino.top() + 8, ancho, alto)
        else:
            caja = QRectF(destino.right() - ancho - 8, destino.bottom() - alto - 8, ancho, alto)
        pintor.setPen(Qt.PenStyle.NoPen)
        pintor.setBrush(QColor(0, 0, 0, 150))
        pintor.drawRoundedRect(caja, tema.RADIO_CHICO, tema.RADIO_CHICO)
        pintor.setPen(QColor(tema.TEXTO))
        pintor.drawText(caja, Qt.AlignmentFlag.AlignCenter, texto)

    def _pintar_insignias(self, pintor: QPainter, destino: QRectF) -> None:
        pintor.setFont(tema.Fuentes.monoespaciada(10, negrita=True))
        metrica = pintor.fontMetrics()
        x = destino.left() + 8
        y = destino.bottom() - 26
        for texto, color_hex in self._insignias:
            ancho = metrica.horizontalAdvance(texto) + 14
            caja = QRectF(x, y, ancho, 18)
            color = QColor(color_hex)
            pintor.setPen(Qt.PenStyle.NoPen)
            pintor.setBrush(QColor(0, 0, 0, 170))
            pintor.drawRoundedRect(caja, tema.RADIO_CHICO, tema.RADIO_CHICO)
            pintor.setPen(color)
            pintor.drawText(caja, Qt.AlignmentFlag.AlignCenter, texto)
            x += ancho + 6

    def _pintar_cortina(self, pintor: QPainter, destino: QRectF) -> None:
        velo = QColor(tema.FONDO)
        velo.setAlphaF(0.62)
        pintor.fillRect(destino, velo)

        ancho_barra = min(destino.width() * 0.52, 260.0)
        barra = QRectF(
            destino.center().x() - ancho_barra / 2,
            destino.center().y() + 6,
            ancho_barra,
            5,
        )
        pintor.setPen(Qt.PenStyle.NoPen)
        pintor.setBrush(QColor(tema.HUNDIDO))
        pintor.drawRoundedRect(barra, 2.5, 2.5)

        # Barra indeterminada: un segmento que recorre el carril de ida y vuelta.
        largo = barra.width() * 0.3
        recorrido = barra.width() - largo
        fase = self._fase_progreso * 2
        avance = fase if fase <= 1 else 2 - fase
        segmento = QRectF(barra.left() + recorrido * avance, barra.top(), largo, barra.height())
        pintor.setBrush(QColor(tema.TEXTO))
        pintor.drawRoundedRect(segmento, 2.5, 2.5)

        pintor.setPen(QColor(tema.TEXTO))
        pintor.setFont(tema.Fuentes.cuerpo(12, negrita=True))
        pintor.drawText(
            QRect(
                int(destino.left()),
                int(destino.center().y() - 28),
                int(destino.width()),
                20,
            ),
            Qt.AlignmentFlag.AlignCenter,
            self._texto_ocupado,
        )
