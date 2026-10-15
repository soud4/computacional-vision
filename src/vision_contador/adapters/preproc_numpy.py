"""Preprocesamiento de imagen implementado con numpy.

Las cinco tecnicas del curso estan aqui de verdad, no simuladas: son pocas
lineas de algebra sobre arreglos y asi la demostracion muestra histogramas que
cambian porque la imagen cambio, no porque se hayan inventado los numeros.

``preproc_opencv`` queda pendiente como optimizacion para cuando la camara
entregue 30 cuadros por segundo; para una captura por pulsacion, numpy sobra.
"""

from __future__ import annotations

import math

import numpy as np

from ..core.modelos import EtapaPreproc, Imagen, ParametrosPreproc, Rect
from ..ports.preprocesador import Preprocesador, ResultadoPreproc
from ..services.histograma import luminancia

#: Inclinacion que se asume en el montaje de la camara sobre la mesa, en grados.
#: La transformacion geometrica la corrige para que los bordes queden a escuadra.
INCLINACION_GRADOS = -1.8

#: Cuanto se oscurece lo que queda fuera de la region de interes.
ATENUACION_FUERA_ROI = 0.38


def correccion_gamma(imagen: Imagen, gamma: float) -> Imagen:
    """``salida = 255 · (entrada/255)^gamma``.

    Con gamma menor que 1 se aclaran los tonos medios sin quemar los claros, que
    es el caso de una mesa mal iluminada.
    """
    # Se redondea en vez de truncar: con ``astype`` directo, gamma 1.0 convierte
    # algunos niveles en el anterior y la "identidad" oscurece la imagen.
    tabla = np.rint(np.linspace(0, 1, 256) ** gamma * 255.0).astype(np.uint8)
    return tabla[imagen]


#: Cuanto pesa la ecualizacion frente a la imagen de entrada. Al 100 % la
#: ecualizacion global lava los colores y el libro rojo se vuelve pardo; mezclada
#: al 60 % abre el histograma sin destruir la cromaticidad de la escena.
FUERZA_ECUALIZACION = 0.6


def ecualizar_histograma(imagen: Imagen, fuerza: float = FUERZA_ECUALIZACION) -> Imagen:
    """Ecualizacion sobre la luminancia, conservando el color.

    Ecualizar los tres canales por separado desplaza los tonos y la mesa de
    madera se vuelve rosada. En su lugar se ecualiza solo la luminancia y se
    reescala el RGB por la razon entre la luminancia nueva y la vieja.
    """
    luma = luminancia(imagen)
    histo = np.bincount(luma.ravel(), minlength=256).astype(np.float64)
    acumulado = histo.cumsum()
    total = acumulado[-1]
    if total == 0:
        return imagen.copy()

    # Se ignoran los niveles vacios iniciales para no desperdiciar rango.
    minimo = acumulado[acumulado > 0][0]
    divisor = total - minimo
    if divisor <= 0:
        return imagen.copy()
    tabla = np.clip((acumulado - minimo) / divisor * 255.0, 0, 255)

    luma_f = luma.astype(np.float32)
    nueva = luma_f * (1.0 - fuerza) + tabla[luma].astype(np.float32) * fuerza
    razon = np.where(luma > 0, nueva / np.maximum(luma_f, 1.0), 1.0)
    return np.clip(imagen.astype(np.float32) * razon[..., None], 0, 255).astype(np.uint8)


def _nucleo_gaussiano(tam: int) -> np.ndarray:
    """Nucleo 1D normalizado; sigma segun la convencion de OpenCV."""
    sigma = 0.3 * ((tam - 1) * 0.5 - 1) + 0.8
    ejes = np.arange(tam, dtype=np.float32) - (tam - 1) / 2
    nucleo = np.exp(-(ejes**2) / (2 * sigma**2))
    return nucleo / nucleo.sum()


def suavizado_gaussiano(imagen: Imagen, tam: int) -> Imagen:
    """Filtro gaussiano separable de ``tam`` x ``tam``.

    Separar el nucleo 2D en dos pasadas 1D convierte un coste O(n²) por pixel en
    O(2n), que para 1280x720 es la diferencia entre notarlo y no notarlo.
    """
    if tam < 3:
        return imagen.copy()
    if tam % 2 == 0:
        tam += 1
    nucleo = _nucleo_gaussiano(tam)
    radio = tam // 2

    datos = imagen.astype(np.float32)
    # Borde replicado: evita el halo oscuro que deja el relleno con ceros.
    datos = np.pad(datos, ((radio, radio), (radio, radio), (0, 0)), mode="edge")

    horizontal = sum(nucleo[i] * datos[:, i : i + imagen.shape[1]] for i in range(tam))
    vertical = sum(nucleo[i] * horizontal[i : i + imagen.shape[0]] for i in range(tam))
    return np.clip(vertical, 0, 255).astype(np.uint8)


