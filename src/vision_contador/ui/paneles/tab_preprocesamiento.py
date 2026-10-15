"""Pestana Preprocesamiento: interruptor general, etapas, parametros y ROI."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...core.modelos import ETAPAS_CONFIGURABLES, EtapaPreproc, ParametrosPreproc, Rect
from .. import tema
from ..widgets.fila_control import FilaDeslizador, FilaDiscreta
from ..widgets.indicadores import Insignia
from ..widgets.panel import Tarjeta, etiqueta_mono, etiqueta_sec, separador

KERNELS = [3, 5, 7]


class FilaEtapa(QWidget):
    """Casilla, nombre, semana del curso y estado de la ultima captura."""

    cambiada = Signal(bool)

    def __init__(self, etapa: EtapaPreproc, activa: bool, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.etapa = etapa

        fila = QHBoxLayout(self)
        fila.setContentsMargins(0, 3, 0, 3)
        fila.setSpacing(8)

        self.casilla = QCheckBox(etapa.etiqueta, self)
        self.casilla.setChecked(activa)
        self.casilla.setFont(tema.Fuentes.cuerpo(13))
        self.casilla.toggled.connect(self.cambiada)

        self.semana = Insignia(etapa.semana, tema.TEXTO_SEC, self)
        self.estado = Insignia("—", tema.TEXTO_SEC, self)
        self.estado.setMinimumWidth(68)

        fila.addWidget(self.casilla, 1)
        fila.addWidget(self.semana)
        fila.addWidget(self.estado)

    def fijar_estado(self, aplicada: bool | None) -> None:
        """Verde 'Aplicada' o gris 'Omitida', segun la ultima captura."""
        if aplicada is None:
            self.estado.setText("—")
            self.estado.fijar_color(tema.TEXTO_SEC)
        elif aplicada:
            self.estado.setText("Aplicada")
            self.estado.fijar_color(tema.OK)
        else:
            self.estado.setText("Omitida")
            self.estado.fijar_color(tema.TEXTO_SEC)


class TabPreprocesamiento(QWidget):
    """Controla todos los parametros de la cadena de PDI."""

    parametros_cambiados = Signal()
    definir_roi = Signal()
    restablecer = Signal()
    guardar = Signal()

    def __init__(self, params: ParametrosPreproc, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._params = params
        self._silenciar = False

        columna = QVBoxLayout(self)
        columna.setContentsMargins(12, 12, 12, 12)
        columna.setSpacing(12)

        columna.addWidget(self._construir_interruptor())
        columna.addWidget(self._construir_etapas())
        columna.addWidget(self._construir_parametros())
        columna.addWidget(self._construir_roi())
        columna.addStretch(1)
        columna.addLayout(self._construir_botones())

    # --- Secciones ---------------------------------------------------------
    def _construir_interruptor(self) -> QWidget:
        caja = QWidget(self)
        columna = QVBoxLayout(caja)
        columna.setContentsMargins(2, 0, 2, 0)
        columna.setSpacing(3)

        self.activo = QCheckBox("Preprocesamiento activo", caja)
        self.activo.setChecked(self._params.activo)
        self.activo.setFont(tema.Fuentes.cuerpo(13, negrita=True))
        self.activo.toggled.connect(self._al_cambiar_activo)

        nota = etiqueta_sec("Desactívelo para comparar la detección sin mejoras", 11)
        nota.setContentsMargins(22, 0, 0, 0)

        columna.addWidget(self.activo)
        columna.addWidget(nota)
        return caja

    def _construir_etapas(self) -> Tarjeta:
        tarjeta = Tarjeta("ETAPAS", parent=self)
        self.filas: dict[EtapaPreproc, FilaEtapa] = {}
        for etapa in ETAPAS_CONFIGURABLES:
            fila = FilaEtapa(etapa, self._params.etapas_activas.get(etapa, True), tarjeta)
            fila.cambiada.connect(self._al_cambiar_parametro)
            self.filas[etapa] = fila
            tarjeta.cuerpo.addWidget(fila)
        return tarjeta

    def _construir_parametros(self) -> Tarjeta:
        tarjeta = Tarjeta("PARÁMETROS", parent=self)

        self.gamma = FilaDeslizador(
            "Gamma", 0.3, 1.5, self._params.gamma, 0.01, lambda v: f"{v:.2f}", tarjeta
        )
        self.kernel = FilaDiscreta(
            "Tamaño de máscara de suavizado",
            KERNELS,
            self._params.kernel_suavizado,
            lambda v: f"{KERNELS[int(v)]} x {KERNELS[int(v)]}",
            tarjeta,
        )
        self.umbral_brillo = FilaDeslizador(
            "Umbral de brillo para gamma", 0, 255, self._params.umbral_brillo, 1,
            lambda v: f"{int(v)}", tarjeta,
        )
        self.umbral_contraste = FilaDeslizador(
            "Umbral de contraste para ecualización", 0, 128, self._params.umbral_contraste, 1,
            lambda v: f"{int(v)}", tarjeta,
        )
        self.confianza = FilaDeslizador(
            "Confianza mínima de YOLO", 0.05, 0.95, self._params.confianza_minima, 0.01,
            lambda v: f"{v:.2f}", tarjeta,
        )

        for control in (
            self.gamma, self.kernel, self.umbral_brillo,
            self.umbral_contraste, self.confianza,
        ):
            control.valor_cambiado.connect(self._al_cambiar_parametro)
            tarjeta.cuerpo.addWidget(control)

        tarjeta.cuerpo.addWidget(separador())
        self.adaptativo = QCheckBox("Modo adaptativo", tarjeta)
        self.adaptativo.setChecked(self._params.modo_adaptativo)
        self.adaptativo.toggled.connect(self._al_cambiar_parametro)
        nota = etiqueta_sec("Aplica cada corrección solo si el histograma lo requiere", 11)
        nota.setContentsMargins(22, 0, 0, 0)
        nota.setWordWrap(True)
        tarjeta.cuerpo.addWidget(self.adaptativo)
        tarjeta.cuerpo.addWidget(nota)
        return tarjeta

    def _construir_roi(self) -> Tarjeta:
        tarjeta = Tarjeta("REGIÓN DE INTERÉS", parent=self)
        self.boton_roi = QPushButton("Definir región en el video", tarjeta)
        self.boton_roi.setCursor(Qt.CursorShape.PointingHandCursor)
        self.boton_roi.clicked.connect(self.definir_roi)
        tarjeta.cuerpo.addWidget(self.boton_roi)

        fila = QHBoxLayout()
        fila.setSpacing(14)
        self._valores_roi: dict[str, object] = {}
        for clave, etiqueta in (("x", "X"), ("y", "Y"), ("ancho", "Ancho"), ("alto", "Alto")):
            celda = QWidget(tarjeta)
            columna = QVBoxLayout(celda)
            columna.setContentsMargins(0, 0, 0, 0)
            columna.setSpacing(1)
            titulo = etiqueta_sec(etiqueta, 11)
            valor = etiqueta_mono("0", 13, tema.TEXTO)
            columna.addWidget(titulo)
            columna.addWidget(valor)
            self._valores_roi[clave] = valor
            fila.addWidget(celda)
        fila.addStretch(1)
        tarjeta.cuerpo.addLayout(fila)
        self.fijar_roi(self._params.roi)
        return tarjeta

    def _construir_botones(self) -> QHBoxLayout:
        fila = QHBoxLayout()
        fila.setSpacing(10)
        self.boton_restablecer = QPushButton("Restablecer valores", self)
        self.boton_guardar = QPushButton("Guardar configuración", self)
        self.boton_guardar.setObjectName("Primario")
        for boton, senal in (
            (self.boton_restablecer, self.restablecer),
            (self.boton_guardar, self.guardar),
        ):
            boton.setCursor(Qt.CursorShape.PointingHandCursor)
            boton.clicked.connect(senal)
        fila.addWidget(self.boton_restablecer, 1)
        fila.addWidget(self.boton_guardar, 1)
        return fila

    # --- Estado ------------------------------------------------------------
    def _al_cambiar_activo(self, activo: bool) -> None:
        for fila in self.filas.values():
            fila.setEnabled(activo)
        self._al_cambiar_parametro()

    def _al_cambiar_parametro(self, *_args) -> None:
        if self._silenciar:
            return
        self.parametros_cambiados.emit()

    def leer(self) -> ParametrosPreproc:
        """Vuelca los controles a un objeto de parametros."""
        return ParametrosPreproc(
            activo=self.activo.isChecked(),
            gamma=self.gamma.valor_actual(),
            kernel_suavizado=self.kernel.valor_actual(),
            umbral_brillo=int(self.umbral_brillo.valor_actual()),
            umbral_contraste=int(self.umbral_contraste.valor_actual()),
            confianza_minima=self.confianza.valor_actual(),
            modo_adaptativo=self.adaptativo.isChecked(),
            etapas_activas={e: f.casilla.isChecked() for e, f in self.filas.items()},
            roi=self._params.roi,
        )

    def escribir(self, params: ParametrosPreproc) -> None:
        """Lleva los valores a los controles sin disparar senales."""
        self._silenciar = True
        try:
            self._params = params
            self.activo.setChecked(params.activo)
            self.gamma.fijar_valor(params.gamma)
            self.kernel.fijar_valor(params.kernel_suavizado)
            self.umbral_brillo.fijar_valor(params.umbral_brillo)
            self.umbral_contraste.fijar_valor(params.umbral_contraste)
            self.confianza.fijar_valor(params.confianza_minima)
            self.adaptativo.setChecked(params.modo_adaptativo)
            for etapa, fila in self.filas.items():
                fila.casilla.setChecked(params.etapas_activas.get(etapa, True))
                fila.setEnabled(params.activo)
            self.fijar_roi(params.roi)
        finally:
            self._silenciar = False
        self.parametros_cambiados.emit()

    def fijar_roi(self, roi: Rect) -> None:
        self._params.roi = roi
        for clave, valor in (
            ("x", roi.x), ("y", roi.y), ("ancho", roi.ancho), ("alto", roi.alto)
        ):
            self._valores_roi[clave].setText(str(valor))

    def fijar_estados(self, aplicadas: dict[EtapaPreproc, bool] | None) -> None:
        """Marca cada etapa como Aplicada u Omitida tras una captura."""
        for etapa, fila in self.filas.items():
            fila.fijar_estado(None if aplicadas is None else aplicadas.get(etapa, False))
