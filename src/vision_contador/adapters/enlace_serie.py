"""Transporte serie sobre pyserial.

Solo contiene lo propio del puerto serie; el protocolo lo pone
:class:`~vision_contador.adapters.enlace_lineas.EnlaceLineas`.
"""

from __future__ import annotations

import serial
from serial.tools import list_ports

from ..core.config import ConfigPlaca
from ..ports.enlace_arduino import ArduinoNoDisponible
from .enlace_lineas import EnlaceLineas

#: Identificadores de fabricante de los conversores USB-serie habituales en
#: placas Arduino y sus clones. Se usan solo para ordenar la lista, nunca para
#: descartar un puerto: una placa desconocida tiene que seguir apareciendo.
VID_CONOCIDOS = {
    0x2341,  # Arduino SA
    0x2A03,  # Arduino.org
    0x1A86,  # QinHeng CH340, el de la mayoria de los clones
    0x0403,  # FTDI
    0x10C4,  # Silicon Labs CP210x
    0x1B4F,  # SparkFun
}


def puertos_del_sistema() -> list[str]:
    """Puertos serie utiles, tal como los nombra el sistema operativo.

    En Windows seran ``COM3``, ``COM4``…; en Linux ``/dev/ttyUSB0`` o
    ``/dev/ttyACM0``. Nunca se codifica un nombre fijo.

    En Linux, ``comports()`` devuelve ademas una treintena de ``/dev/ttyS*``:
    puertos serie del chipset que casi nunca existen fisicamente. Si se
    mostraran todos, el desplegable seria inservible y la autoseleccion
    elegiria uno fantasma, asi que se filtran los que no son USB. Los que
    parecen Arduino van primero.
    """
    puertos = list(list_ports.comports())
    por_usb = [p for p in puertos if p.vid is not None]

    if por_usb:
        candidatos = por_usb
    else:
        # Sin ningun puerto USB queda el respaldo, pero en Linux los
        # ``/dev/ttyS*`` sin fabricante son los fantasma del chipset: incluirlos
        # es peor que no ofrecer nada, porque la autoseleccion elegiria uno y el
        # usuario creeria que tiene la placa conectada.
        candidatos = [p for p in puertos if not p.device.startswith("/dev/ttyS")]

    candidatos.sort(key=lambda p: (p.vid not in VID_CONOCIDOS, p.device))
    return [p.device for p in candidatos]


def explicar(puerto: str, error: Exception) -> str:
    """Convierte el error de pyserial en algo accionable."""
    texto = str(error).lower()

    # El orden importa: en Windows un puerto ocupado da «Access is denied», que
    # contiene «denied». Si se comprobara antes el caso de permisos, al usuario
    # de Windows se le aconsejaria «usermod -aG uucp», que alli no existe.
    if "busy" in texto or "access is denied" in texto:
        return f"{puerto} está ocupado por otra aplicación (¿el monitor serie del IDE de Arduino?)"
    if "permission" in texto or "denied" in texto:
        return (
            f"sin permiso para abrir {puerto}. En Linux hay que pertenecer al grupo "
            f"dueño del dispositivo: «sudo usermod -aG uucp $USER» (o «dialout» según "
            f"la distribución) y volver a iniciar sesión"
        )
    if "could not open" in texto or "no such file" in texto:
        return f"puerto {puerto} no disponible"
    return f"{puerto}: {error}"


class EnlaceSerie(EnlaceLineas):
    """Placa conectada por USB."""

    def __init__(self, config: ConfigPlaca) -> None:
        super().__init__(config.nombre, config.reconectar)
        self._baudios = config.baudios
        self._destino = config.destino
        self._serial: serial.Serial | None = None

    def _destinos_del_transporte(self) -> list[str]:
        return puertos_del_sistema()

    def _abrir(self, destino: str) -> None:
        if not destino:
            disponibles = puertos_del_sistema()
            if not disponibles:
                raise ArduinoNoDisponible("no se encontró ningún puerto serie")
            destino = disponibles[0]
            self._destino = destino

        try:
            self._serial = serial.Serial(
                port=destino,
                baudrate=self._baudios,
                timeout=0.2,        # para que la lectura no bloquee el cierre
                write_timeout=1.0,
            )
        except (serial.SerialException, OSError) as error:
            self._serial = None
            raise ArduinoNoDisponible(explicar(destino, error)) from error

        # Lo que quedara en el bufer es del arranque anterior y solo confunde.
        self._serial.reset_input_buffer()
        self._serial.reset_output_buffer()

    def _leer_linea(self) -> str | None:
        if self._serial is None:
            return None
        crudo = self._serial.readline()
        return crudo.decode("utf-8", errors="replace") if crudo else None

    def _escribir_linea(self, linea: str) -> None:
        if self._serial is None:
            raise ArduinoNoDisponible("el puerto no está abierto")
        self._serial.write(f"{linea}\n".encode())
        self._serial.flush()

    def _cerrar(self) -> None:
        if self._serial is not None:
            self._serial.close()
            self._serial = None


#: Nombre anterior, conservado para no romper importaciones existentes.
ArduinoSerial = EnlaceSerie
