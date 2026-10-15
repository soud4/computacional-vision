"""Pruebas del enlace TCP contra un servidor que habla el protocolo de verdad."""

from __future__ import annotations

import time

import pytest
from placa_falsa import EscuchaDePrueba, PlacaFalsaTcp

from vision_contador.adapters.enlace_tcp import EnlaceTcp, partir_destino
from vision_contador.core.config import ConfigPlaca
from vision_contador.ports.enlace_arduino import CMD_ID, ArduinoNoDisponible, cmd_lcd


def esperar(condicion, segundos: float = 3.0) -> bool:
    """Sondea hasta que se cumpla la condición o expire el plazo."""
    limite = time.monotonic() + segundos
    while time.monotonic() < limite:
        if condicion():
            return True
        time.sleep(0.02)
    return condicion()


@pytest.fixture
def placa():
    servidor = PlacaFalsaTcp()
    yield servidor
    servidor.cerrar()


@pytest.fixture
def enlace(placa):
    e = EnlaceTcp(ConfigPlaca(nombre="ESP32", transporte="tcp", destino=placa.destino))
    yield e
    e.desconectar()


class TestDestino:
    def test_formas_aceptadas(self):
        assert partir_destino("tcp://192.168.4.1:3333") == ("192.168.4.1", 3333)
        assert partir_destino("192.168.4.1:80") == ("192.168.4.1", 80)
        assert partir_destino("tcp://192.168.4.1") == ("192.168.4.1", 3333)

    def test_destino_vacio_o_invalido(self):
        with pytest.raises(ArduinoNoDisponible):
            partir_destino("")
        with pytest.raises(ArduinoNoDisponible):
            partir_destino("tcp://host:puerto")


class TestConexion:
    def test_conecta_y_saluda_con_id(self, enlace, placa):
        escucha = EscuchaDePrueba()
        enlace.suscribir(escucha)
        enlace.conectar(placa.destino)

        assert enlace.conectado
        assert placa.esperar_orden(CMD_ID), "el enlace debe preguntar ID al conectar"
        assert esperar(lambda: enlace.identidad == "ESP32")

    def test_recibe_el_ready_del_arranque(self, enlace, placa):
        escucha = EscuchaDePrueba()
        enlace.suscribir(escucha)
        enlace.conectar(placa.destino)
        assert esperar(lambda: "READY" in escucha.recibidas)

    def test_falla_con_mensaje_util_si_no_hay_nadie(self):
        # Puerto cerrado: nadie escucha en ese extremo.
        enlace = EnlaceTcp(
            ConfigPlaca(nombre="ESP32", transporte="tcp", destino="tcp://127.0.0.1:1")
        )
        with pytest.raises(ArduinoNoDisponible) as excinfo:
            enlace.conectar("")
        assert "127.0.0.1" in str(excinfo.value)
        assert not enlace.conectado

    def test_desconectar_cierra_y_avisa(self, enlace, placa):
        escucha = EscuchaDePrueba()
        enlace.suscribir(escucha)
        enlace.conectar(placa.destino)
        enlace.desconectar()
        assert not enlace.conectado
        assert any(not conectado for conectado, _ in escucha.conexiones)


class TestTrafico:
    def test_la_orden_llega_entera_a_la_placa(self, enlace, placa):
        enlace.conectar(placa.destino)
        orden = cmd_lcd(1, "Total: 4 objetos")
        enlace.enviar(orden)
        assert placa.esperar_orden(orden)

    def test_el_acuse_vuelve_al_escucha(self, enlace, placa):
        escucha = EscuchaDePrueba()
        enlace.suscribir(escucha)
        enlace.conectar(placa.destino)
        enlace.enviar("LED:VERDE")
        assert esperar(lambda: escucha.recibidas.count("OK") >= 1)
        assert "LED:VERDE" in escucha.enviadas

    def test_varias_ordenes_seguidas_no_se_mezclan(self, enlace, placa):
        """TCP es un flujo de bytes: sin bufer de líneas, las órdenes se parten."""
        enlace.conectar(placa.destino)
        ordenes = [cmd_lcd(1, "fila uno"), cmd_lcd(2, "fila dos"), "LED:ROJO"]
        for orden in ordenes:
            enlace.enviar(orden)
        for orden in ordenes:
            assert placa.esperar_orden(orden), f"se perdió o se partió «{orden}»"

    def test_el_boton_de_la_placa_llega_sin_preguntar(self, enlace, placa):
        escucha = EscuchaDePrueba()
        enlace.suscribir(escucha)
        enlace.conectar(placa.destino)
        assert esperar(lambda: enlace.identidad == "ESP32")

        placa.pulsar_boton()
        assert esperar(lambda: escucha.pulsaciones == 1)
        assert "BTN" in escucha.recibidas

    def test_enviar_sin_conectar_falla(self, enlace):
        with pytest.raises(ArduinoNoDisponible):
            enlace.enviar("LED:VERDE")


class TestPerdidaDeConexion:
    def test_si_la_placa_corta_el_enlace_se_entera(self, enlace, placa):
        escucha = EscuchaDePrueba()
        enlace.suscribir(escucha)
        enlace.conectar(placa.destino)
        assert esperar(lambda: enlace.identidad == "ESP32")

        placa.cortar()
        assert esperar(lambda: not enlace.conectado, 5.0)
        assert any("perdió la conexión" in linea for linea in escucha.recibidas)
