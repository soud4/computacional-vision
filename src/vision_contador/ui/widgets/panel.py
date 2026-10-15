"""Panel con borde y barra de titulo, la unidad basica del layout."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .. import tema


class Panel(QFrame):
    """Marco de 1 px con cabecera de 28 px y un cuerpo para el contenido.

    Las acciones que se pasan se alinean a la derecha de la cabecera, como los
    desplegables de la consola serial o el selector de etapa del visor
    preprocesado.
    """

    def __init__(
        self,
        titulo: str,
        acciones: list[QWidget] | None = None,
        margenes: tuple[int, int, int, int] = (12, 12, 12, 12),
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("Panel")

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(1, 1, 1, 1)
        raiz.setSpacing(0)

        self.cabecera = QFrame(self)
        self.cabecera.setObjectName("CabeceraPanel")
        self.cabecera.setFixedHeight(tema.ALTO_CABECERA_PANEL)
        fila = QHBoxLayout(self.cabecera)
        fila.setContentsMargins(11, 0, 8, 0)
        fila.setSpacing(8)

        self.titulo = QLabel(titulo, self.cabecera)
        self.titulo.setObjectName("TituloPanel")
        self.titulo.setFont(tema.Fuentes.titulo_panel())
        fila.addWidget(self.titulo)
        fila.addStretch(1)
        for accion in acciones or []:
            accion.setParent(self.cabecera)
            fila.addWidget(accion)

        raiz.addWidget(self.cabecera)

        self._cuerpo = QWidget(self)
        # La regla se limita al propio cuerpo. Sin el selector, una hoja de
        # estilo puesta en un widget se hereda a todos sus hijos y gana a la
        # hoja global: los botones de dentro del panel se quedaban sin fondo y
        # parecian texto suelto.
        self._cuerpo.setObjectName("CuerpoPanel")
        self._cuerpo.setStyleSheet("QWidget#CuerpoPanel { background: transparent; }")
        self.cuerpo = QVBoxLayout(self._cuerpo)
        self.cuerpo.setContentsMargins(*margenes)
        self.cuerpo.setSpacing(10)
        raiz.addWidget(self._cuerpo, 1)

    def agregar(self, widget: QWidget, estirar: int = 0) -> None:
        self.cuerpo.addWidget(widget, estirar)


class Tarjeta(Panel):
    """Panel compacto para las tarjetas de la columna derecha."""

    def __init__(
        self, titulo: str, acciones: list[QWidget] | None = None, parent: QWidget | None = None
    ) -> None:
        super().__init__(titulo, acciones, margenes=(12, 10, 12, 12), parent=parent)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)


def separador() -> QFrame:
    """Linea horizontal de 1 px para dividir secciones dentro de una tarjeta."""
    linea = QFrame()
    linea.setFrameShape(QFrame.Shape.HLine)
    linea.setFixedHeight(1)
    linea.setStyleSheet(f"background-color: {tema.BORDE}; border: none;")
    return linea


def etiqueta_sec(texto: str, tam: int = 12) -> QLabel:
    """Texto secundario gris."""
    lbl = QLabel(texto)
    lbl.setObjectName("TextoSecundario")
    lbl.setFont(tema.Fuentes.cuerpo(tam))
    lbl.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
    return lbl


def etiqueta_mono(texto: str, tam: int = 12, color: str = tema.TEXTO) -> QLabel:
    """Valor numerico o nombre de puerto, en monoespaciada."""
    lbl = QLabel(texto)
    lbl.setFont(tema.Fuentes.monoespaciada(tam))
    lbl.setStyleSheet(f"color: {color}; background: transparent;")
    return lbl
