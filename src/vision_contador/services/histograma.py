"""Histograma de luminancia y sus estadisticos."""

from __future__ import annotations

import numpy as np

from ..core.modelos import Histograma, Imagen

#: Coeficientes de luminancia de la Rec. 601, los mismos que usa cv2.COLOR_RGB2GRAY.
_PESOS_LUMA = np.array([0.299, 0.587, 0.114], dtype=np.float32)


def luminancia(imagen: Imagen) -> np.ndarray:
    """Canal de luminancia en uint8 a partir de una imagen RGB."""
    if imagen.ndim == 2:
        return imagen.astype(np.uint8)
    return (imagen[..., :3].astype(np.float32) @ _PESOS_LUMA).astype(np.uint8)


def calcular(imagen: Imagen) -> Histograma:
    """Histograma de 256 niveles normalizado, con brillo medio y contraste.

    El contraste se mide como la desviacion estandar de la luminancia: es la
    definicion que usa el modo adaptativo para decidir si vale la pena ecualizar.
    """
    luma = luminancia(imagen)
    conteos = np.bincount(luma.ravel(), minlength=256).astype(np.float32)
    maximo = float(conteos.max()) or 1.0
    return Histograma(
        valores=conteos / maximo,
        brillo_medio=float(luma.mean()),
        contraste=float(luma.std()),
    )
