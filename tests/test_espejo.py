"""Pruebas del espejo del estado del hardware."""

from __future__ import annotations

from vision_contador.core.modelos import Led
from vision_contador.ui.espejo import EspejoHardware


def test_las_ordenes_de_lcd_llenan_las_dos_filas():
    e = EspejoHardware()
    e.al_enviar("LCD1:Total: 4 objetos")
    e.al_enviar("LCD2:Bo1 Ta1 Ce1 Li1")
    assert e.lcd == ["Total: 4 objetos", "Bo1 Ta1 Ce1 Li1"]


def test_la_lcd_recorta_a_dieciseis_columnas():
    e = EspejoHardware()
    e.al_enviar("LCD1:" + "x" * 40)
    assert len(e.lcd[0]) == 16


def test_los_leds_son_exclusivos():
    """Encender uno apaga los demás, igual que en el hardware."""
    e = EspejoHardware()
    e.al_enviar("LED:AMARILLO")
    e.al_enviar("LED:VERDE")
    assert e.leds == {Led.AMARILLO: False, Led.VERDE: True, Led.ROJO: False}


def test_ninguno_los_apaga_todos():
    e = EspejoHardware()
    e.al_enviar("LED:ROJO")
    e.al_enviar("LED:NINGUNO")
    assert not any(e.leds.values())


def test_un_color_desconocido_no_rompe_el_espejo():
    e = EspejoHardware()
    e.al_enviar("LED:MORADO")
    assert not any(e.leds.values())


def test_pensando_escribe_en_la_lcd():
    e = EspejoHardware()
    e.al_enviar("LCD2:algo viejo")
    e.al_enviar("PENSANDO")
    assert e.lcd == ["Pensando...", ""]


def test_las_ordenes_sin_efecto_visible_se_ignoran():
    e = EspejoHardware()
    e.al_enviar("LED:VERDE")
    e.al_enviar("PING")
    assert e.leds[Led.VERDE] is True


def test_el_contador_de_pulsaciones_avanza():
    e = EspejoHardware()
    assert e.ultima_pulsacion == "—"
    e.anotar_pulsacion()
    e.anotar_pulsacion()
    assert e.pulsaciones == 2
    assert e.ultima_pulsacion != "—"


def test_reiniciar_olvida_el_estado_pero_no_las_pulsaciones():
    """Al perder la conexión ya no se sabe qué tiene puesto la placa."""
    e = EspejoHardware()
    e.anotar_pulsacion()
    e.al_enviar("LED:VERDE")
    e.al_enviar("LCD1:algo")
    e.reiniciar()
    assert not any(e.leds.values())
    assert e.lcd == ["", ""]
    assert e.pulsaciones == 1


class TestVariasPlacas:
    """Con el enlace compuesto las líneas llegan etiquetadas con la placa."""

    def test_la_etiqueta_de_la_placa_no_estorba(self):
        e = EspejoHardware()
        e.al_enviar("[UNO] LED:VERDE")
        assert e.leds[Led.VERDE] is True

    def test_tambien_en_las_filas_de_la_lcd(self):
        e = EspejoHardware()
        e.al_enviar("[ESP32] LCD1:Total: 4 objetos")
        assert e.lcd[0] == "Total: 4 objetos"

    def test_una_orden_sin_etiqueta_sigue_funcionando(self):
        e = EspejoHardware()
        e.al_enviar("LED:ROJO")
        assert e.leds[Led.ROJO] is True

    def test_un_corchete_dentro_del_texto_de_la_lcd_se_respeta(self):
        e = EspejoHardware()
        e.al_enviar("LCD2:[ok] 4 obj")
        assert e.lcd[1] == "[ok] 4 obj"
