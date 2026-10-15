"""Escena sintetica para el modo demo.

Una vista cenital de una mesa de madera clara con una botella, una taza, un
celular y un libro: los mismos cuatro objetos del diseno. Se dibuja con numpy
para no arrastrar OpenCV ni un JPEG binario al repositorio, y porque asi se
conocen de antemano las cajas exactas de cada objeto, que es justo lo que el
detector simulado necesita devolver.
"""

from __future__ import annotations

import numpy as np

from ..core.modelos import Imagen, Rect

ANCHO, ALTO = 1280, 720

#: Cajas reales de cada objeto, en coordenadas de la imagen. El detector
#: simulado devuelve estas mismas cajas, de modo que lo que se ve dibujado
#: coincide con lo que se cuenta.
CAJAS: dict[str, Rect] = {
    "bottle": Rect(286, 150, 104, 322),
    "cup": Rect(566, 268, 156, 150),
    "cell phone": Rect(830, 186, 124, 232),
    "book": Rect(372, 492, 322, 182),
}


def _lienzo() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    ys, xs = np.mgrid[0:ALTO, 0:ANCHO].astype(np.float32)
    return np.zeros((ALTO, ANCHO, 3), np.float32), xs, ys


def _mezclar(img: np.ndarray, mascara: np.ndarray, color: tuple[float, float, float]) -> None:
    """Pinta ``color`` sobre ``img`` con una mascara suave en [0, 1]."""
    alfa = mascara[..., None]
    img *= 1.0 - alfa
    img += alfa * np.asarray(color, np.float32)


def _rect_redondeado(
    xs: np.ndarray, ys: np.ndarray, caja: Rect, radio: float, suavizado: float = 1.5
) -> np.ndarray:
    """Mascara antialiaseada de un rectangulo de esquinas redondeadas."""
    cx, cy = caja.x + caja.ancho / 2, caja.y + caja.alto / 2
    dx = np.abs(xs - cx) - (caja.ancho / 2 - radio)
    dy = np.abs(ys - cy) - (caja.alto / 2 - radio)
    distancia = np.hypot(np.maximum(dx, 0), np.maximum(dy, 0)) + np.minimum(
        np.maximum(dx, dy), 0
    )
    return np.clip((radio - distancia) / suavizado, 0.0, 1.0)


def _elipse(
    xs: np.ndarray, ys: np.ndarray, cx: float, cy: float, rx: float, ry: float
) -> np.ndarray:
    norma = np.hypot((xs - cx) / rx, (ys - cy) / ry)
    return np.clip((1.0 - norma) * max(rx, ry) / 1.5, 0.0, 1.0)


def _anillo(
    xs: np.ndarray, ys: np.ndarray, cx: float, cy: float, radio: float, grosor: float
) -> np.ndarray:
    distancia = np.abs(np.hypot(xs - cx, ys - cy) - radio)
    return np.clip((grosor - distancia) / 1.5, 0.0, 1.0)


def _mesa(img: np.ndarray, xs: np.ndarray, ys: np.ndarray, semilla: int) -> None:
    """Madera clara: base calida, veta sinusoidal y grano fino."""
    rng = np.random.default_rng(semilla)
    img[:] = np.asarray([201.0, 171.0, 131.0], np.float32)

    veta = (
        np.sin(ys / 23.0 + np.sin(xs / 310.0) * 2.6) * 7.0
        + np.sin(ys / 7.3 + xs / 820.0) * 3.0
    )
    grano = rng.normal(0.0, 3.2, (ALTO, ANCHO)).astype(np.float32)
    img += (veta + grano)[..., None] * np.asarray([1.0, 0.92, 0.78], np.float32)

    # Vineteado suave: la luz del aula nunca cae pareja sobre la mesa.
    radial = np.hypot((xs - ANCHO / 2) / (ANCHO / 2), (ys - ALTO / 2) / (ALTO / 2))
    img *= (1.0 - 0.20 * np.clip(radial, 0, 1.4) ** 2)[..., None]


