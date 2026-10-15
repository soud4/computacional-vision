"""Escritura de PNG sin dependencias externas.

El registro necesita guardar las imagenes de cada captura, pero los servicios no
deben depender de OpenCV ni de Qt: en modo demo ninguno de los dos esta
necesariamente instalado. Un codificador PNG son treinta lineas sobre ``zlib``,
asi que se escribe aqui y el nucleo queda limpio.
"""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

import numpy as np

from ..core.modelos import Imagen


def _trozo(tipo: bytes, datos: bytes) -> bytes:
    return (
        struct.pack(">I", len(datos))
        + tipo
        + datos
        + struct.pack(">I", zlib.crc32(tipo + datos) & 0xFFFFFFFF)
    )


def guardar_png(imagen: Imagen, ruta: Path) -> Path:
    """Escribe un arreglo RGB uint8 como PNG de color verdadero."""
    arreglo = np.ascontiguousarray(imagen[..., :3].astype(np.uint8))
    alto, ancho = arreglo.shape[:2]

    # Cada fila del PNG va precedida por un byte de filtro; se usa 0 (sin filtro),
    # que zlib comprime igual de bien para estas imagenes.
    filas = np.hstack(
        [np.zeros((alto, 1), dtype=np.uint8), arreglo.reshape(alto, ancho * 3)]
    )

    cabecera = struct.pack(">IIBBBBB", ancho, alto, 8, 2, 0, 0, 0)
    contenido = (
        b"\x89PNG\r\n\x1a\n"
        + _trozo(b"IHDR", cabecera)
        + _trozo(b"IDAT", zlib.compress(filas.tobytes(), 6))
        + _trozo(b"IEND", b"")
    )
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_bytes(contenido)
    return ruta
