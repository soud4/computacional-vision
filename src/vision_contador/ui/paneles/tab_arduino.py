"""Pestana Arduino: conexion, LCD, control manual de LEDs y pulsador."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...core.modelos import Led
from .. import tema
from ..widgets.consola_serial import VELOCIDADES
from ..widgets.indicadores import LedConNombre, PuntoEstado
from ..widgets.lcd import COLUMNAS, PantallaLcd
from ..widgets.panel import Tarjeta, etiqueta_mono, etiqueta_sec, separador

#: El color real de cada LED de la protoboard, la excepcion a la escala de
#: grises: aqui el color dice que bombilla esta encendida.
COLORES_LED = {
    Led.AMARILLO: tema.LED_AMARILLO,
    Led.VERDE: tema.LED_VERDE,
    Led.ROJO: tema.LED_ROJO,
}


class TarjetaConexion(Tarjeta):
    """CONEXIÓN: puerto, velocidad, estado y los dos botones."""

    conectar = Signal()
    desconectar = Signal()
    buscar = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("CONEXIÓN", parent=parent)

        fila = QHBoxLayout()
        fila.setSpacing(8)
        self.puertos = QComboBox(self)
        self.puertos.setMinimumWidth(140)
        self.velocidades = QComboBox(self)
        self.velocidades.addItems(VELOCIDADES)
        self.velocidades.setCurrentText("9600")
        fila.addWidget(etiqueta_sec("Puerto", 12))
        fila.addWidget(self.puertos, 1)
        fila.addWidget(etiqueta_sec("Velocidad", 12))
        fila.addWidget(self.velocidades)
        self.cuerpo.addLayout(fila)

        estado = QHBoxLayout()
        estado.setSpacing(6)
        self.punto = PuntoEstado(tema.ERROR, 8, self)
        self.texto_estado = QLabel("Desconectado", self)
        self.texto_estado.setFont(tema.Fuentes.cuerpo(13))
        estado.addWidget(self.punto)
        estado.addWidget(self.texto_estado)
        estado.addStretch(1)

        self.boton_conexion = QPushButton("Conectar", self)
        self.boton_buscar = QPushButton("Buscar puertos", self)
        for boton in (self.boton_conexion, self.boton_buscar):
            boton.setCursor(Qt.CursorShape.PointingHandCursor)
        self.boton_buscar.clicked.connect(self.buscar)
        self.boton_conexion.clicked.connect(self._al_pulsar)
        estado.addWidget(self.boton_conexion)
        estado.addWidget(self.boton_buscar)
        self.cuerpo.addLayout(estado)

        self._conectado = False

    def _al_pulsar(self) -> None:
        (self.desconectar if self._conectado else self.conectar).emit()

    def fijar_puertos(self, puertos: list[str], seleccionado: str = "") -> None:
        self.puertos.blockSignals(True)
        self.puertos.clear()
        self.puertos.addItems(puertos or ["(sin puertos)"])
        if seleccionado and seleccionado in puertos:
            self.puertos.setCurrentText(seleccionado)
        self.puertos.blockSignals(False)

    def fijar_conectado(self, conectado: bool, detalle: str = "") -> None:
        self._conectado = conectado
        self.punto.fijar_color(tema.OK if conectado else tema.ERROR, halo=conectado)
        self.texto_estado.setText("Conectado" if conectado else (detalle or "Desconectado"))
        self.texto_estado.setStyleSheet(
            f"color: {tema.OK if conectado else tema.TEXTO_SEC}; background: transparent;"
        )
        self.boton_conexion.setText("Desconectar" if conectado else "Conectar")
        self.puertos.setEnabled(not conectado)
        self.velocidades.setEnabled(not conectado)

    @property
    def puerto(self) -> str:
        return self.puertos.currentText()

    @property
    def velocidad(self) -> int:
        try:
            return int(self.velocidades.currentText())
        except ValueError:
            return 9600


class TarjetaLcd(Tarjeta):
    """PANTALLA LCD 16x2: la representacion y los dos campos de texto."""

    enviar = Signal(str, str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("PANTALLA LCD 16x2", parent=parent)

        self.pantalla = PantallaLcd(self)
        self.cuerpo.addWidget(self.pantalla)

        self.campos: list[QLineEdit] = []
        for numero in (1, 2):
            fila = QHBoxLayout()
            fila.setSpacing(8)
            campo = QLineEdit(self)
            campo.setMaxLength(COLUMNAS)
            campo.setFont(tema.Fuentes.monoespaciada(12))
            campo.setPlaceholderText(f"Fila {numero}")
            contador = etiqueta_mono(f"0/{COLUMNAS}", 11, tema.TEXTO_SEC)
            campo.textChanged.connect(
                lambda texto, lbl=contador: lbl.setText(f"{len(texto)}/{COLUMNAS}")
            )
            campo.textChanged.connect(self._previsualizar)
            fila.addWidget(etiqueta_sec(f"Fila {numero}", 12))
            fila.addWidget(campo, 1)
            fila.addWidget(contador)
            self.campos.append(campo)
            self.cuerpo.addLayout(fila)

        self.boton = QPushButton("Enviar a LCD", self)
        self.boton.setCursor(Qt.CursorShape.PointingHandCursor)
        self.boton.clicked.connect(
            lambda: self.enviar.emit(self.campos[0].text(), self.campos[1].text())
        )
        self.cuerpo.addWidget(self.boton)

    def _previsualizar(self) -> None:
        """Lo que se escribe se ve en la pantalla antes de enviarlo."""
        self.pantalla.fijar(self.campos[0].text(), self.campos[1].text())

    def mostrar(self, fila1: str, fila2: str) -> None:
        """Refleja lo que el Arduino tiene de verdad en pantalla."""
        self.pantalla.fijar(fila1, fila2)


class TarjetaLedsManual(Tarjeta):
    """CONTROL MANUAL DE LEDS: tres interruptores y el boton de apagar todos."""

    cambiado = Signal(object, bool)
    apagar_todos = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("CONTROL MANUAL DE LEDS", parent=parent)

        fila = QHBoxLayout()
        fila.setSpacing(0)
        self.leds: dict[Led, LedConNombre] = {}
        self.casillas: dict[Led, QCheckBox] = {}

        for led in Led:
            celda = QWidget(self)
            columna = QVBoxLayout(celda)
            columna.setContentsMargins(0, 0, 0, 0)
            columna.setSpacing(6)
            columna.setAlignment(Qt.AlignmentFlag.AlignHCenter)

            widget = LedConNombre(led.etiqueta, COLORES_LED[led], 40, celda)
            casilla = QCheckBox(celda)
            casilla.toggled.connect(lambda on, cual=led: self.cambiado.emit(cual, on))

            columna.addWidget(widget, 0, Qt.AlignmentFlag.AlignHCenter)
            columna.addWidget(casilla, 0, Qt.AlignmentFlag.AlignHCenter)
            self.leds[led] = widget
            self.casillas[led] = casilla

            fila.addStretch(1)
            fila.addWidget(celda)
        fila.addStretch(1)
        self.cuerpo.addLayout(fila)

        self.boton = QPushButton("Apagar todos", self)
        self.boton.setCursor(Qt.CursorShape.PointingHandCursor)
        self.boton.clicked.connect(self.apagar_todos)
        self.cuerpo.addWidget(self.boton)

    def mostrar(self, encendidos: dict[Led, bool]) -> None:
        """Refleja el estado real sin volver a emitir la senal de cambio."""
        for led, widget in self.leds.items():
            encendido = encendidos.get(led, False)
            widget.encender(encendido)
            casilla = self.casillas[led]
            casilla.blockSignals(True)
            casilla.setChecked(encendido)
            casilla.blockSignals(False)


class TarjetaPulsador(Tarjeta):
    """PULSADOR: ultima pulsacion y contador de la sesion."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("PULSADOR", parent=parent)

        self.ultima = etiqueta_mono("—", 13, tema.TEXTO)
        self.contador = etiqueta_mono("0", 13, tema.TEXTO)
        for etiqueta, valor in (
            ("Última pulsación", self.ultima),
            ("Pulsaciones en la sesión", self.contador),
        ):
            fila = QHBoxLayout()
            fila.addWidget(etiqueta_sec(etiqueta, 12))
            fila.addStretch(1)
            fila.addWidget(valor)
            self.cuerpo.addLayout(fila)

    def mostrar(self, ultima: str, pulsaciones: int) -> None:
        self.ultima.setText(ultima)
        self.contador.setText(str(pulsaciones))


