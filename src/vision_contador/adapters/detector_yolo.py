"""Detector local con YOLO de Ultralytics."""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np

from ..core.config import ConfigDetector
from ..core.modelos import Deteccion, Imagen, Rect
from ..ports.detector import Detector, DetectorNoDisponible, ResultadoDeteccion


def _dispositivo() -> str:
    """``cuda`` si hay GPU utilizable, ``cpu`` en caso contrario.

    Se comprueba en tiempo de ejecucion y no por la variante de torch instalada:
    una rueda compilada con CUDA sigue cayendo a CPU si no hay tarjeta o si el
    controlador no responde.
    """
    try:
        import torch
    except ImportError:
        return "cpu"
    return "cuda" if torch.cuda.is_available() else "cpu"


class DetectorYolo(Detector):
    """Ejecuta YOLO localmente sobre la imagen ya preprocesada."""

    def __init__(self, config: ConfigDetector) -> None:
        self._config = config
        self._modelo = None
        self._dispositivo = _dispositivo()
        self._nombres: dict[int, str] = {}

    def cargar(self) -> None:
        """Carga los pesos y hace una inferencia en blanco.

        La primera pasada de un modelo recien cargado tarda varios segundos
        mientras se reservan los bufers. Pagarla aqui, al arrancar, evita que la
        primera captura del usuario parezca que se colgo.
        """
        if self._modelo is not None:
            return

        try:
            from ultralytics import YOLO
        except ImportError as error:
            raise DetectorNoDisponible(
                "falta la dependencia ultralytics (uv pip install -e '.[yolo]')"
            ) from error

        pesos = self._config.pesos
        try:
            # Si no es una ruta existente, ultralytics lo trata como nombre de
            # modelo y lo descarga la primera vez.
            modelo = YOLO(pesos)
            modelo.to(self._dispositivo)
            modelo.predict(
                np.zeros((640, 640, 3), np.uint8),
                device=self._dispositivo,
                verbose=False,
            )
        except Exception as error:
            raise DetectorNoDisponible(
                f"no se pudieron cargar los pesos «{pesos}»: {error}"
            ) from error

        self._modelo = modelo
        self._nombres = dict(modelo.names)

    def detectar(self, imagen: Imagen, confianza_minima: float) -> ResultadoDeteccion:
        if self._modelo is None:
            self.cargar()

        inicio = time.perf_counter()
        salida = self._modelo.predict(
            imagen,
            conf=confianza_minima,
            device=self._dispositivo,
            verbose=False,
        )
        ms = int((time.perf_counter() - inicio) * 1000)

        detecciones: list[Deteccion] = []
        for resultado in salida:
            cajas = resultado.boxes
            if cajas is None:
                continue
            for clase, confianza, xyxy in zip(
                cajas.cls.tolist(), cajas.conf.tolist(), cajas.xyxy.tolist()
            ):
                x1, y1, x2, y2 = (round(v) for v in xyxy)
                detecciones.append(
                    Deteccion(
                        # El nombre que sale de aqui es el de COCO en ingles;
                        # el pipeline lo traduce al espanol mas adelante.
                        clase=self._nombres.get(int(clase), str(int(clase))),
                        confianza=float(confianza),
                        caja=Rect(x1, y1, x2 - x1, y2 - y1),
                    )
                )

        return ResultadoDeteccion(detecciones, ms, self.nombre)

    @property
    def nombre(self) -> str:
        etiqueta = self._config.modelo or Path(self._config.pesos).stem
        return etiqueta if self._dispositivo == "cpu" else f"{etiqueta} · GPU"

    @property
    def listo(self) -> bool:
        return self._modelo is not None
