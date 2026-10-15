"""El protocolo vive en cinco sitios y tiene que decir lo mismo en los cinco.

`docs/protocolo.md` obliga a que cualquier cambio entre a la vez en los dos
adaptadores reales, el simulado y los dos sketches. Esa regla depende hoy de
que alguien se acuerde; estas pruebas la comprueban.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from vision_contador.core.modelos import Led
from vision_contador.ports import enlace_arduino as proto

RAIZ = Path(__file__).resolve().parents[1]
SKETCH_UNO = RAIZ / "arduino" / "vision_contador" / "vision_contador.ino"
SKETCH_ESP32 = RAIZ / "arduino" / "vision_contador_esp32" / "vision_contador_esp32.ino"
DOC = RAIZ / "docs" / "protocolo.md"

SKETCHES = [
    pytest.param(SKETCH_UNO, id="uno"),
    pytest.param(SKETCH_ESP32, id="esp32"),
]

#: Lo que la laptop puede llegar a enviar.
ORDENES = [
    proto.CMD_PENSANDO,
    proto.CMD_PING,
    proto.CMD_ID,
    "LCD1:",
    "LCD2:",
    "LED:",
]

#: Lo que la placa puede llegar a contestar.
RESPUESTAS = [proto.MSG_READY, proto.MSG_BTN, proto.MSG_OK, proto.PREFIJO_ERROR]


@pytest.mark.parametrize("sketch", SKETCHES)
@pytest.mark.parametrize("orden", ORDENES)
def test_los_sketches_entienden_todas_las_ordenes(sketch: Path, orden: str):
    assert f'"{orden}"' in sketch.read_text(encoding="utf-8"), (
        f"{sketch.name} no reconoce la orden «{orden}»"
    )


@pytest.mark.parametrize("sketch", SKETCHES)
@pytest.mark.parametrize("respuesta", RESPUESTAS)
def test_los_sketches_emiten_todas_las_respuestas(sketch: Path, respuesta: str):
    assert f'"{respuesta}' in sketch.read_text(encoding="utf-8"), (
        f"{sketch.name} nunca emite «{respuesta}»"
    )


@pytest.mark.parametrize("sketch", SKETCHES)
@pytest.mark.parametrize("led", list(Led))
def test_los_sketches_conocen_los_tres_colores(sketch: Path, led: Led):
    assert f'"{led.value}"' in sketch.read_text(encoding="utf-8")


@pytest.mark.parametrize("sketch", SKETCHES)
def test_cada_sketch_declara_su_identidad(sketch: Path):
    """Con dos placas conectadas hay que poder distinguirlas."""
    assert "IDENTIDAD" in sketch.read_text(encoding="utf-8")


def test_las_dos_placas_no_se_llaman_igual():
    def identidad(sketch: Path) -> str:
        for linea in sketch.read_text(encoding="utf-8").splitlines():
            if linea.startswith("const char IDENTIDAD"):
                return linea.split('"')[1]
        raise AssertionError(f"{sketch.name} no declara IDENTIDAD")

    assert identidad(SKETCH_UNO) != identidad(SKETCH_ESP32)


@pytest.mark.parametrize("orden", ORDENES + RESPUESTAS)
def test_el_documento_menciona_cada_mensaje(orden: str):
    assert orden in DOC.read_text(encoding="utf-8"), (
        f"docs/protocolo.md no documenta «{orden}»"
    )


def test_el_mock_contesta_lo_mismo_que_una_placa():
    """El simulado tiene que ser indistinguible del firmware para el enlace."""
    from vision_contador.adapters.arduino_mock import ArduinoMock

    class Escucha:
        def __init__(self): self.recibidas = []
        def al_recibir(self, linea): self.recibidas.append(linea)
        def al_enviar(self, linea): pass
        def al_cambiar_conexion(self, conectado, detalle): pass
        def al_pulsar_boton(self): pass

    import time

    mock = ArduinoMock(identidad="SIMULADA")
    escucha = Escucha()
    mock.suscribir(escucha)
    mock.conectar(mock.puertos_disponibles()[0], 9600)

    mock.enviar(proto.CMD_ID)
    mock.enviar(proto.cmd_led(Led.VERDE))
    time.sleep(0.3)

    assert proto.MSG_READY in escucha.recibidas
    assert f"{proto.PREFIJO_ID}SIMULADA" in escucha.recibidas
    assert proto.MSG_OK in escucha.recibidas
    mock.desconectar()


def test_las_filas_de_la_lcd_nunca_superan_las_columnas_fisicas():
    assert proto.cmd_lcd(1, "x" * 40) == "LCD1:" + "x" * 16
    with pytest.raises(ValueError):
        proto.cmd_lcd(3, "no existe la fila 3")
