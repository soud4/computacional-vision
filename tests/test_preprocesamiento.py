"""Pruebas del preprocesamiento: que cada tecnica haga lo que dice."""

from __future__ import annotations

import numpy as np
import pytest

from vision_contador.adapters import preproc_numpy as pre
from vision_contador.core.modelos import ETAPAS_CONFIGURABLES, EtapaPreproc, ParametrosPreproc, Rect
from vision_contador.services.histograma import calcular, luminancia


@pytest.fixture
def imagen_oscura() -> np.ndarray:
    """Una imagen con el histograma apelotonado en los valores bajos."""
    rng = np.random.default_rng(3)
    return np.clip(rng.normal(55, 14, (120, 160, 3)), 0, 255).astype(np.uint8)


class TestTecnicas:
    def test_gamma_menor_que_uno_aclara(self, imagen_oscura):
        clara = pre.correccion_gamma(imagen_oscura, 0.5)
        assert luminancia(clara).mean() > luminancia(imagen_oscura).mean()

    def test_gamma_mayor_que_uno_oscurece(self, imagen_oscura):
        oscura = pre.correccion_gamma(imagen_oscura, 1.8)
        assert luminancia(oscura).mean() < luminancia(imagen_oscura).mean()

    def test_gamma_uno_no_cambia_nada(self, imagen_oscura):
        assert np.array_equal(pre.correccion_gamma(imagen_oscura, 1.0), imagen_oscura)

    def test_ecualizacion_abre_el_contraste(self, imagen_oscura):
        antes = calcular(imagen_oscura).contraste
        despues = calcular(pre.ecualizar_histograma(imagen_oscura)).contraste
        assert despues > antes

    def test_ecualizacion_conserva_el_tono(self):
        """Ecualizar los tres canales por separado volveria rosada la madera."""
        madera = np.zeros((40, 40, 3), np.uint8)
        madera[:] = (140, 110, 70)
        madera[:20] = (90, 70, 45)
        resultado = pre.ecualizar_histograma(madera)
        # El rojo sigue dominando sobre el azul en toda la imagen.
        assert resultado[..., 0].mean() > resultado[..., 2].mean()

    def test_suavizado_reduce_el_ruido(self, imagen_oscura):
        antes = pre._ruido_estimado(imagen_oscura)
        despues = pre._ruido_estimado(pre.suavizado_gaussiano(imagen_oscura, 5))
        assert despues < antes

    def test_suavizado_conserva_la_forma(self, imagen_oscura):
        assert pre.suavizado_gaussiano(imagen_oscura, 7).shape == imagen_oscura.shape

    def test_mascara_oscurece_solo_fuera_de_la_region(self):
        plana = np.full((100, 100, 3), 200, np.uint8)
        roi = Rect(20, 20, 60, 60)
        salida = pre.mascara_roi(plana, roi)
        assert salida[50, 50, 0] == 200
        assert salida[5, 5, 0] < 200

    def test_transformacion_conserva_la_forma(self, imagen_oscura):
        assert pre.transformacion_geometrica(imagen_oscura).shape == imagen_oscura.shape

    def test_transformacion_de_cero_grados_no_toca_la_imagen(self, imagen_oscura):
        assert np.array_equal(pre.transformacion_geometrica(imagen_oscura, 0.0), imagen_oscura)


class TestCadena:
    def test_devuelve_las_siete_etapas(self, imagen_oscura):
        resultado = pre.PreprocesadorNumpy().procesar(imagen_oscura, ParametrosPreproc())
        assert set(resultado.etapas) == set(EtapaPreproc)

    def test_desactivar_el_preprocesamiento_deja_la_imagen_intacta(self, imagen_oscura):
        params = ParametrosPreproc(activo=False)
        resultado = pre.PreprocesadorNumpy().procesar(imagen_oscura, params)
        assert np.array_equal(resultado.final, imagen_oscura)
        assert not any(resultado.aplicadas.values())

    def test_una_etapa_desactivada_se_marca_como_omitida(self, imagen_oscura):
        params = ParametrosPreproc(modo_adaptativo=False)
        params.etapas_activas[EtapaPreproc.GAMMA] = False
        resultado = pre.PreprocesadorNumpy().procesar(imagen_oscura, params)
        assert resultado.aplicadas[EtapaPreproc.GAMMA] is False
        assert resultado.aplicadas[EtapaPreproc.ECUALIZACION] is True

    def test_modo_adaptativo_omite_la_gamma_en_una_imagen_clara(self):
        clara = np.full((60, 60, 3), 210, np.uint8)
        params = ParametrosPreproc(modo_adaptativo=True, umbral_brillo=90)
        resultado = pre.PreprocesadorNumpy().procesar(clara, params)
        assert resultado.aplicadas[EtapaPreproc.GAMMA] is False

    def test_modo_adaptativo_aplica_la_gamma_en_una_imagen_oscura(self, imagen_oscura):
        params = ParametrosPreproc(modo_adaptativo=True, umbral_brillo=90)
        resultado = pre.PreprocesadorNumpy().procesar(imagen_oscura, params)
        assert resultado.aplicadas[EtapaPreproc.GAMMA] is True

    def test_sin_modo_adaptativo_se_aplican_todas(self, imagen_oscura):
        params = ParametrosPreproc(modo_adaptativo=False)
        resultado = pre.PreprocesadorNumpy().procesar(imagen_oscura, params)
        assert all(resultado.aplicadas[e] for e in ETAPAS_CONFIGURABLES)

    def test_la_cadena_completa_mejora_la_imagen(self, imagen_oscura):
        # La region de interes cubre toda la imagen: si no, la mascara atenuaria
        # los bordes y el brillo medio global bajaria aunque el interior mejore.
        alto, ancho = imagen_oscura.shape[:2]
        params = ParametrosPreproc(roi=Rect(0, 0, ancho, alto))
        resultado = pre.PreprocesadorNumpy().procesar(imagen_oscura, params)
        antes, despues = calcular(imagen_oscura), calcular(resultado.final)
        assert despues.brillo_medio > antes.brillo_medio
        assert despues.contraste > antes.contraste
