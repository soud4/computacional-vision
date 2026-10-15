"""Arduino simulado.

Implementa el mismo contrato que ``enlace_serie`` y que el sketch ``.ino``:
responde ``READY`` al conectar, acusa cada orden con ``OK`` tras un retardo
creible y emite ``BTN`` cuando se "presiona" el pulsador. Gracias a eso la
consola serial de la interfaz muestra trafico real desde el primer dia y el
pipeline no distingue si hay hardware detras.
"""

from __future__ import annotations

import sys
import threading
import time

from ..core.modelos import Led
from ..ports.enlace_arduino import (
    CMD_ID,
    MSG_BTN,
    MSG_OK,
    MSG_READY,
    PREFIJO_ID,
    ArduinoNoDisponible,
    EnlaceArduino,
    EscuchaArduino,
)

#: Lo que tarda el Arduino en acusar una orden, en segundos.
RETARDO_ACUSE = 0.04

#: Puerto que no existe, para poder demostrar la variante "Arduino desconectado".
PUERTO_INEXISTENTE = "COM9"


def _puertos_plausibles() -> list[str]:
    """Nombres de puerto con la forma que tendrian en este sistema operativo."""
    if sys.platform.startswith("win"):
        return ["COM3", "COM4"]
    return ["/dev/ttyUSB0", "/dev/ttyACM0"]


class ArduinoMock(EnlaceArduino):
    """Enlace simulado con un hilo que entrega los acuses fuera de linea."""

    def __init__(self, fallar_siempre: bool = False, identidad: str = "SIMULADA") -> None:
        self.identidad = identidad
        self._escuchas: list[EscuchaArduino] = []
        self._conectado = False
        self._puerto = ""
        self._lock = threading.Lock()
        self._temporizadores: list[threading.Timer] = []
        #: Con esto la variante B del diseno se reproduce sin tocar nada mas.
        self.fallar_siempre = fallar_siempre
        self.pulsaciones = 0
        self.ultima_pulsacion: str = "—"
        self.leds: dict[Led, bool] = {led: False for led in Led}
        self.lcd: list[str] = ["", ""]

    # --- Puerto -----------------------------------------------------------
    def puertos_disponibles(self) -> list[str]:
        return _puertos_plausibles()

    def conectar(self, puerto: str, baudios: int) -> None:
        if self.fallar_siempre or puerto == PUERTO_INEXISTENTE:
            self._conectado = False
            detalle = f"puerto {puerto} no disponible"
            self._avisar_conexion(False, detalle)
            raise ArduinoNoDisponible(detalle)
        self._puerto = puerto
        self._conectado = True
        self._avisar_conexion(True, f"{puerto} a {baudios} baudios")
        self._programar(lambda: self._recibir(MSG_READY), 0.01)

    def desconectar(self) -> None:
        self._cancelar_pendientes()
        if not self._conectado:
            return
        self._conectado = False
        self._avisar_conexion(False, "desconectado por el usuario")

    # --- Trafico ----------------------------------------------------------
    def enviar(self, orden: str) -> None:
        if not self._conectado:
            raise ArduinoNoDisponible("el puerto no esta abierto")
        for escucha in list(self._escuchas):
            escucha.al_enviar(orden)
        self._aplicar(orden)
        # ``ID`` se contesta con la identidad; el resto con el acuse de siempre.
        respuesta = f"{PREFIJO_ID}{self.identidad}" if orden == CMD_ID else MSG_OK
        self._programar(lambda: self._recibir(respuesta), RETARDO_ACUSE)

    def pulsar_boton(self) -> None:
        """Simula el pulsador fisico de la protoboard."""
        self.pulsaciones += 1
        self.ultima_pulsacion = time.strftime("%H:%M:%S")
        if self._conectado:
            self._recibir(MSG_BTN)
        for escucha in list(self._escuchas):
            escucha.al_pulsar_boton()

    def suscribir(self, escucha: EscuchaArduino) -> None:
        self._escuchas.append(escucha)

    @property
    def conectado(self) -> bool:
        return self._conectado

    @property
    def puerto_actual(self) -> str:
        return self._puerto

    # --- Interno ----------------------------------------------------------
    def _aplicar(self, orden: str) -> None:
        """Mantiene el estado del hardware simulado: LCD y LEDs."""
        if orden.startswith("LCD1:"):
            self.lcd[0] = orden[5:][:16]
        elif orden.startswith("LCD2:"):
            self.lcd[1] = orden[5:][:16]
        elif orden.startswith("LED:"):
            valor = orden[4:]
            self.leds = {led: led.value == valor for led in Led}
        elif orden == "PENSANDO":
            self.lcd = ["Pensando...", ""]

    def _recibir(self, linea: str) -> None:
        for escucha in list(self._escuchas):
            escucha.al_recibir(linea)

    def _avisar_conexion(self, conectado: bool, detalle: str) -> None:
        for escucha in list(self._escuchas):
            escucha.al_cambiar_conexion(conectado, detalle)

    def _programar(self, accion, retardo: float) -> None:
        temporizador = threading.Timer(retardo, accion)
        temporizador.daemon = True
        with self._lock:
            self._temporizadores = [t for t in self._temporizadores if t.is_alive()]
            self._temporizadores.append(temporizador)
        temporizador.start()

    def _cancelar_pendientes(self) -> None:
        with self._lock:
            for temporizador in self._temporizadores:
                temporizador.cancel()
            self._temporizadores.clear()
