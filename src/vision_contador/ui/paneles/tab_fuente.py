"""Pestana Fuente: de donde salen los cuadros que se van a procesar.

Tres entradas posibles: la camara conectada a la maquina, una camara de red
-tipicamente la del telefono, publicada por una aplicacion como IP Webcam o
DroidCam- y una imagen guardada en disco. La pestana solo recoge la eleccion y
la anuncia con una senal; abrir la fuente y cambiarla es trabajo de la ventana.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from .. import tema
from ..widgets.panel import Tarjeta, etiqueta_sec, separador

AYUDA_RED = (
    "Instale IP Webcam o DroidCam en el teléfono, conéctelo a la misma red WiFi "
    "que esta laptop y pegue aquí la dirección que muestra la aplicación. "
    "El puerto suele ser 8080 en IP Webcam y 4747 en DroidCam."
)

AVISO_SIN_OPENCV = (
    "Las cámaras necesitan OpenCV: uv pip install -e \".[vision]\". "
    "La imagen de archivo funciona igual sin instalarlo."
)


class TarjetaEntrada(Tarjeta):
    """ENTRADA: las tres opciones, el boton de prueba y el de usar."""

    probar = Signal(str)
    usar = Signal(str)
    buscar = Signal()
    abrir_imagen = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("ENTRADA", parent=parent)

        self.grupo = QButtonGroup(self)
        self.opcion_local = QRadioButton("Cámara local", self)
        self.opcion_red = QRadioButton("Cámara de red (celular)", self)
        self.opcion_archivo = QRadioButton("Imagen de archivo", self)
        self.opcion_local.setChecked(True)
        for opcion in (self.opcion_local, self.opcion_red, self.opcion_archivo):
            self.grupo.addButton(opcion)
            opcion.toggled.connect(self._al_cambiar_opcion)

        # --- camara local
        self.cuerpo.addWidget(self.opcion_local)
        fila_local = QHBoxLayout()
        fila_local.setContentsMargins(22, 0, 0, 0)
        fila_local.setSpacing(8)
        self.dispositivos = QComboBox(self)
        self.dispositivos.setMinimumWidth(190)
        self.boton_buscar = QPushButton("Buscar", self)
        self.boton_buscar.clicked.connect(self.buscar)
        fila_local.addWidget(self.dispositivos, 1)
        fila_local.addWidget(self.boton_buscar)
        self.cuerpo.addLayout(fila_local)

        # --- camara de red
        self.cuerpo.addWidget(self.opcion_red)
        fila_red = QVBoxLayout()
        fila_red.setContentsMargins(22, 0, 0, 0)
        fila_red.setSpacing(3)
        self.url = QLineEdit(self)
        self.url.setPlaceholderText("http://192.168.1.40:8080/video")
        self.url.setFont(tema.Fuentes.monoespaciada(12))
        self.url.setToolTip(AYUDA_RED)
        ayuda = etiqueta_sec(
            "La misma red WiFi en ambos · puerto 8080 en IP Webcam, 4747 en DroidCam", 11
        )
        ayuda.setWordWrap(True)
        fila_red.addWidget(self.url)
        fila_red.addWidget(ayuda)
        self.cuerpo.addLayout(fila_red)

        # --- imagen de archivo
        self.cuerpo.addWidget(self.opcion_archivo)
        fila_archivo = QHBoxLayout()
        fila_archivo.setContentsMargins(22, 0, 0, 0)
        fila_archivo.setSpacing(8)
        self.archivo = etiqueta_sec("Ninguna imagen cargada", 12)
        self.boton_archivo = QPushButton("Abrir imagen…", self)
        self.boton_archivo.clicked.connect(self.abrir_imagen)
        fila_archivo.addWidget(self.archivo, 1)
        fila_archivo.addWidget(self.boton_archivo)
        self.cuerpo.addLayout(fila_archivo)

        self.cuerpo.addWidget(separador())

        # --- acciones
        acciones = QHBoxLayout()
        acciones.setSpacing(10)
        self.boton_probar = QPushButton("Probar", self)
        self.boton_usar = QPushButton("Usar esta fuente", self)
        self.boton_usar.setObjectName("Primario")
        for boton in (self.boton_probar, self.boton_usar):
            boton.setCursor(Qt.CursorShape.PointingHandCursor)
        self.boton_probar.clicked.connect(lambda: self.probar.emit(self.destino))
        self.boton_usar.clicked.connect(self._al_usar)
        acciones.addWidget(self.boton_probar)
        acciones.addWidget(self.boton_usar, 1)
        self.cuerpo.addLayout(acciones)

        self.estado = QLabel("", self)
        self.estado.setFont(tema.Fuentes.monoespaciada(11))
        self.estado.setWordWrap(True)
        self.estado.setStyleSheet(f"color: {tema.TEXTO_SEC}; background: transparent;")
        self.cuerpo.addWidget(self.estado)

        self._al_cambiar_opcion()

    # --- Estado ------------------------------------------------------------
    @property
    def destino(self) -> str:
        """Lo que hay que abrir, ya como texto: un indice o una URL."""
        if self.opcion_red.isChecked():
            return self.url.text().strip()
        return self.dispositivos.currentData() or ""

    def _al_usar(self) -> None:
        if self.opcion_archivo.isChecked():
            self.abrir_imagen.emit()
        else:
            self.usar.emit(self.destino)

    def _al_cambiar_opcion(self) -> None:
        local, red, archivo = (
            self.opcion_local.isChecked(),
            self.opcion_red.isChecked(),
            self.opcion_archivo.isChecked(),
        )
        self.dispositivos.setEnabled(local)
        self.boton_buscar.setEnabled(local)
        self.url.setEnabled(red)
        self.boton_archivo.setEnabled(archivo)
        # Probar abre la fuente de verdad; con una imagen de archivo no hay nada
        # que tantear, el propio dialogo dice si se pudo leer.
        self.boton_probar.setEnabled(not archivo)
        self.boton_usar.setText("Abrir imagen…" if archivo else "Usar esta fuente")

    def fijar_dispositivos(self, dispositivos: list[tuple[str, str]], actual: str = "") -> None:
        self.dispositivos.blockSignals(True)
        self.dispositivos.clear()
        for destino, etiqueta in dispositivos:
            self.dispositivos.addItem(etiqueta, destino)
        if not dispositivos:
            self.dispositivos.addItem("(ninguna cámara encontrada)", "")
        if actual:
            indice = self.dispositivos.findData(actual)
            if indice >= 0:
                self.dispositivos.setCurrentIndex(indice)
        self.dispositivos.blockSignals(False)

    def fijar_archivo(self, ruta: str) -> None:
        self.archivo.setText(Path(ruta).name if ruta else "Ninguna imagen cargada")

    def fijar_mensaje(self, texto: str, error: bool = False) -> None:
        self.estado.setText(texto)
        self.estado.setStyleSheet(
            f"color: {tema.ERROR if error else tema.TEXTO_SEC}; background: transparent;"
        )

    def fijar_probando(self, probando: bool) -> None:
        self.boton_probar.setEnabled(not probando and not self.opcion_archivo.isChecked())
        self.boton_probar.setText("Probando…" if probando else "Probar")

    def deshabilitar_camaras(self) -> None:
        """Sin OpenCV solo queda la imagen de archivo."""
        self.opcion_archivo.setChecked(True)
        for widget in (self.opcion_local, self.opcion_red):
            widget.setEnabled(False)
            widget.setToolTip(AVISO_SIN_OPENCV)
        self._al_cambiar_opcion()
        self.fijar_mensaje(AVISO_SIN_OPENCV)


class TabFuente(QWidget):
    """La pestana completa."""

    probar = Signal(str)
    usar = Signal(str)
    buscar = Signal()
    abrir_imagen = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        columna = QVBoxLayout(self)
        columna.setContentsMargins(12, 12, 12, 12)
        columna.setSpacing(12)

        self.entrada = TarjetaEntrada(self)
        self.entrada.probar.connect(self.probar)
        self.entrada.usar.connect(self.usar)
        self.entrada.buscar.connect(self.buscar)
        self.entrada.abrir_imagen.connect(self.abrir_imagen)

        columna.addWidget(self.entrada)
        columna.addStretch(1)
