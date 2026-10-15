"""Pruebas del compuesto que reparte entre varias placas."""

from __future__ import annotations

import time

import pytest
from placa_falsa import EscuchaDePrueba

from vision_contador.adapters.enlace_multiple import EnlaceMultiple
from vision_contador.ports.enlace_arduino import ArduinoNoDisponible, EnlaceArduino


class EnlaceDePrueba(EnlaceArduino):
    """Enlace mínimo que registra lo que le mandan."""

    def __init__(self, nombre: str, destino: str, puede_conectar: bool = True) -> None:
        self._nombre = nombre
        self._destino = destino
        self._puede = puede_conectar
        self._conectado = False
        self._escuchas: list = []
        self.enviadas: list[str] = []

    def puertos_disponibles(self): return [self._destino]
    def suscribir(self, escucha): self._escuchas.append(escucha)

    def conectar(self, puerto: str, baudios: int = 9600) -> None:
        if not self._puede:
            raise ArduinoNoDisponible(f"{self._nombre} no disponible")
        self._conectado = True
        for e in self._escuchas:
            e.al_cambiar_conexion(True, f"{self._destino} abierto")

    def desconectar(self) -> None:
        self._conectado = False
        for e in self._escuchas:
            e.al_cambiar_conexion(False, "cerrado")

    def enviar(self, orden: str) -> None:
        if not self._conectado:
            raise ArduinoNoDisponible(f"{self._nombre} cerrado")
        self.enviadas.append(orden)
        for e in self._escuchas:
            e.al_enviar(orden)

    def pulsar(self) -> None:
        for e in self._escuchas:
            e.al_pulsar_boton()

    def recibir(self, linea: str) -> None:
        for e in self._escuchas:
            e.al_recibir(linea)

    @property
    def conectado(self) -> bool: return self._conectado
    @property
    def puerto_actual(self) -> str: return self._destino if self._conectado else ""


@pytest.fixture
def dos():
    uno = EnlaceDePrueba("UNO", "/dev/ttyACM0")
    esp = EnlaceDePrueba("ESP32", "tcp://192.168.4.1:3333")
    return uno, esp, EnlaceMultiple({"UNO": uno, "ESP32": esp})


class TestReparto:
    def test_la_orden_llega_a_todas(self, dos):
        uno, esp, multiple = dos
        multiple.conectar("", 9600)
        multiple.enviar("LED:VERDE")
        assert uno.enviadas == ["LED:VERDE"]
        assert esp.enviadas == ["LED:VERDE"]

    def test_una_placa_caida_no_deja_mudas_a_las_demas(self, dos):
        uno, esp, multiple = dos
        multiple.conectar("", 9600)
        esp.desconectar()
        multiple.enviar("LED:ROJO")
        assert uno.enviadas == ["LED:ROJO"]

    def test_sin_ninguna_conectada_falla(self, dos):
        _, _, multiple = dos
        with pytest.raises(ArduinoNoDisponible, match="ninguna placa"):
            multiple.enviar("LED:VERDE")

    def test_destinos_unificados_y_sin_repetir(self, dos):
        _, _, multiple = dos
        assert multiple.puertos_disponibles() == [
            "/dev/ttyACM0", "tcp://192.168.4.1:3333"
        ]


class TestConexion:
    def test_conectado_basta_con_una(self, dos):
        uno, _esp, multiple = dos
        assert not multiple.conectado
        uno.conectar("", 9600)
        assert multiple.conectado, "con un actuador vivo el pipeline debe poder enviar"

    def test_si_una_falla_la_otra_conecta_igual(self):
        buena = EnlaceDePrueba("UNO", "/dev/ttyACM0")
        mala = EnlaceDePrueba("ESP32", "tcp://x", puede_conectar=False)
        multiple = EnlaceMultiple({"UNO": buena, "ESP32": mala})
        multiple.conectar("", 9600)
        assert multiple.conectado
        assert buena.conectado and not mala.conectado

    def test_solo_falla_si_no_conecta_ninguna(self):
        a = EnlaceDePrueba("A", "x", puede_conectar=False)
        b = EnlaceDePrueba("B", "y", puede_conectar=False)
        multiple = EnlaceMultiple({"A": a, "B": b})
        with pytest.raises(ArduinoNoDisponible):
            multiple.conectar("", 9600)

    def test_un_destino_concreto_conecta_solo_esa(self, dos):
        uno, esp, multiple = dos
        multiple.conectar("/dev/ttyACM0", 9600)
        assert uno.conectado and not esp.conectado

    def test_el_resumen_usa_nombres_y_cuenta_las_demas(self, dos):
        """Un destino tcp:// completo desbordaría el indicador de la barra."""
        uno, esp, multiple = dos
        assert multiple.puerto_actual == ""
        uno.conectar("", 9600)
        assert multiple.puerto_actual == "UNO"
        esp.conectar("", 9600)
        assert multiple.puerto_actual == "UNO +1"


class TestEventos:
    def test_las_lineas_se_etiquetan_con_la_placa(self, dos):
        uno, _, multiple = dos
        escucha = EscuchaDePrueba()
        multiple.suscribir(escucha)
        uno.recibir("OK")
        assert escucha.recibidas == ["[UNO] OK"]

    def test_con_una_sola_placa_no_se_etiqueta(self):
        uno = EnlaceDePrueba("UNO", "/dev/ttyACM0")
        multiple = EnlaceMultiple({"UNO": uno})
        escucha = EscuchaDePrueba()
        multiple.suscribir(escucha)
        uno.recibir("OK")
        assert escucha.recibidas == ["OK"]

    def test_dos_placas_con_pulsador_producen_una_sola_captura(self, dos):
        """Es el motivo de existir del antirrebote: dos BTN son una intención."""
        uno, esp, multiple = dos
        escucha = EscuchaDePrueba()
        multiple.suscribir(escucha)
        uno.pulsar()
        esp.pulsar()
        assert escucha.pulsaciones == 1

    def test_dos_pulsaciones_separadas_si_cuentan(self, dos, monkeypatch):
        # Se acorta la ventana en vez de dormir medio segundo en cada ejecución.
        monkeypatch.setattr(
            "vision_contador.adapters.enlace_multiple.SEGUNDOS_ANTIRREBOTE_BTN", 0.05
        )
        uno, _, multiple = dos
        escucha = EscuchaDePrueba()
        multiple.suscribir(escucha)
        uno.pulsar()
        time.sleep(0.1)
        uno.pulsar()
        assert escucha.pulsaciones == 2
