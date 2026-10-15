"""Hilos de trabajo.

La camara, el puerto serial y la inferencia bloquean. Si cualquiera de los tres
corriera en el hilo de la interfaz, la ventana se congelaria justo durante la
demostracion. Aqui viven los hilos y los puentes de senales; la regla es que
ningun widget se toca fuera de un slot conectado a estas senales.
"""

from __future__ import annotations

import time

from PySide6.QtCore import QObject, QThread, Signal

from ..core.modelos import Direccion, ParametrosPreproc
from ..core.pipeline import Pipeline
from ..ports.camara import FuenteVideo
from ..ports.detector import Detector


class HiloCamara(QThread):
    """Lee cuadros de la fuente de video y los publica a ritmo constante."""

    cuadro_listo = Signal(object)
    fps_medidos = Signal(float)
    fallo = Signal(str)

    def __init__(self, camara: FuenteVideo, fps: int = 30, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._camara = camara
        self._periodo = 1.0 / max(fps, 1)
        self._corriendo = False
        #: Mientras hay una captura en curso se deja de leer, para no competir
        #: con ella por la camara.
        self.pausado = False

    def run(self) -> None:
        self._corriendo = True
        marcas: list[float] = []
        while self._corriendo:
            inicio = time.perf_counter()
            if not self.pausado:
                try:
                    cuadro = self._camara.leer_cuadro()
                except Exception as error:  # el hilo no puede morir en silencio
                    self.fallo.emit(str(error))
                    break
                if cuadro is not None:
                    self.cuadro_listo.emit(cuadro)
                    marcas.append(inicio)
                    if len(marcas) > 20:
                        marcas.pop(0)
                    if len(marcas) > 1:
                        lapso = marcas[-1] - marcas[0]
                        if lapso > 0:
                            self.fps_medidos.emit((len(marcas) - 1) / lapso)

            resto = self._periodo - (time.perf_counter() - inicio)
            if resto > 0:
                self.msleep(int(resto * 1000))

    def detener(self) -> None:
        self._corriendo = False
        self.wait(1500)


class HiloCaptura(QThread):
    """Corre una pasada completa del pipeline fuera del hilo de la interfaz."""

    progreso = Signal(int, str)
    terminado = Signal(object)
    fallo = Signal(str)

    def __init__(
        self, pipeline: Pipeline, params: ParametrosPreproc, parent: QObject | None = None
    ) -> None:
        super().__init__(parent)
        self._pipeline = pipeline
        self._params = params

    def run(self) -> None:
        try:
            resultado = self._pipeline.ejecutar(self._params, self._informar)
        except Exception as error:
            self.fallo.emit(str(error))
        else:
            self.terminado.emit(resultado)

    def _informar(self, indice: int, texto: str) -> None:
        self.progreso.emit(indice, texto)


class HiloCargaModelo(QThread):
    """Carga los pesos del detector sin congelar la ventana.

    YOLO tarda unos segundos en cargar y en hacer su primera inferencia. Si eso
    ocurriera dentro de la primera captura, el usuario veria la aplicacion
    detenida justo al pulsar el boton.
    """

    listo = Signal(str)
    fallo = Signal(str)

    def __init__(self, detector: Detector, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._detector = detector

    def run(self) -> None:
        try:
            self._detector.cargar()
        except Exception as error:
            self.fallo.emit(str(error))
        else:
            self.listo.emit(self._detector.nombre)


class HiloProbarFuente(QThread):
    """Tantea una fuente de video sin congelar la ventana.

    Abrir una camara de red que no responde tarda lo que dure su tiempo limite
    -varios segundos-, asi que la prueba no puede correr en el hilo de la
    interfaz. Emite ``(ok, resumen)``: la resolucion y los FPS si responde, o el
    motivo del fallo si no.
    """

    terminado = Signal(bool, str)

    def __init__(self, destino: str, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._destino = destino

    def run(self) -> None:
        try:
            from ..adapters.camara_opencv import probar
        except ImportError as error:
            self.terminado.emit(False, f"falta OpenCV ({error})")
            return

        try:
            resultado = probar(self._destino)
        except Exception as error:  # el hilo no puede morir en silencio
            self.terminado.emit(False, str(error))
        else:
            self.terminado.emit(resultado.ok, resultado.resumen)


class PuenteArduino(QObject):
    """Convierte los eventos del enlace serial en senales de Qt.

    El adaptador llama a estos metodos desde su propio hilo. Las senales de Qt
    hacen el cruce al hilo de la interfaz por si solas, que es exactamente por
    lo que existe esta clase.
    """

    linea = Signal(object, str)  # (Direccion, texto)
    conexion_cambiada = Signal(bool, str)
    boton_pulsado = Signal()

    def al_recibir(self, linea: str) -> None:
        direccion = Direccion.ERROR if linea.startswith("ERR:") else Direccion.RECIBIDO
        self.linea.emit(direccion, linea)

    def al_enviar(self, linea: str) -> None:
        self.linea.emit(Direccion.ENVIADO, linea)

    def al_cambiar_conexion(self, conectado: bool, detalle: str) -> None:
        self.conexion_cambiada.emit(conectado, detalle)

    def al_pulsar_boton(self) -> None:
        self.boton_pulsado.emit()
