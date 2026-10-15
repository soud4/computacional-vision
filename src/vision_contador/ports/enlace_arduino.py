"""Puerto del enlace serial con el Arduino.

El contrato de mensajes esta documentado en ``docs/protocolo.md`` y lo respetan
identicamente el adaptador simulado, el real y el sketch ``.ino``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Protocol

from ..core.modelos import Led

# --- Ordenes que la laptop envia a la placa -----------------------------------
CMD_PENSANDO = "PENSANDO"
CMD_PING = "PING"
#: Pregunta quien hay al otro lado. Con dos placas conectadas a la vez, aceptar
#: cualquier ``OK`` como saludo no basta para saber cual contesto.
CMD_ID = "ID"


def cmd_lcd(fila: int, texto: str) -> str:
    """Construye ``LCD1:…`` o ``LCD2:…`` recortando a los 16 caracteres de la pantalla."""
    if fila not in (1, 2):
        raise ValueError(f"La LCD solo tiene filas 1 y 2, no {fila}")
    return f"LCD{fila}:{texto[:16]}"


def cmd_led(led: Led | None) -> str:
    """``LED:VERDE`` o ``LED:NINGUNO`` para apagarlos todos."""
    return f"LED:{led.value if led else 'NINGUNO'}"


# --- Mensajes que la placa envia a la laptop ----------------------------------
MSG_READY = "READY"
MSG_BTN = "BTN"
MSG_OK = "OK"
PREFIJO_ERROR = "ERR:"
#: Respuesta a ``ID``: ``ID:UNO``, ``ID:ESP32``…
PREFIJO_ID = "ID:"

#: Mensajes que valen como saludo al abrir el canal. Se acepta ``OK`` ademas de
#: ``READY`` porque hay montajes donde la placa no se reinicia al abrir el
#: puerto y el ``READY`` del arranque ya paso; y se acepta ``ID:`` para que un
#: firmware antiguo, que no conoce la orden ``ID``, siga conectando.
SALUDOS = (MSG_READY, MSG_OK)


def es_saludo(linea: str) -> bool:
    return linea in SALUDOS or linea.startswith(PREFIJO_ID)


def nombre_en_id(linea: str) -> str:
    """Extrae el nombre de un ``ID:UNO``; cadena vacia si no es una respuesta de identidad."""
    return linea[len(PREFIJO_ID):].strip() if linea.startswith(PREFIJO_ID) else ""


class EscuchaArduino(Protocol):
    """Quien quiera enterarse de lo que pasa en el puerto implementa esto.

    El adaptador llama a estos metodos desde su propio hilo; la interfaz los
    reenvia al hilo de Qt mediante senales.
    """

    def al_recibir(self, linea: str) -> None: ...
    def al_enviar(self, linea: str) -> None: ...
    def al_cambiar_conexion(self, conectado: bool, detalle: str) -> None: ...
    def al_pulsar_boton(self) -> None: ...


class EnlaceArduino(ABC):
    """Canal de ordenes hacia el Arduino y de eventos desde el Arduino."""

    @abstractmethod
    def puertos_disponibles(self) -> list[str]:
        """Nombres de puerto tal como los reporta el sistema operativo.

        En Windows seran ``COM3``, ``COM4``…; en Linux ``/dev/ttyUSB0`` o
        ``/dev/ttyACM0``. Nunca se codifica un nombre fijo.
        """

    @abstractmethod
    def conectar(self, puerto: str, baudios: int) -> None:
        """Abre el puerto y espera el ``READY`` del Arduino."""

    @abstractmethod
    def desconectar(self) -> None:
        """Cierra el puerto."""

    @abstractmethod
    def enviar(self, orden: str) -> None:
        """Encola una orden. No bloquea: el acuse llega por ``al_recibir``."""

    @abstractmethod
    def suscribir(self, escucha: EscuchaArduino) -> None:
        """Registra quien recibe los eventos del puerto."""

    @property
    @abstractmethod
    def conectado(self) -> bool: ...

    @property
    @abstractmethod
    def puerto_actual(self) -> str: ...


class ArduinoNoDisponible(RuntimeError):
    """El puerto no existe, esta ocupado o el Arduino no respondio ``READY``."""
