"""Transporte TCP, para una placa conectada por WiFi (el ESP32).

El protocolo es exactamente el mismo que por el cable: una orden por linea. Lo
unico que cambia es que las lineas viajan por un socket en vez de por un puerto
serie, lo que permite que el actuador este al otro lado del aula.

Se usa un socket crudo de la biblioteca estandar a proposito: ni WebSocket, ni
un broker MQTT, ni un servidor HTTP. Para mover veinte bytes por captura, y
necesitando que la placa pueda hablar cuando quiera (el ``BTN`` del pulsador),
un socket TCP es la pieza mas simple que cumple.
"""

from __future__ import annotations

import socket

from ..core.config import ConfigPlaca
from ..ports.enlace_arduino import ArduinoNoDisponible
from .enlace_lineas import EnlaceLineas

ESQUEMA = "tcp://"
PUERTO_POR_DEFECTO = 3333

#: Tiempo de espera de la lectura. Corto para que cerrar no tenga que esperar.
SEGUNDOS_LECTURA = 0.3

#: Tiempo de espera al abrir la conexion. Si el ESP32 esta apagado o fuera de
#: cobertura, conviene fallar rapido en vez de congelar la interfaz.
SEGUNDOS_CONEXION = 3.0


def partir_destino(destino: str) -> tuple[str, int]:
    """``tcp://192.168.4.1:3333`` → ``("192.168.4.1", 3333)``.

    Acepta tambien la forma sin esquema y sin puerto.
    """
    texto = destino[len(ESQUEMA):] if destino.startswith(ESQUEMA) else destino
    if not texto:
        raise ArduinoNoDisponible("falta la dirección de la placa")
    anfitrion, _, puerto = texto.partition(":")
    if not puerto:
        return anfitrion, PUERTO_POR_DEFECTO
    try:
        return anfitrion, int(puerto)
    except ValueError as error:
        raise ArduinoNoDisponible(f"puerto no válido en «{destino}»") from error


class EnlaceTcp(EnlaceLineas):
    """Placa conectada por red."""

    def __init__(self, config: ConfigPlaca) -> None:
        super().__init__(config.nombre, config.reconectar)
        self._destino = config.destino or f"{ESQUEMA}192.168.4.1:{PUERTO_POR_DEFECTO}"
        self._socket: socket.socket | None = None
        #: Las lecturas traen trozos arbitrarios, no lineas: lo que sobra de una
        #: lectura se guarda aqui hasta que llegue el salto de linea.
        self._resto = b""

    def _destinos_del_transporte(self) -> list[str]:
        """El destino TCP se configura; no hay nada que descubrir."""
        return [self._destino]

    def _abrir(self, destino: str) -> None:
        anfitrion, puerto = partir_destino(destino or self._destino)
        try:
            conexion = socket.create_connection(
                (anfitrion, puerto), timeout=SEGUNDOS_CONEXION
            )
        except OSError as error:
            raise ArduinoNoDisponible(self._explicar(destino, error)) from error

        conexion.settimeout(SEGUNDOS_LECTURA)
        # Sin esto, un cable de red arrancado no da error hasta que expira el
        # TCP, y la interfaz se queda diciendo "conectado" durante minutos.
        conexion.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        self._socket = conexion
        self._resto = b""

    @staticmethod
    def _explicar(destino: str, error: OSError) -> str:
        if isinstance(error, socket.timeout):
            return (
                f"{destino} no respondió a tiempo. ¿Está encendida la placa y "
                "la laptop asociada a su red WiFi?"
            )
        if error.errno == 111:  # ECONNREFUSED
            return f"{destino} rechazó la conexión. ¿Está cargado el sketch y escuchando?"
        if error.errno in (113, 101):  # EHOSTUNREACH, ENETUNREACH
            return f"no se alcanza {destino}. La laptop no está en la misma red que la placa"
        return f"{destino}: {error}"

    def _leer_linea(self) -> str | None:
        """Devuelve una linea completa, acumulando lo que llegue partido.

        TCP es un flujo de bytes, no de mensajes: una lectura puede traer media
        linea o dos y media. Sin este bufer, las ordenes se parten y el otro
        extremo recibe basura.
        """
        if self._socket is None:
            return None

        while b"\n" not in self._resto:
            try:
                trozo = self._socket.recv(1024)
            except TimeoutError:
                return None
            if not trozo:
                raise ConnectionError("la placa cerró la conexión")
            self._resto += trozo

        linea, _, self._resto = self._resto.partition(b"\n")
        return linea.decode("utf-8", errors="replace")

    def _escribir_linea(self, linea: str) -> None:
        if self._socket is None:
            raise ArduinoNoDisponible("la conexión no está abierta")
        self._socket.sendall(f"{linea}\n".encode())

    def _cerrar(self) -> None:
        if self._socket is not None:
            try:
                self._socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            self._socket.close()
            self._socket = None
        self._resto = b""