def _sombra(img: np.ndarray, xs: np.ndarray, ys: np.ndarray, caja: Rect) -> None:
    """Sombra proyectada hacia abajo y a la derecha."""
    desplazada = Rect(caja.x + 10, caja.y + 12, caja.ancho, caja.alto)
    mascara = _rect_redondeado(xs, ys, desplazada, min(caja.ancho, caja.alto) * 0.3, 18.0)
    img *= (1.0 - 0.34 * mascara)[..., None]


def _botella(img: np.ndarray, xs: np.ndarray, ys: np.ndarray) -> None:
    caja = CAJAS["bottle"]
    _sombra(img, xs, ys, caja)
    cuerpo = Rect(caja.x, caja.y + 70, caja.ancho, caja.alto - 70)
    _mezclar(img, _rect_redondeado(xs, ys, cuerpo, 26), (168.0, 201.0, 206.0))
    # Cuello y tapa.
    _mezclar(img, _rect_redondeado(xs, ys, Rect(caja.x + 33, caja.y + 24, 38, 60), 10), (176.0, 206.0, 210.0))
    _mezclar(img, _rect_redondeado(xs, ys, Rect(caja.x + 28, caja.y, 48, 30), 7), (72.0, 128.0, 196.0))
    # Etiqueta y brillo especular del plastico.
    _mezclar(img, _rect_redondeado(xs, ys, Rect(caja.x + 2, caja.y + 180, caja.ancho - 4, 92), 6), (236.0, 238.0, 232.0))
    _mezclar(img, _rect_redondeado(xs, ys, Rect(caja.x + 16, caja.y + 86, 14, 210), 7, 6.0) * 0.55, (255.0, 255.0, 255.0))


def _taza(img: np.ndarray, xs: np.ndarray, ys: np.ndarray) -> None:
    caja = CAJAS["cup"]
    _sombra(img, xs, ys, caja)
    cx, cy = caja.x + 75, caja.y + caja.alto / 2
    # El asa se dibuja primero para que el cuerpo tape su arranque y se lea
    # pegada a la taza en lugar de como un segundo objeto.
    _mezclar(img, _anillo(xs, ys, cx + 68, cy, 22, 8), (230.0, 230.0, 225.0))
    _mezclar(img, _elipse(xs, ys, cx, cy, 75, 75), (238.0, 238.0, 233.0))
    _mezclar(img, _elipse(xs, ys, cx, cy, 63, 63), (212.0, 211.0, 204.0))
    _mezclar(img, _elipse(xs, ys, cx, cy, 56, 56), (86.0, 58.0, 40.0))
    _mezclar(img, _elipse(xs, ys, cx - 18, cy - 18, 15, 10) * 0.45, (255.0, 255.0, 255.0))


def _celular(img: np.ndarray, xs: np.ndarray, ys: np.ndarray) -> None:
    caja = CAJAS["cell phone"]
    _sombra(img, xs, ys, caja)
    _mezclar(img, _rect_redondeado(xs, ys, caja, 16), (34.0, 37.0, 43.0))
    pantalla = Rect(caja.x + 7, caja.y + 7, caja.ancho - 14, caja.alto - 14)
    _mezclar(img, _rect_redondeado(xs, ys, pantalla, 11), (22.0, 25.0, 31.0))
    # Reflejo diagonal del vidrio.
    diagonal = np.clip(1.0 - np.abs((xs - caja.x) * 0.9 + (ys - caja.y) * 0.5 - 150) / 26.0, 0, 1)
    _mezclar(img, _rect_redondeado(xs, ys, pantalla, 11) * diagonal * 0.22, (255.0, 255.0, 255.0))


