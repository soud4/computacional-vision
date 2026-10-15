"""Pruebas del enlace serie contra un pseudoterminal.

``os.openpty()`` da un par de dispositivos de verdad: pyserial abre el esclavo
creyendo que es un puerto, y la prueba escribe y lee por el maestro haciendo de
placa. Se ejercita el camino real del adaptador, no una imitación.

Es específico de Unix, así que en Windows se omite.
"""

from __future__ import annotations

import os
import time

import pytest
from placa_falsa import EscuchaDePrueba

from vision_contador.adapters.enlace_serie import EnlaceSerie, explicar, puertos_del_sistema
from vision_contador.core.config import ConfigPlaca
from vision_contador.ports.enlace_arduino import CMD_ID, ArduinoNoDisponible

pytestmark = pytest.mark.skipif(
    not hasattr(os, "openpty"), reason="openpty solo existe en Unix"
)


def esperar(condicion, segundos: float = 3.0) -> bool:
    limite = time.monotonic() + segundos
    while time.monotonic() < limite:
        if condicion():
            return True
        time.sleep(0.02)
    return condicion()


class PlacaFalsaSerie:
    """El extremo maestro del pty, haciendo de Arduino."""

    def __init__(self) -> None:
        self.maestro, self.esclavo = os.openpty()
        os.set_blocking(self.maestro, False)
        self.destino = os.ttyname(self.esclavo)
        self._resto = b""

    def leer_ordenes(self) -> list[str]:
        try:
            self._resto += os.read(self.maestro, 4096)
        except (BlockingIOError, OSError):
            pass
        ordenes = []
        while b"\n" in self._resto:
            linea, _, self._resto = self._resto.partition(b"\n")
            texto = linea.decode(errors="replace").strip()
            if texto:
                ordenes.append(texto)
        return ordenes

    def responder(self, linea: str) -> None:
        os.write(self.maestro, f"{linea}\n".encode())

    def cerrar(self) -> None:
        for descriptor in (self.maestro, self.esclavo):
            try:
                os.close(descriptor)
            except OSError:
                pass


@pytest.fixture
def placa():
    p = PlacaFalsaSerie()
    yield p
    p.cerrar()


@pytest.fixture
def enlace(placa):
    e = EnlaceSerie(ConfigPlaca(nombre="UNO", transporte="serie", destino=placa.destino))
    yield e
    e.desconectar()


def test_conecta_y_pregunta_la_identidad(enlace, placa):
    enlace.conectar(placa.destino)
    assert enlace.conectado
    assert esperar(lambda: CMD_ID in placa.leer_ordenes())


def test_la_orden_llega_con_su_terminador(enlace, placa):
    enlace.conectar(placa.destino)
    vistas: list[str] = []
    enlace.enviar("LCD1:Total: 4 objetos")
    assert esperar(lambda: vistas.extend(placa.leer_ordenes()) or "LCD1:Total: 4 objetos" in vistas)


def test_lo_que_responde_la_placa_llega_al_escucha(enlace, placa):
    escucha = EscuchaDePrueba()
    enlace.suscribir(escucha)
    enlace.conectar(placa.destino)
    placa.responder("ID:UNO")
    assert esperar(lambda: enlace.identidad == "UNO")
    assert "ID:UNO" in escucha.recibidas


def test_el_pulsador_fisico_dispara_la_senal(enlace, placa):
    escucha = EscuchaDePrueba()
    enlace.suscribir(escucha)
    enlace.conectar(placa.destino)
    placa.responder("BTN")
    assert esperar(lambda: escucha.pulsaciones == 1)


def test_un_puerto_inexistente_falla_con_mensaje_util():
    enlace = EnlaceSerie(
        ConfigPlaca(nombre="UNO", transporte="serie", destino="/dev/ttyNOEXISTE")
    )
    with pytest.raises(ArduinoNoDisponible) as excinfo:
        enlace.conectar("")
    assert "ttyNOEXISTE" in str(excinfo.value)


def test_sin_puertos_lo_dice_en_vez_de_inventarse_uno(monkeypatch):
    monkeypatch.setattr(
        "vision_contador.adapters.enlace_serie.puertos_del_sistema", lambda: []
    )
    enlace = EnlaceSerie(ConfigPlaca(nombre="UNO", transporte="serie", destino=""))
    with pytest.raises(ArduinoNoDisponible, match="ningún puerto serie"):
        enlace.conectar("")


class TestEnumeracionDePuertos:
    def test_descarta_los_ttyS_fantasma_del_chipset(self, monkeypatch):
        """En Linux comports() devuelve una treintena de puertos que no existen."""

        class Falso:
            def __init__(self, device, vid=None):
                self.device, self.vid = device, vid

        monkeypatch.setattr(
            "vision_contador.adapters.enlace_serie.list_ports.comports",
            lambda: [Falso(f"/dev/ttyS{i}") for i in range(32)],
        )
        assert puertos_del_sistema() == []

    def test_los_vid_conocidos_van_primero(self, monkeypatch):
        class Falso:
            def __init__(self, device, vid=None):
                self.device, self.vid = device, vid

        monkeypatch.setattr(
            "vision_contador.adapters.enlace_serie.list_ports.comports",
            lambda: [Falso("/dev/ttyUSB9", 0x1234), Falso("/dev/ttyACM0", 0x2341)],
        )
        assert puertos_del_sistema()[0] == "/dev/ttyACM0"


class TestMensajesDeError:
    def test_permiso_denegado_dice_que_hacer(self):
        mensaje = explicar("/dev/ttyACM0", PermissionError("Permission denied"))
        assert "usermod" in mensaje

    def test_puerto_ocupado_senala_al_ide(self):
        """«Access is denied» en Windows es un puerto ocupado, no un problema de grupos."""
        mensaje = explicar("COM3", OSError("Access is denied"))
        assert "ocupado" in mensaje
        assert "usermod" not in mensaje

    def test_puerto_inexistente(self):
        mensaje = explicar("/dev/ttyX", OSError("could not open port"))
        assert "no disponible" in mensaje
