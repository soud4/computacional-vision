"""Modelos de datos del dominio.

Este modulo no importa Qt, OpenCV ni pyserial: es el vocabulario comun que
comparten el nucleo, los servicios, los adaptadores y la interfaz.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

import numpy as np

# Una imagen es siempre un arreglo RGB de forma (alto, ancho, 3) y tipo uint8.
Imagen = np.ndarray


class EstadoApp(Enum):
    """Estado principal de la maquina de estados de la aplicacion."""

    LISTO = "listo"
    PENSANDO = "pensando"
    MOSTRANDO = "mostrando"
    SIN_DETECCION = "sin_deteccion"
    ERROR = "error"

    @property
    def etiqueta(self) -> str:
        return {
            EstadoApp.LISTO: "Listo · Esperando captura",
            EstadoApp.PENSANDO: "Pensando… Analizando imagen",
            EstadoApp.MOSTRANDO: "Listo · Resultado mostrado",
            EstadoApp.SIN_DETECCION: "Sin detecciones en la imagen",
            EstadoApp.ERROR: "Error en el procesamiento",
        }[self]

    @property
    def etiqueta_corta(self) -> str:
        """Lo que cabe en la barra superior; la larga va al tooltip."""
        return {
            EstadoApp.LISTO: "Listo",
            EstadoApp.PENSANDO: "Pensando…",
            EstadoApp.MOSTRANDO: "Listo",
            EstadoApp.SIN_DETECCION: "Sin detecciones",
            EstadoApp.ERROR: "Error",
        }[self]

    @property
    def severidad(self) -> str:
        """Clave de color: ok, procesando o error."""
        return {
            EstadoApp.LISTO: "ok",
            EstadoApp.PENSANDO: "procesando",
            EstadoApp.MOSTRANDO: "ok",
            EstadoApp.SIN_DETECCION: "error",
            EstadoApp.ERROR: "error",
        }[self]


class EtapaPreproc(Enum):
    """Las siete etapas que expone el desplegable del panel PREPROCESADA."""

    ORIGINAL = "original"
    GEOMETRICA = "geometrica"
    GAMMA = "gamma"
    ECUALIZACION = "ecualizacion"
    SUAVIZADO = "suavizado"
    MASCARA_ROI = "mascara_roi"
    RESULTADO = "resultado"

    @property
    def etiqueta(self) -> str:
        return {
            EtapaPreproc.ORIGINAL: "Original",
            EtapaPreproc.GEOMETRICA: "Transformación geométrica",
            EtapaPreproc.GAMMA: "Corrección gamma",
            EtapaPreproc.ECUALIZACION: "Ecualización",
            EtapaPreproc.SUAVIZADO: "Suavizado",
            EtapaPreproc.MASCARA_ROI: "Máscara de región",
            EtapaPreproc.RESULTADO: "Resultado final",
        }[self]

    @property
    def semana(self) -> str:
        """Semana del curso en la que se vio la tecnica (para la pestana)."""
        return {
            EtapaPreproc.ORIGINAL: "",
            EtapaPreproc.GEOMETRICA: "Sem. 6",
            EtapaPreproc.GAMMA: "Sem. 7",
            EtapaPreproc.ECUALIZACION: "Sem. 4",
            EtapaPreproc.SUAVIZADO: "Sem. 4",
            EtapaPreproc.MASCARA_ROI: "Sem. 7",
            EtapaPreproc.RESULTADO: "",
        }[self]


#: Etapas configurables, en el orden en que se aplican. Excluye ORIGINAL y RESULTADO,
#: que son los extremos de la cadena y no se pueden desactivar.
ETAPAS_CONFIGURABLES: tuple[EtapaPreproc, ...] = (
    EtapaPreproc.GEOMETRICA,
    EtapaPreproc.GAMMA,
    EtapaPreproc.ECUALIZACION,
    EtapaPreproc.SUAVIZADO,
    EtapaPreproc.MASCARA_ROI,
)


class Led(Enum):
    """Los tres LEDs de la protoboard."""

    AMARILLO = "AMARILLO"
    VERDE = "VERDE"
    ROJO = "ROJO"

    @property
    def etiqueta(self) -> str:
        return self.value.capitalize()


@dataclass(frozen=True, slots=True)
class Rect:
    """Rectangulo en pixeles de la imagen."""

    x: int
    y: int
    ancho: int
    alto: int

    @property
    def x2(self) -> int:
        return self.x + self.ancho

    @property
    def y2(self) -> int:
        return self.y + self.alto


@dataclass(frozen=True, slots=True)
class Deteccion:
    """Un objeto detectado por el modelo."""

    clase: str
    confianza: float
    caja: Rect

    @property
    def etiqueta(self) -> str:
        """Texto que se dibuja sobre la caja: 'Botella 0.91'."""
        return f"{self.clase} {self.confianza:.2f}"


@dataclass(frozen=True, slots=True)
class ConteoClase:
    """Cuantos objetos de una clase hay en la captura."""

    clase: str
    cantidad: int


@dataclass(frozen=True, slots=True)
class Histograma:
    """Histograma de luminancia con sus estadisticos."""

    valores: np.ndarray  # 256 posiciones, normalizadas a [0, 1]
    brillo_medio: float
    contraste: float


@dataclass(slots=True)
class ParametrosPreproc:
    """Los parametros que controla la pestana Preprocesamiento."""

    activo: bool = True
    gamma: float = 0.65
    kernel_suavizado: int = 3
    umbral_brillo: int = 90
    umbral_contraste: int = 40
    confianza_minima: float = 0.50
    modo_adaptativo: bool = True
    etapas_activas: dict[EtapaPreproc, bool] = field(
        default_factory=lambda: {etapa: True for etapa in ETAPAS_CONFIGURABLES}
    )
    roi: Rect = Rect(120, 80, 1040, 560)

    def etapa_activa(self, etapa: EtapaPreproc) -> bool:
        if not self.activo:
            return False
        return self.etapas_activas.get(etapa, True)


@dataclass(slots=True)
class ResultadoCaptura:
    """Todo lo que produce una pasada completa del pipeline."""

    momento: datetime
    capturada: Imagen
    etapas: dict[EtapaPreproc, Imagen]
    etapas_aplicadas: dict[EtapaPreproc, bool]
    detecciones: list[Deteccion]
    conteos: list[ConteoClase]
    frase: str
    modelo: str
    ms_inferencia: int
    histograma_antes: Histograma
    histograma_despues: Histograma

    @property
    def total(self) -> int:
        return sum(c.cantidad for c in self.conteos)

    @property
    def resolucion(self) -> tuple[int, int]:
        alto, ancho = self.capturada.shape[:2]
        return ancho, alto

    @property
    def preprocesada(self) -> Imagen:
        return self.etapas[EtapaPreproc.RESULTADO]

    @property
    def hora(self) -> str:
        return self.momento.strftime("%H:%M:%S")


class Direccion(Enum):
    """De donde viene una linea de la consola serial."""

    ENVIADO = "enviado"
    RECIBIDO = "recibido"
    ERROR = "error"
    INFO = "info"

    @property
    def flecha(self) -> str:
        return {
            Direccion.ENVIADO: "→",
            Direccion.RECIBIDO: "←",
            Direccion.ERROR: "✕",
            Direccion.INFO: "·",
        }[self]


@dataclass(frozen=True, slots=True)
class LineaSerial:
    """Una linea del monitor serial."""

    momento: datetime
    direccion: Direccion
    texto: str

    def formatear(self) -> str:
        return f"[{self.momento.strftime('%H:%M:%S')}] {self.direccion.flecha} {self.texto}"
