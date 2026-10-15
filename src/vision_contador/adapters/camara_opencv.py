"""Camara real sobre OpenCV: webcam local o camara de red."""

from __future__ import annotations

import glob
import sys
import threading
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from ..core.config import ConfigCamara
from ..core.modelos import Imagen
from ..ports.camara import CamaraNoDisponible, FuenteVideo

#: Cuadros que se leen y descartan al abrir, para que la auto-exposicion
#: converja antes de mostrar nada.
CUADROS_DE_CALENTAMIENTO = 8

#: Cuanto se espera, como maximo, a que una camara de red responda. Sin esto una
#: direccion equivocada deja la lectura colgada minutos.
TIEMPO_LIMITE_RED_MS = 4000

#: Indices que se sondean al enumerar camaras en Windows, donde no hay nada
#: parecido a ``/dev/video*`` que listar.
INDICES_SONDEADOS = 6


def _backend_preferido() -> int:
    """En Windows, DirectShow abre la camara en menos de un segundo.

    Con el backend por defecto (MSMF) el primer ``VideoCapture`` puede tardar
    varios segundos, y eso se nota al arrancar la aplicacion.
    """
    if sys.platform.startswith("win"):
        return cv2.CAP_DSHOW
    if sys.platform.startswith("linux"):
        return cv2.CAP_V4L2
    return cv2.CAP_ANY


def normalizar(destino: int | str) -> int | str:
    """Deja el destino como entero si es un indice y como texto si es una ruta o URL."""
    if isinstance(destino, int):
        return destino
    texto = str(destino).strip()
    if texto.isdigit():
        return int(texto)
    return texto


def es_url(destino: int | str) -> bool:
    """True solo para una camara de red.

    No vale preguntar si el destino es texto: ``/dev/video0`` tambien lo es y
    es una camara conectada por USB. Lo que distingue a una camara de red es
    que su destino lleva esquema -http, rtsp, rtmp- delante.
    """
    return isinstance(destino, str) and "://" in destino


def _abrir(destino: int | str) -> cv2.VideoCapture:
    """Abre un indice local o una URL de red.

    Una URL se abre con ``CAP_ANY``, nunca con el backend preferido: ni V4L2 ni
    DirectShow entienden de HTTP, y con ellos la apertura falla sin decir por que.
    """
    destino = normalizar(destino)
    if not es_url(destino):
        # Un indice o una ruta de dispositivo los abre mejor el backend nativo.
        return cv2.VideoCapture(destino, _backend_preferido())

    cap = cv2.VideoCapture(destino, cv2.CAP_ANY)
    for propiedad in (cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, cv2.CAP_PROP_READ_TIMEOUT_MSEC):
        try:
            cap.set(propiedad, TIEMPO_LIMITE_RED_MS)
        except cv2.error:
            # No todos los backends admiten estas propiedades; el unico efecto
            # de que no se apliquen es que un fallo tarde mas en notarse.
            pass
    return cap


def dispositivos() -> list[tuple[str, str]]:
    """Camaras locales encontradas, como pares ``(destino, etiqueta)``.

    En Linux se leen de ``/dev/video*``, con el nombre legible que publica el
    nucleo en ``/sys``. En el resto de sistemas no hay una lista que consultar,
    asi que se sondean los primeros indices abriendolos de verdad.
    """
    if sys.platform.startswith("linux"):
        encontrados = []
        for ruta in sorted(glob.glob("/dev/video*")):
            nombre = Path(f"/sys/class/video4linux/{Path(ruta).name}/name")
            try:
                etiqueta = nombre.read_text(encoding="utf-8").strip()
            except OSError:
                etiqueta = ""
            encontrados.append((ruta, f"{Path(ruta).name} — {etiqueta}" if etiqueta else ruta))
        return encontrados

    encontrados = []
    for indice in range(INDICES_SONDEADOS):
        cap = cv2.VideoCapture(indice, _backend_preferido())
        abierta = cap.isOpened()
        cap.release()
        if abierta:
            encontrados.append((str(indice), f"Cámara {indice}"))
    return encontrados


@dataclass(frozen=True, slots=True)
class ResultadoPrueba:
    """Lo que se averigua al tantear una fuente antes de usarla."""

    ok: bool
    ancho: int = 0
    alto: int = 0
    fps: float = 0.0
    error: str = ""

    @property
    def resumen(self) -> str:
        if not self.ok:
            return self.error or "no responde"
        return f"{self.ancho} x {self.alto} · {self.fps:.0f} FPS"


def probar(destino: int | str) -> ResultadoPrueba:
    """Abre la fuente, lee un cuadro y la cierra.

    Bloquea mientras la fuente responde o agota su tiempo limite, asi que la
    interfaz la llama desde un hilo de trabajo.
    """
    try:
        cap = _abrir(destino)
    except cv2.error as error:
        return ResultadoPrueba(False, error=str(error))

    try:
        if not cap.isOpened():
            return ResultadoPrueba(False, error="no se pudo abrir la fuente")
        leido, cuadro = cap.read()
        if not leido or cuadro is None:
            return ResultadoPrueba(False, error="se abrió pero no entrega cuadros")
        alto, ancho = cuadro.shape[:2]
        fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
        return ResultadoPrueba(True, ancho, alto, float(fps))
    finally:
        cap.release()


