"""Pruebas de las fuentes de video que no son la camara."""

from __future__ import annotations

import numpy as np
import pytest

from vision_contador.adapters.camara_mock import CamaraMock
from vision_contador.adapters.fuente_conmutable import FuenteConmutable
from vision_contador.adapters.fuente_imagen import FuenteImagen
from vision_contador.ports.camara import CamaraNoDisponible


def imagen(valor: int, alto: int = 4, ancho: int = 6) -> np.ndarray:
    return np.full((alto, ancho, 3), valor, dtype=np.uint8)


class FuenteRota(FuenteImagen):
    """Una fuente que no abre, como una camara desconectada."""

    def abrir(self) -> None:
        raise CamaraNoDisponible("no hay nadie en casa")


def test_la_imagen_se_entrega_una_vez_y_se_captura_siempre():
    fuente = FuenteImagen(imagen(90), "mesa.png")
    fuente.abrir()

    assert fuente.leer_cuadro() is not None
    # El visor conserva el ultimo cuadro, asi que no hace falta repetirlo.
    assert fuente.leer_cuadro() is None
    # Capturar, en cambio, tiene que funcionar tantas veces como se pulse.
    assert fuente.capturar_estable().shape == (4, 6, 3)
    assert fuente.capturar_estable()[0, 0, 0] == 90
    assert fuente.tamano == (6, 4)
    assert fuente.disponible


def test_la_captura_no_devuelve_el_arreglo_interno():
    """Quien recibe la captura la puede modificar sin corromper la fuente."""
    fuente = FuenteImagen(imagen(10), "mesa.png")
    fuente.abrir()
    copia = fuente.capturar_estable()
    copia[:] = 255
    assert fuente.capturar_estable()[0, 0, 0] == 10


def test_conmutar_entrega_los_cuadros_de_la_fuente_nueva():
    camara = CamaraMock(fps=30)
    conmutable = FuenteConmutable(camara)
    conmutable.abrir()
    assert conmutable.leer_cuadro() is not None

    conmutable.cambiar(FuenteImagen(imagen(200), "mesa.png"))
    assert conmutable.capturar_estable()[0, 0, 0] == 200
    assert not camara.disponible          # la anterior se cerro
    assert conmutable.original is camara  # y sigue disponible para volver

    conmutable.cambiar(conmutable.original)
    assert conmutable.capturar_estable()[0, 0, 0] != 200


def test_si_la_fuente_nueva_no_abre_se_conserva_la_anterior():
    anterior = FuenteImagen(imagen(30), "antes.png")
    conmutable = FuenteConmutable(anterior)
    conmutable.abrir()

    with pytest.raises(CamaraNoDisponible):
        conmutable.cambiar(FuenteRota(imagen(40), "rota.png"))

    assert conmutable.activa is anterior
    assert conmutable.capturar_estable()[0, 0, 0] == 30
