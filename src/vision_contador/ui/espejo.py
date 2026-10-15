"""Espejo del estado del hardware.

La interfaz tiene que mostrar en que estado estan la LCD y los LEDs, pero
preguntarselo al adaptador solo funcionaria con el simulado: el enlace serial
real no puede leer el estado del Arduino, porque el protocolo no lo contempla y
no merece la pena complicarlo para eso.

La solucion es deducirlo de las ordenes que salen. Como toda orden pasa por
``al_enviar``, este espejo se mantiene al dia con cualquier adaptador, y ademas
refleja los cambios manuales de la pestana Arduino sin cableado adicional.
"""

from __future__ import annotations

import re
from datetime import datetime

from ..core.modelos import Led

#: Con varias placas, el enlace compuesto antepone su nombre a cada linea
#: (``[UNO] LED:VERDE``) para que la consola sea legible. El espejo necesita la
#: orden limpia, asi que la etiqueta se quita aqui en vez de obligar al resto
#: del programa a saber si hay una placa o tres.
_ETIQUETA = re.compile(r"^\[[^\]]*\]\s*")


def sin_etiqueta(linea: str) -> str:
    return _ETIQUETA.sub("", linea, count=1)


class EspejoHardware:
    """Lo que la laptop cree que el Arduino tiene puesto en este momento."""

    def __init__(self) -> None:
        self.leds: dict[Led, bool] = {led: False for led in Led}
        self.lcd: list[str] = ["", ""]
        self.pulsaciones = 0
        self.ultima_pulsacion = "—"

    def al_enviar(self, orden: str) -> None:
        """Actualiza el espejo con una orden que acaba de salir hacia las placas."""
        orden = sin_etiqueta(orden)
        if orden.startswith("LCD1:"):
            self.lcd[0] = orden[5:][:16]
        elif orden.startswith("LCD2:"):
            self.lcd[1] = orden[5:][:16]
        elif orden.startswith("LED:"):
            self.encender(_led_por_nombre(orden[4:]))
        elif orden == "PENSANDO":
            self.lcd = ["Pensando...", ""]

    def encender(self, led: Led | None) -> None:
        """Los LEDs son exclusivos, igual que en el hardware."""
        self.leds = {uno: uno is led for uno in Led}

    def apagar_todos(self) -> None:
        self.encender(None)

    def anotar_pulsacion(self) -> None:
        self.pulsaciones += 1
        self.ultima_pulsacion = datetime.now().strftime("%H:%M:%S")

    def reiniciar(self) -> None:
        """Al perder la conexion ya no se sabe que tiene puesto la placa."""
        self.apagar_todos()
        self.lcd = ["", ""]


def _led_por_nombre(nombre: str) -> Led | None:
    try:
        return Led(nombre)
    except ValueError:
        return None