class CamaraOpenCV(FuenteVideo):
    """Entrega los cuadros de una webcam local o de una camara de red.

    El hilo de video y el de captura usan el mismo ``VideoCapture``, y acceder a
    el desde dos hilos a la vez devuelve cuadros corruptos o revienta segun el
    backend. Por eso todas las operaciones pasan por un cerrojo.
    """

    def __init__(self, config: ConfigCamara, destino: int | str | None = None) -> None:
        self._config = config
        self._destino = normalizar(destino if destino is not None else config.destino)
        self._cap: cv2.VideoCapture | None = None
        self._cerrojo = threading.Lock()
        self._fps_nominal = float(config.fps)

    @property
    def destino(self) -> int | str:
        return self._destino

    @property
    def es_red(self) -> bool:
        return es_url(self._destino)

    # --- Ciclo de vida -----------------------------------------------------
    def abrir(self) -> None:
        with self._cerrojo:
            if self._cap is not None and self._cap.isOpened():
                return

            cap = _abrir(self._destino)
            if not cap.isOpened():
                cap.release()
                raise CamaraNoDisponible(self._porque_no_abre())

            if not self.es_red:
                # Una camara de red sirve la resolucion que decida la app del
                # telefono; pedirle otra no hace nada y con algunos backends
                # tira la conexion.
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._config.ancho)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._config.alto)
                cap.set(cv2.CAP_PROP_FPS, self._config.fps)
            # Un bufer de un cuadro reduce el retardo entre lo que pasa delante
            # de la camara y lo que se ve en pantalla. No todos los backends lo
            # respetan, por eso ademas se descartan cuadros al capturar.
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

            # Calentamiento: la auto-exposicion y el balance de blancos de una
            # webcam tardan varios cuadros en converger. Sin esto el primer
            # cuadro que se muestra sale casi negro y el usuario cree que la
            # camara no funciona.
            leido = False
            for _ in range(CUADROS_DE_CALENTAMIENTO):
                leido, _ = cap.read()
                if not leido:
                    break

            if not leido:
                cap.release()
                raise CamaraNoDisponible(f"{self._nombre()} se abrió pero no entrega cuadros")

            self._cap = cap
            medidos = cap.get(cv2.CAP_PROP_FPS)
            if medidos and medidos > 0:
                self._fps_nominal = float(medidos)

    def cerrar(self) -> None:
        with self._cerrojo:
            if self._cap is not None:
                self._cap.release()
                self._cap = None

    def _nombre(self) -> str:
        return f"la cámara de red {self._destino}" if self.es_red else f"la cámara {self._destino}"

    def _porque_no_abre(self) -> str:
        if self.es_red:
            return (
                f"no se pudo abrir {self._nombre()}. Compruebe que el teléfono y la laptop "
                "estén en la misma red WiFi y que la dirección sea la que muestra la aplicación "
                "del teléfono."
            )
        return (
            f"no se pudo abrir {self._nombre()}. "
            "Compruebe que esté conectada y que ninguna otra aplicación la esté usando."
        )

    # --- Lectura -----------------------------------------------------------
    def leer_cuadro(self) -> Imagen | None:
        with self._cerrojo:
            if self._cap is None:
                return None
            leido, cuadro = self._cap.read()
        return self._a_rgb(cuadro) if leido else None

    def capturar_estable(self) -> Imagen:
        """Descarta el bufer y devuelve un cuadro actual.

        Sin este descarte se fotografia la escena de hace medio segundo, es
        decir, la de antes de que el usuario terminara de colocar los objetos.
        """
        with self._cerrojo:
            if self._cap is None:
                raise CamaraNoDisponible(f"{self._nombre()} no está abierta")

            for _ in range(max(self._config.cuadros_a_descartar, 0)):
                self._cap.grab()

            leido, cuadro = self._cap.retrieve()
            if not leido:
                # ``retrieve`` falla si el ultimo ``grab`` no trajo nada; se
                # reintenta con una lectura completa antes de darse por vencido.
                leido, cuadro = self._cap.read()

        if not leido:
            raise CamaraNoDisponible(f"{self._nombre()} dejó de entregar cuadros")
        return self._a_rgb(cuadro)

    @staticmethod
    def _a_rgb(cuadro: np.ndarray) -> Imagen:
        """OpenCV entrega BGR; el resto del programa trabaja en RGB.

        La conversion se hace aqui, en la frontera del adaptador, y no mas
        adelante: de lo contrario el azul y el rojo aparecen cambiados en los
        visores y en las imagenes del registro.
        """
        return cv2.cvtColor(cuadro, cv2.COLOR_BGR2RGB)

    # --- Estado ------------------------------------------------------------
    @property
    def fps(self) -> float:
        return self._fps_nominal

    @property
    def disponible(self) -> bool:
        return self._cap is not None and self._cap.isOpened()
