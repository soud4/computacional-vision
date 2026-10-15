"""Puente entre los arreglos de numpy del nucleo y las imagenes de Qt."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PySide6.QtGui import QImage, QPixmap

from ..core.modelos import Imagen


def a_qimage(imagen: Imagen) -> QImage:
    """Convierte un arreglo RGB uint8 en QImage.

    Se copia el buffer a proposito: QImage no toma posesion de la memoria de
    numpy y, si el arreglo se libera antes que la imagen, Qt dibuja basura.
    """
    arreglo = np.ascontiguousarray(imagen[..., :3].astype(np.uint8))
    alto, ancho = arreglo.shape[:2]
    return QImage(arreglo.data, ancho, alto, ancho * 3, QImage.Format.Format_RGB888).copy()


def a_pixmap(imagen: Imagen) -> QPixmap:
    return QPixmap.fromImage(a_qimage(imagen))


class ImagenIlegible(ValueError):
    """El archivo no es una imagen que Qt sepa leer."""


def desde_archivo(ruta: str | Path) -> Imagen:
    """Lee un PNG, JPG, BMP o WebP y lo devuelve como arreglo RGB uint8.

    El decodificador es el de Qt y no el de OpenCV porque PySide6 es dependencia
    base de la aplicacion, mientras ``cv2`` es opcional: subir una imagen tiene
    que funcionar tambien en una instalacion minima.
    """
    imagen = QImage(str(ruta))
    if imagen.isNull():
        raise ImagenIlegible(f"no se pudo leer la imagen «{Path(ruta).name}»")

    imagen = imagen.convertToFormat(QImage.Format.Format_RGB888)
    ancho, alto = imagen.width(), imagen.height()
    # Qt alinea cada fila a cuatro bytes, asi que el arreglo se reconstruye con
    # el paso real (``bytesPerLine``) y luego se recortan los bytes de relleno:
    # suponer ``ancho * 3`` inclina la imagen en diagonal.
    crudo = np.frombuffer(imagen.constBits(), dtype=np.uint8, count=imagen.sizeInBytes())
    filas = crudo.reshape(alto, imagen.bytesPerLine())
    return np.ascontiguousarray(filas[:, : ancho * 3].reshape(alto, ancho, 3))
