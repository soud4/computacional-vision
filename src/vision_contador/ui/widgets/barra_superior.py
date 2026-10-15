"""Barra superior: marca, estado, chips de hardware y el boton de captura."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QToolButton,
    QWidget,
)

from ...core.modelos import EstadoApp
from .. import iconos, tema
from .indicadores import ChipIndicador, PildoraEstado

#: La nota que antes ocupaba sitio al lado del boton; ahora es su tooltip.
AYUDA_CAPTURA = "Capturar la imagen (Espacio)\no presione el pulsador físico del Arduino"


class BarraSuperior(QFrame):
    """De lado a lado: la marca a la izquierda y la accion a la derecha.

    El texto se ha reducido al minimo -el subtitulo de la marca y las etiquetas
    de los indicadores viven ahora en los tooltips- para que la franja no
    compita con los cuatro visores, que son lo que hay que mirar.
    """

    capturar = Signal()
    subir_imagen = Signal()
    volver_camara = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Panel")
        self.setFixedHeight(tema.ALTO_BARRA_SUPERIOR)

        fila = QHBoxLayout(self)
        fila.setContentsMargins(14, 0, 12, 0)
        fila.setSpacing(14)

        fila.addWidget(self._construir_marca())
        fila.addStretch(1)

        self.pildora = PildoraEstado(self)
        self.pildora.fijar(EstadoApp.LISTO.etiqueta_corta, EstadoApp.LISTO.severidad)
        self.pildora.setToolTip(EstadoApp.LISTO.etiqueta)
        fila.addWidget(self.pildora)
        fila.addStretch(1)

        self.chip_camara = ChipIndicador(iconos.camara(), "Fuente", tema.TEXTO_SEC, self)
        self.chip_arduino = ChipIndicador(iconos.placa(), "Arduino", tema.TEXTO_SEC, self)
        self.chip_modelo = ChipIndicador(iconos.modelo(), "Modelo", tema.TEXTO_SEC, self)
        for chip in (self.chip_camara, self.chip_arduino, self.chip_modelo):
            fila.addWidget(chip)

        fila.addWidget(self._construir_boton())

    def _construir_marca(self) -> QWidget:
        marca = QWidget(self)
        fila = QHBoxLayout(marca)
        fila.setContentsMargins(0, 0, 0, 0)
        fila.setSpacing(9)

        icono = QLabel(marca)
        icono.setPixmap(iconos.camara_ojo(26))
        icono.setFixedSize(26, 26)

        titulo = QLabel("Visión Contador", marca)
        titulo.setFont(tema.Fuentes.cuerpo(14, negrita=True))
        titulo.setToolTip("Detección, clasificación y conteo de objetos")

        fila.addWidget(icono)
        fila.addWidget(titulo)
        return marca

    def _construir_boton(self) -> QWidget:
        """Boton partido: la accion a la izquierda y las fuentes en el menu."""
        self.boton = QToolButton(self)
        self.boton.setObjectName("Primario")
        self.boton.setText("Capturar")
        self.boton.setIcon(iconos.obturador(18, tema.TINTA_INVERSA))
        self.boton.setIconSize(QSize(18, 18))
        self.boton.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.boton.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        self.boton.setMinimumHeight(34)
        self.boton.setCursor(Qt.CursorShape.PointingHandCursor)
        self.boton.setToolTip(AYUDA_CAPTURA)
        self.boton.clicked.connect(self.capturar)

        menu = QMenu(self.boton)
        self.accion_camara = menu.addAction("Capturar de la cámara")
        self.accion_camara.setShortcut(QKeySequence("Space"))
        self.accion_camara.triggered.connect(self.capturar)

        self.accion_subir = menu.addAction(iconos.imagen(), "Subir imagen…")
        self.accion_subir.setShortcut(QKeySequence("Ctrl+O"))
        self.accion_subir.triggered.connect(self.subir_imagen)

        menu.addSeparator()
        self.accion_volver = menu.addAction(iconos.camara(16, tema.TEXTO), "Volver a la cámara")
        self.accion_volver.setEnabled(False)
        self.accion_volver.triggered.connect(self.volver_camara)

        self.boton.setMenu(menu)
        return self.boton

    # --- Estado ------------------------------------------------------------
    def fijar_estado(self, estado: EstadoApp, texto: str | None = None) -> None:
        self.pildora.fijar(texto or estado.etiqueta_corta, estado.severidad)
        self.pildora.setToolTip(texto or estado.etiqueta)

    def fijar_camara(self, activa: bool, detalle: str = "") -> None:
        self.chip_camara.fijar(
            detalle or ("activa" if activa else "no disponible"),
            tema.OK if activa else tema.ERROR,
        )

    def fijar_fuente_archivo(self, es_archivo: bool) -> None:
        """«Volver a la cámara» solo tiene sentido con una imagen cargada."""
        self.accion_volver.setEnabled(es_archivo)

    def fijar_arduino(self, conectado: bool, puerto: str = "", placas: int = 1) -> None:
        """Con varias placas se muestra cuántas, que es lo que importa de un vistazo."""
        if not conectado:
            detalle = "desconectado"
        elif placas > 1:
            detalle = f"{placas} placas conectadas"
        else:
            detalle = f"{puerto} conectado" if puerto else "conectado"
        self.chip_arduino.fijar(detalle, tema.OK if conectado else tema.ERROR)

    def fijar_modelo(self, nombre: str, listo: bool = True) -> None:
        self.chip_modelo.fijar(nombre, tema.OK if listo else tema.PROCESANDO)

    def habilitar_captura(self, habilitada: bool) -> None:
        self.boton.setEnabled(habilitada)