def transformacion_geometrica(imagen: Imagen, grados: float = INCLINACION_GRADOS) -> Imagen:
    """Rotacion alrededor del centro con muestreo bilineal.

    Corrige la inclinacion del montaje de la camara. El muestreo bilineal evita
    los dientes de sierra que deja tomar el vecino mas cercano, que despues el
    detector interpreta como bordes falsos.
    """
    if abs(grados) < 1e-3:
        return imagen.copy()

    alto, ancho = imagen.shape[:2]
    radianes = math.radians(grados)
    cos, sen = math.cos(radianes), math.sin(radianes)
    cx, cy = (ancho - 1) / 2, (alto - 1) / 2

    ys, xs = np.mgrid[0:alto, 0:ancho].astype(np.float32)
    dx, dy = xs - cx, ys - cy
    # Rotacion inversa: para cada pixel de salida se busca de donde viene.
    ox = cos * dx + sen * dy + cx
    oy = -sen * dx + cos * dy + cy

    ox = np.clip(ox, 0, ancho - 1)
    oy = np.clip(oy, 0, alto - 1)
    x0, y0 = np.floor(ox).astype(np.int32), np.floor(oy).astype(np.int32)
    x1 = np.minimum(x0 + 1, ancho - 1)
    y1 = np.minimum(y0 + 1, alto - 1)
    fx, fy = (ox - x0)[..., None], (oy - y0)[..., None]

    datos = imagen.astype(np.float32)
    arriba = datos[y0, x0] * (1 - fx) + datos[y0, x1] * fx
    abajo = datos[y1, x0] * (1 - fx) + datos[y1, x1] * fx
    return np.clip(arriba * (1 - fy) + abajo * fy, 0, 255).astype(np.uint8)


def mascara_roi(imagen: Imagen, roi: Rect, atenuacion: float = ATENUACION_FUERA_ROI) -> Imagen:
    """Oscurece todo lo que cae fuera de la region de interes.

    No se recorta la imagen: el detector sigue viendo el cuadro completo y la
    interfaz puede dibujar el rectangulo discontinuo en su sitio, pero los
    objetos de fuera de la mesa dejan de competir por atencion.
    """
    alto, ancho = imagen.shape[:2]
    factor = np.full((alto, ancho), atenuacion, np.float32)
    x0, y0 = max(roi.x, 0), max(roi.y, 0)
    x1, y1 = min(roi.x2, ancho), min(roi.y2, alto)
    if x1 > x0 and y1 > y0:
        factor[y0:y1, x0:x1] = 1.0
    return (imagen.astype(np.float32) * factor[..., None]).astype(np.uint8)


def _ruido_estimado(imagen: Imagen) -> float:
    """Desviacion de un paso alto rapido; sube con el grano del sensor."""
    luma = luminancia(imagen).astype(np.float32)
    alto_paso = luma[1:-1, 1:-1] * 4 - luma[:-2, 1:-1] - luma[2:, 1:-1] - luma[1:-1, :-2] - luma[1:-1, 2:]
    return float(alto_paso.std())


#: Por encima de este ruido el suavizado vale la pena en modo adaptativo.
UMBRAL_RUIDO = 6.0


class PreprocesadorNumpy(Preprocesador):
    """Aplica la cadena completa y devuelve cada etapa intermedia."""

    def procesar(self, imagen: Imagen, params: ParametrosPreproc) -> ResultadoPreproc:
        etapas: dict[EtapaPreproc, Imagen] = {EtapaPreproc.ORIGINAL: imagen}
        aplicadas: dict[EtapaPreproc, bool] = {}
        actual = imagen

        def paso(etapa: EtapaPreproc, procede: bool, calcular) -> None:
            nonlocal actual
            if params.etapa_activa(etapa) and procede:
                actual = calcular(actual)
                aplicadas[etapa] = True
            else:
                aplicadas[etapa] = False
            etapas[etapa] = actual

        adaptativo = params.modo_adaptativo

        def requiere(condicion) -> bool:
            """En modo adaptativo cada etapa decide mirando la imagen que recibe.

            Medir siempre sobre la imagen original seria incorrecto: despues de la
            gamma la toma ya esta aclarada, y volver a ecualizarla por el
            contraste que tenia antes es lo que lava los colores.
            """
            return not adaptativo or condicion(actual)

        paso(EtapaPreproc.GEOMETRICA, True, transformacion_geometrica)
        # La gamma solo entra si la imagen esta oscura; forzarla sobre una toma
        # bien expuesta solo la lava.
        paso(
            EtapaPreproc.GAMMA,
            requiere(lambda img: luminancia(img).mean() < params.umbral_brillo),
            lambda img: correccion_gamma(img, params.gamma),
        )
        paso(
            EtapaPreproc.ECUALIZACION,
            requiere(lambda img: luminancia(img).std() < params.umbral_contraste),
            ecualizar_histograma,
        )
        paso(
            EtapaPreproc.SUAVIZADO,
            requiere(lambda img: _ruido_estimado(img) > UMBRAL_RUIDO),
            lambda img: suavizado_gaussiano(img, params.kernel_suavizado),
        )
        paso(
            EtapaPreproc.MASCARA_ROI,
            True,
            lambda img: mascara_roi(img, params.roi),
        )

        etapas[EtapaPreproc.RESULTADO] = actual
        return ResultadoPreproc(etapas, aplicadas)
