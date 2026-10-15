"""Sintesis de voz con edge-tts y cache en disco."""

from __future__ import annotations

import asyncio
import hashlib
import shutil
import subprocess
import threading
from pathlib import Path

from ..core.config import RAIZ, ConfigVoz
from ..ports.voz import SintetizadorVoz

#: Reproductores de linea de ordenes que se prueban, en orden, si Qt no puede.
REPRODUCTORES = (
    ("ffplay", ("-nodisp", "-autoexit", "-loglevel", "quiet")),
    ("mpv", ("--no-video", "--really-quiet")),
    ("cvlc", ("--play-and-exit", "--quiet")),
)


class VozEdgeTts(SintetizadorVoz):
    """Sintetiza la frase con las voces de Edge y la reproduce por los parlantes.

    El cache no es una optimizacion: en el aula la misma frase se repite mucho y
    no conviene que cada captura dependa de que la red responda.
    """

    def __init__(self, config: ConfigVoz) -> None:
        self._config = config
        self._carpeta = RAIZ / config.carpeta_cache
        self._carpeta.mkdir(parents=True, exist_ok=True)
        self._desde_cache = False
        self._ultimo_error = ""
        self._reproduciendo: subprocess.Popen | None = None
        self._cerrojo = threading.Lock()

    # --- API ---------------------------------------------------------------
    def decir(self, frase: str) -> None:
        """Sintetiza y reproduce sin bloquear a quien llama."""
        if not frase.strip():
            return
        hilo = threading.Thread(
            target=self._trabajar, args=(frase,), name="voz", daemon=True
        )
        hilo.start()

    def detener(self) -> None:
        with self._cerrojo:
            if self._reproduciendo is not None and self._reproduciendo.poll() is None:
                self._reproduciendo.terminate()
            self._reproduciendo = None

    @property
    def descripcion(self) -> str:
        if self._ultimo_error:
            return f"edge-tts · {self._ultimo_error}"
        return f"edge-tts · {'desde caché' if self._desde_cache else 'sintetizada'}"

    # --- Interno -----------------------------------------------------------
    def _ruta(self, frase: str) -> Path:
        """Una frase, un archivo. El nombre incluye la voz: cambiarla invalida el cache."""
        clave = f"{self._config.voz}|{frase}".encode()
        return self._carpeta / f"{hashlib.sha256(clave).hexdigest()[:16]}.mp3"

    def _trabajar(self, frase: str) -> None:
        try:
            ruta = self._sintetizar(frase)
        except Exception as error:
            self._ultimo_error = f"sin audio ({error})"
            return
        self._ultimo_error = ""
        self._reproducir(ruta)

    def _sintetizar(self, frase: str) -> Path:
        ruta = self._ruta(frase)
        if ruta.is_file() and ruta.stat().st_size > 0:
            self._desde_cache = True
            return ruta

        self._desde_cache = False
        import edge_tts

        async def generar() -> None:
            comunicacion = edge_tts.Communicate(frase, self._config.voz)
            # Se escribe a un archivo temporal y se renombra al final: si la red
            # se corta a mitad, el cache no se queda con un MP3 truncado que
            # despues se daria por bueno para siempre.
            parcial = ruta.with_suffix(".parcial")
            await comunicacion.save(str(parcial))
            parcial.replace(ruta)

        # El hilo de voz no tiene bucle de eventos propio; se crea uno para esta
        # llamada y se cierra al terminar.
        asyncio.run(generar())
        return ruta

    def _reproducir(self, ruta: Path) -> None:
        if self._reproducir_con_qt(ruta):
            return
        self._reproducir_con_programa(ruta)

    def _reproducir_con_qt(self, ruta: Path) -> bool:
        """QtMultimedia, que ya viene con PySide6.

        Depende de los complementos de GStreamer en Linux, que no siempre estan
        instalados; por eso el fallo no es excepcional y hay un respaldo.
        """
        try:
            from PySide6.QtCore import QUrl
            from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
        except ImportError:
            return False

        try:
            reproductor = QMediaPlayer()
            salida = QAudioOutput()
            reproductor.setAudioOutput(salida)
            reproductor.setSource(QUrl.fromLocalFile(str(ruta)))
            reproductor.play()
            if reproductor.error() != QMediaPlayer.Error.NoError:
                return False
        except Exception:
            return False

        # Se guardan como atributos o el recolector de basura los destruye a
        # mitad de la reproduccion y el audio se corta en seco.
        self._qt_reproductor = reproductor
        self._qt_salida = salida
        return True

    def _reproducir_con_programa(self, ruta: Path) -> None:
        for programa, opciones in REPRODUCTORES:
            if shutil.which(programa) is None:
                continue
            with self._cerrojo:
                self._reproduciendo = subprocess.Popen(
                    [programa, *opciones, str(ruta)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            return
        self._ultimo_error = "no hay reproductor de audio disponible"
