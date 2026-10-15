"""Consola serial: la franja inferior de la ventana.

Muestra el trafico con el Arduino coloreado por direccion y permite enviar
ordenes a mano, que es la forma mas rapida de probar la LCD o un LED sin
recompilar nada.
"""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QToolButton,
    QWidget,
)

from ...core.modelos import Direccion, LineaSerial
from .. import iconos, tema
from .panel import Panel

#: Nivel de gris de cada direccion en el area de texto. Las flechas de
#: ``Direccion`` ya distinguen quien habla; el gris solo marca la jerarquia:
#: los errores destacan, lo informativo se apaga.
COLORES = {
    Direccion.ENVIADO: tema.TEXTO,
    Direccion.RECIBIDO: tema.OK,
    Direccion.ERROR: tema.ERROR,
    Direccion.INFO: tema.TEXTO_SEC,
}

#: Lineas que se conservan. Mas alla de esto la consola solo gasta memoria.
MAXIMO_LINEAS = 500

VELOCIDADES = ["9600", "19200", "38400", "57600", "115200"]


class ConsolaSerial(Panel):
    """Panel con el monitor, los controles de puerto y el campo de envio."""

    conectar_pulsado = Signal()
    desconectar_pulsado = Signal()
    enviar_pulsado = Signal(str)
    puerto_cambiado = Signal(str)
    velocidad_cambiada = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        self.puertos = QComboBox()
        self.puertos.setMinimumWidth(130)
        self.velocidades = QComboBox()
        self.velocidades.addItems(VELOCIDADES)
        self.velocidades.setCurrentText("9600")
        self.velocidades.setMinimumWidth(80)
        # Las etiquetas "Puerto" y "Velocidad" se han ido al tooltip: dos
        # desplegables seguidos en la cabecera de la consola serial no necesitan
        # que se les diga lo que son.
        self.puertos.setToolTip("Puerto serie del Arduino")
        self.velocidades.setToolTip("Velocidad del puerto, en baudios")

        self.boton_conexion = QPushButton("Conectar")
        self.boton_limpiar = QToolButton()
        self.boton_limpiar.setIcon(iconos.escoba(15))
        self.boton_limpiar.setToolTip("Limpiar la consola")
        self.auto_desplazar = QToolButton()
        self.auto_desplazar.setIcon(iconos.flecha_abajo(15))
        self.auto_desplazar.setCheckable(True)
        self.auto_desplazar.setChecked(True)
        self.auto_desplazar.setToolTip("Seguir la última línea automáticamente")
        for boton in (self.boton_limpiar, self.auto_desplazar):
            boton.setCursor(Qt.CursorShape.PointingHandCursor)

        super().__init__(
            "CONSOLA SERIAL",
            acciones=[
                self.puertos,
                self.velocidades,
                self.boton_conexion,
                self.boton_limpiar,
                self.auto_desplazar,
            ],
            margenes=(10, 8, 10, 10),
            parent=parent,
        )

        self.texto = QPlainTextEdit(self)
        self.texto.setReadOnly(True)
        self.texto.setFont(tema.Fuentes.monoespaciada(12))
        self.texto.setStyleSheet(
            f"background-color: {tema.HUNDIDO}; border: 1px solid {tema.BORDE};"
            f" border-radius: {tema.RADIO}px; padding: 6px;"
        )
        self.texto.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.cuerpo.addWidget(self.texto, 1)

        envio = QHBoxLayout()
        envio.setSpacing(8)
        self.campo = QLineEdit(self)
        self.campo.setPlaceholderText("Escribir comando…")
        self.campo.setFont(tema.Fuentes.monoespaciada(12))
        self.campo.returnPressed.connect(self._emitir_envio)
        self.boton_enviar = QPushButton("Enviar", self)
        self.boton_enviar.clicked.connect(self._emitir_envio)
        envio.addWidget(self.campo, 1)
        envio.addWidget(self.boton_enviar)
        self.cuerpo.addLayout(envio)

        self.boton_limpiar.clicked.connect(self.limpiar)
        self.boton_conexion.clicked.connect(self._al_pulsar_conexion)
        self.puertos.currentTextChanged.connect(self.puerto_cambiado)
        self.velocidades.currentTextChanged.connect(
            lambda v: self.velocidad_cambiada.emit(int(v))
        )

        self._conectado = False
        self._actualizar_boton()

    # --- Estado ------------------------------------------------------------
    def fijar_puertos(self, puertos: list[str], seleccionado: str = "") -> None:
        self.puertos.blockSignals(True)
        self.puertos.clear()
        self.puertos.addItems(puertos or ["(sin puertos)"])
        if seleccionado and seleccionado in puertos:
            self.puertos.setCurrentText(seleccionado)
        self.puertos.blockSignals(False)

    def fijar_conectado(self, conectado: bool) -> None:
        self._conectado = conectado
        self._actualizar_boton()

    def _actualizar_boton(self) -> None:
        self.boton_conexion.setText("Desconectar" if self._conectado else "Conectar")
        self.puertos.setEnabled(not self._conectado)
        self.velocidades.setEnabled(not self._conectado)
        self.campo.setEnabled(self._conectado)
        self.boton_enviar.setEnabled(self._conectado)

    @property
    def puerto(self) -> str:
        return self.puertos.currentText()

    @property
    def velocidad(self) -> int:
        return int(self.velocidades.currentText())

    # --- Contenido ---------------------------------------------------------
    def anotar(self, linea: LineaSerial) -> None:
        """Agrega una linea ya formateada con el color de su direccion."""
        documento = self.texto.document()
        if documento.blockCount() > MAXIMO_LINEAS:
            cursor = QTextCursor(documento.firstBlock())
            cursor.select(QTextCursor.SelectionType.BlockUnderCursor)
            cursor.removeSelectedText()
            cursor.deleteChar()

        cursor = self.texto.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        gris = QTextCharFormat()
        gris.setForeground(QColor(tema.TEXTO_SEC))
        cuerpo = QTextCharFormat()
        cuerpo.setForeground(QColor(COLORES[linea.direccion]))

        if documento.blockCount() > 1 or documento.firstBlock().text():
            cursor.insertBlock()
        cursor.insertText(f"[{linea.momento.strftime('%H:%M:%S')}] ", gris)
        cursor.insertText(f"{linea.direccion.flecha} {linea.texto}", cuerpo)

        if self.auto_desplazar.isChecked():
            barra = self.texto.verticalScrollBar()
            barra.setValue(barra.maximum())

    def registrar(self, direccion: Direccion, texto: str) -> None:
        self.anotar(LineaSerial(datetime.now(), direccion, texto))

    def limpiar(self) -> None:
        self.texto.clear()

    # --- Senales -----------------------------------------------------------
    def _al_pulsar_conexion(self) -> None:
        if self._conectado:
            self.desconectar_pulsado.emit()
        else:
            self.conectar_pulsado.emit()

    def _emitir_envio(self) -> None:
        orden = self.campo.text().strip()
        if orden:
            self.enviar_pulsado.emit(orden)
            self.campo.clear()
