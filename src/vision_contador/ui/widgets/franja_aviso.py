"""Franja de aviso bajo la barra superior."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QWidget

from .. import tema


class FranjaAviso(QFrame):
    """Banda de color tenue con un mensaje y un boton de accion.

    Se usa para avisar de que no se encontro el Arduino sin bloquear nada: la
    captura tiene que seguir funcionando aunque no haya hardware.
    """

    accion_pulsada = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(38)
        self.setVisible(False)

        fila = QHBoxLayout(self)
        fila.setContentsMargins(14, 0, 10, 0)
        fila.setSpacing(10)

        self.icono = QLabel("⚠", self)
        self.mensaje = QLabel("", self)
        self.mensaje.setFont(tema.Fuentes.cuerpo(12))
        self.boton = QPushButton("Reintentar", self)
        self.boton.setCursor(Qt.CursorShape.PointingHandCursor)
        self.boton.clicked.connect(self.accion_pulsada)

        fila.addWidget(self.icono)
        fila.addWidget(self.mensaje)
        fila.addStretch(1)
        fila.addWidget(self.boton)

    def mostrar(self, mensaje: str, accion: str = "Reintentar", color: str = tema.ERROR) -> None:
        self.mensaje.setText(mensaje)
        self.boton.setText(accion)
        self.boton.setVisible(bool(accion))
        fondo = tema.con_alfa(color, 1.0)
        # Un fondo tenue y el signo de admiración bastan para que se lea como un
        # aviso. Nada de marco ni de barra lateral: con las esquinas redondeadas
        # un borde parcial deja un arco a la vista.
        self.setStyleSheet(
            f"QFrame {{ background-color: rgba({fondo.red()},{fondo.green()},{fondo.blue()},34);"
            f" border: none; border-radius: {tema.RADIO}px; }}"
            f" QLabel {{ color: {color}; background: transparent; }}"
        )
        self.setVisible(True)

    def ocultar(self) -> None:
        self.setVisible(False)
