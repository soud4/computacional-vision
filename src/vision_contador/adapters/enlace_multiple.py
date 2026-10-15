"""Varias placas actuadoras detras de un solo enlace.

Implementa la misma interfaz que un enlace suelto, asi que la ventana y el
pipeline no distinguen si detras hay una placa o tres. Es lo que permite usar
un Arduino por USB y un ESP32 por WiFi a la vez sin que nada aguas arriba se
entere.
"""

from __future__ import annotations

import threading
import time

from ..ports.enlace_arduino import (
    ArduinoNoDisponible,
    EnlaceArduino,
    EscuchaArduino,
)

#: Dos placas con pulsador emiten ``BTN`` casi a la vez cuando en realidad es la
#: misma intencion del usuario. Dentro de esta ventana, el segundo se descarta;
#: sin esto el pipeline arrancaria dos capturas seguidas.
SEGUNDOS_ANTIRREBOTE_BTN = 0.5


class _Reenviador:
    """Escucha de una placa que reetiqueta sus eventos y los sube al compuesto."""

    def __init__(self, compuesto: EnlaceMultiple, nombre: str) -> None:
        self._compuesto = compuesto
        self._nombre = nombre

    def al_recibir(self, linea: str) -> None:
        self._compuesto._difundir_recibido(self._nombre, linea)

    def al_enviar(self, linea: str) -> None:
        self._compuesto._difundir_enviado(self._nombre, linea)

    def al_cambiar_conexion(self, conectado: bool, detalle: str) -> None:
        self._compuesto._difundir_conexion(self._nombre, conectado, detalle)

    def al_pulsar_boton(self) -> None:
        self._compuesto._difundir_pulsacion()


class EnlaceMultiple(EnlaceArduino):
    """Reparte las ordenes entre N enlaces y unifica sus eventos."""

    def __init__(self, enlaces: dict[str, EnlaceArduino]) -> None:
        self._enlaces = dict(enlaces)
        self._escuchas: list[EscuchaArduino] = []
        self._ultima_pulsacion = 0.0
        self._cerrojo = threading.Lock()

        for nombre, enlace in self._enlaces.items():
            enlace.suscribir(_Reenviador(self, nombre))

    @property
    def enlaces(self) -> dict[str, EnlaceArduino]:
        """Los enlaces individuales, por si alguna vista quiere dirigirse a uno."""
        return dict(self._enlaces)

    # --- Interfaz ----------------------------------------------------------
    def puertos_disponibles(self) -> list[str]:
        """Union de los destinos de todas las placas, sin repetir y en orden."""
        vistos: list[str] = []
        for enlace in self._enlaces.values():
            for destino in enlace.puertos_disponibles():
                if destino and destino not in vistos:
                    vistos.append(destino)
        return vistos

    def conectar(self, puerto: str, baudios: int = 9600) -> None:
        """Con destino vacio conecta todas; con uno concreto, solo esa placa.

        Solo se da por fallida la operacion si **ninguna** placa pudo abrirse:
        que el ESP32 este apagado no es razon para dejar sin actuador al
        Arduino que si esta conectado.
        """
        objetivos = [
            enlace
            for enlace in self._enlaces.values()
            if not puerto or puerto in enlace.puertos_disponibles() or puerto == enlace.puerto_actual
        ] or list(self._enlaces.values())

        errores: list[str] = []
        for enlace in objetivos:
            if enlace.conectado:
                continue
            try:
                enlace.conectar(puerto if puerto in enlace.puertos_disponibles() else "", baudios)
            except ArduinoNoDisponible as error:
                errores.append(str(error))

        if not self.conectado and errores:
            raise ArduinoNoDisponible("; ".join(errores))

    def desconectar(self) -> None:
        for enlace in self._enlaces.values():
            if enlace.conectado:
                enlace.desconectar()

    def enviar(self, orden: str) -> None:
        """Reparte la orden a todas las placas conectadas.

        Si una falla, las demas la reciben igual: un actuador caido no debe
        dejar mudos a los otros.
        """
        conectadas = [e for e in self._enlaces.values() if e.conectado]
        if not conectadas:
            raise ArduinoNoDisponible("no hay ninguna placa conectada")

        errores: list[str] = []
        for enlace in conectadas:
            try:
                enlace.enviar(orden)
            except ArduinoNoDisponible as error:
                errores.append(str(error))
        if len(errores) == len(conectadas):
            raise ArduinoNoDisponible("; ".join(errores))

    def suscribir(self, escucha: EscuchaArduino) -> None:
        self._escuchas.append(escucha)

    @property
    def conectado(self) -> bool:
        """Basta con una placa viva: el pipeline tiene a quien mandar."""
        return any(enlace.conectado for enlace in self._enlaces.values())

    @property
    def puerto_actual(self) -> str:
        """Resumen corto para la barra superior: ``ESP32`` o ``UNO +1``.

        Se usan los nombres de las placas y no sus destinos porque un
        ``tcp://192.168.4.1:3333`` desborda el indicador y aplasta la píldora de
        estado. El destino completo sigue a la vista en el desplegable de la
        consola, que es donde se elige.
        """
        activas = [nombre for nombre, e in self._enlaces.items() if e.conectado]
        if not activas:
            return ""
        return activas[0] if len(activas) == 1 else f"{activas[0]} +{len(activas) - 1}"

    @property
    def conectadas(self) -> int:
        return sum(1 for enlace in self._enlaces.values() if enlace.conectado)

    # --- Difusion de eventos ----------------------------------------------
    def _difundir_recibido(self, nombre: str, linea: str) -> None:
        etiquetada = self._etiquetar(nombre, linea)
        for escucha in list(self._escuchas):
            escucha.al_recibir(etiquetada)

    def _difundir_enviado(self, nombre: str, linea: str) -> None:
        # La orden se etiqueta igual que lo recibido para que la consola sea
        # legible, pero el espejo del hardware necesita la orden limpia: por eso
        # solo se antepone el nombre cuando hay mas de una placa.
        etiquetada = self._etiquetar(nombre, linea)
        for escucha in list(self._escuchas):
            escucha.al_enviar(etiquetada)

    def _difundir_conexion(self, nombre: str, conectado: bool, detalle: str) -> None:
        for escucha in list(self._escuchas):
            escucha.al_cambiar_conexion(self.conectado, f"{nombre}: {detalle}")

    def _difundir_pulsacion(self) -> None:
        """Una pulsacion, aunque la reporten dos placas."""
        ahora = time.monotonic()
        with self._cerrojo:
            if ahora - self._ultima_pulsacion < SEGUNDOS_ANTIRREBOTE_BTN:
                return
            self._ultima_pulsacion = ahora
        for escucha in list(self._escuchas):
            escucha.al_pulsar_boton()

    def _etiquetar(self, nombre: str, linea: str) -> str:
        return linea if len(self._enlaces) == 1 else f"[{nombre}] {linea}"