def _libro(img: np.ndarray, xs: np.ndarray, ys: np.ndarray) -> None:
    caja = CAJAS["book"]
    _sombra(img, xs, ys, caja)
    _mezclar(img, _rect_redondeado(xs, ys, caja, 6), (238.0, 236.0, 226.0))  # canto de hojas
    tapa = Rect(caja.x + 14, caja.y, caja.ancho - 14, caja.alto - 8)
    _mezclar(img, _rect_redondeado(xs, ys, tapa, 5), (164.0, 62.0, 52.0))
    _mezclar(img, _rect_redondeado(xs, ys, Rect(tapa.x, tapa.y, 26, tapa.alto), 4), (132.0, 46.0, 38.0))  # lomo
    # Dos renglones del titulo.
    _mezclar(img, _rect_redondeado(xs, ys, Rect(tapa.x + 58, tapa.y + 52, 182, 13), 3), (233.0, 219.0, 196.0))
    _mezclar(img, _rect_redondeado(xs, ys, Rect(tapa.x + 58, tapa.y + 80, 122, 10), 3), (214.0, 198.0, 174.0))


def generar(semilla: int = 7, exposicion: float = 1.0) -> Imagen:
    """Dibuja la escena completa.

    ``exposicion`` por debajo de 1 oscurece la toma, que es justamente el caso
    que el preprocesamiento tiene que corregir: una mesa mal iluminada da un
    histograma apelotonado en los valores bajos.
    """
    img, xs, ys = _lienzo()
    _mesa(img, xs, ys, semilla)
    _botella(img, xs, ys)
    _taza(img, xs, ys)
    _celular(img, xs, ys)
    _libro(img, xs, ys)
    return np.clip(img * exposicion, 0, 255).astype(np.uint8)


#: Escena base a exposicion 1, dibujada una sola vez. Generarla cuesta unos
#: 450 ms, demasiado para repetirlo por cuadro.
_BASE: Imagen | None = None

#: Variantes para el video en vivo, derivadas de la base con operaciones baratas.
_CICLO_VIVO: list[Imagen] = []
_EXPOSICION_CICLO: float | None = None
CUADROS_CICLO = 6

#: El video en vivo se genera a media resolucion: no se mira al detalle y asi el
#: hilo de la camara mantiene los 30 FPS sin esfuerzo.
DIVISOR_VIVO = 2


def _base() -> Imagen:
    global _BASE
    if _BASE is None:
        _BASE = generar(semilla=7, exposicion=1.0)
    return _BASE


def _reducir(imagen: Imagen, divisor: int) -> Imagen:
    """Submuestreo por promedio de bloques, sin dependencias externas."""
    if divisor <= 1:
        return imagen
    alto = imagen.shape[0] // divisor * divisor
    ancho = imagen.shape[1] // divisor * divisor
    bloques = imagen[:alto, :ancho].reshape(
        alto // divisor, divisor, ancho // divisor, divisor, 3
    )
    return bloques.mean(axis=(1, 3)).astype(np.uint8)


def cuadros_vivos(exposicion: float) -> list[Imagen]:
    """Ciclo de cuadros para el video en vivo.

    Se derivan de una unica escena base aplicandole grano y una oscilacion leve
    de exposicion: sin esa variacion el "video en vivo" se ve como una foto
    pegada, y volver a dibujar la escena entera por cuadro costaria 450 ms.
    """
    global _EXPOSICION_CICLO
    if _CICLO_VIVO and _EXPOSICION_CICLO == exposicion:
        return _CICLO_VIVO

    _CICLO_VIVO.clear()
    base = _reducir(_base(), DIVISOR_VIVO).astype(np.float32)
    rng = np.random.default_rng(31)
    for i in range(CUADROS_CICLO):
        parpadeo = 1.0 + 0.012 * (i - CUADROS_CICLO / 2)
        grano = rng.normal(0.0, 2.4, base.shape[:2]).astype(np.float32)[..., None]
        _CICLO_VIVO.append(
            np.clip(base * exposicion * parpadeo + grano, 0, 255).astype(np.uint8)
        )
    _EXPOSICION_CICLO = exposicion
    return _CICLO_VIVO