class TabArduino(QWidget):
    """La pestana completa. Se deshabilita entera cuando no hay conexion."""

    conectar = Signal()
    desconectar = Signal()
    buscar_puertos = Signal()
    enviar_lcd = Signal(str, str)
    led_cambiado = Signal(object, bool)
    apagar_leds = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        columna = QVBoxLayout(self)
        columna.setContentsMargins(12, 12, 12, 12)
        columna.setSpacing(12)

        self.conexion = TarjetaConexion(self)
        self.lcd = TarjetaLcd(self)
        self.leds = TarjetaLedsManual(self)
        self.pulsador = TarjetaPulsador(self)

        self.conexion.conectar.connect(self.conectar)
        self.conexion.desconectar.connect(self.desconectar)
        self.conexion.buscar.connect(self.buscar_puertos)
        self.lcd.enviar.connect(self.enviar_lcd)
        self.leds.cambiado.connect(self.led_cambiado)
        self.leds.apagar_todos.connect(self.apagar_leds)

        for tarjeta in (self.conexion, self.lcd, self.leds, self.pulsador):
            columna.addWidget(tarjeta)

        nota = etiqueta_sec(
            "El Arduino actúa solo como actuador. Todo el procesamiento se realiza "
            "en la laptop.",
            11,
        )
        nota.setWordWrap(True)
        columna.addWidget(separador())
        columna.addWidget(nota)
        columna.addStretch(1)

        self.fijar_conectado(False)

    def fijar_conectado(self, conectado: bool, detalle: str = "") -> None:
        """Los controles de salida solo tienen sentido con el puerto abierto."""
        self.conexion.fijar_conectado(conectado, detalle)
        for tarjeta in (self.lcd, self.leds):
            tarjeta.setEnabled(conectado)
