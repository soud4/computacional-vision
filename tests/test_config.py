"""Pruebas de la carga de configuracion."""

from __future__ import annotations

from pathlib import Path

import pytest

from vision_contador.core import config as cfg
from vision_contador.core.modelos import EtapaPreproc


@pytest.fixture
def defecto(tmp_path: Path) -> Path:
    ruta = tmp_path / "default.toml"
    ruta.write_text(
        """
[general]
modo = "demo"

[preprocesamiento]
gamma = 0.65
umbral_brillo = 90

[preprocesamiento.etapas]
suavizado = true

[preprocesamiento.roi]
x = 120
y = 80
ancho = 1040
alto = 560

[detector]
backend = "mock"
confianza_minima = 0.50
""",
        encoding="utf-8",
    )
    return ruta


def test_lee_el_preprocesamiento_del_archivo(defecto: Path, tmp_path: Path):
    """Regresion: el objeto de parametros se construia pero no se adjuntaba."""
    config = cfg.cargar(defecto, tmp_path / "no-existe.toml")
    assert config.preproc.gamma == 0.65
    assert config.preproc.umbral_brillo == 90
    assert config.preproc.roi.ancho == 1040
    assert config.preproc.confianza_minima == 0.50


def test_el_archivo_de_usuario_se_superpone(defecto: Path, tmp_path: Path):
    usuario = tmp_path / "usuario.toml"
    usuario.write_text(
        "[preprocesamiento]\ngamma = 1.2\n\n[preprocesamiento.etapas]\nsuavizado = false\n",
        encoding="utf-8",
    )
    config = cfg.cargar(defecto, usuario)
    assert config.preproc.gamma == 1.2
    assert config.preproc.etapas_activas[EtapaPreproc.SUAVIZADO] is False
    # Lo que el archivo de usuario no menciona conserva el valor por defecto.
    assert config.preproc.umbral_brillo == 90


def test_sin_archivos_usa_los_valores_por_defecto(tmp_path: Path):
    config = cfg.cargar(tmp_path / "a.toml", tmp_path / "b.toml")
    assert config.modo == "demo"
    assert config.es_demo


def test_ida_y_vuelta_al_guardar(defecto: Path, tmp_path: Path):
    """Lo que escribe la pestana Preprocesamiento se vuelve a leer igual."""
    config = cfg.cargar(defecto, tmp_path / "no-existe.toml")
    config.preproc.gamma = 0.42
    config.preproc.kernel_suavizado = 7
    config.preproc.etapas_activas[EtapaPreproc.ECUALIZACION] = False

    usuario = tmp_path / "usuario.toml"
    cfg.guardar_preprocesamiento(config.preproc, usuario)

    recargada = cfg.cargar(defecto, usuario)
    assert recargada.preproc.gamma == 0.42
    assert recargada.preproc.kernel_suavizado == 7
    assert recargada.preproc.etapas_activas[EtapaPreproc.ECUALIZACION] is False


def test_la_camara_acepta_indice_o_ruta_de_dispositivo(defecto: Path, tmp_path: Path):
    usuario = tmp_path / "usuario.toml"
    usuario.write_text(
        '[camara]\nindice = "/dev/video1"\nurl = "http://192.168.1.40:8080/video"\n'
        'fuente = "red"\n',
        encoding="utf-8",
    )
    config = cfg.cargar(defecto, usuario)
    assert config.camara.indice == "/dev/video1"
    # Con fuente "red" se abre la URL; el indice queda guardado para cuando se
    # vuelva a la camara local.
    assert config.camara.destino == "http://192.168.1.40:8080/video"

    config.camara.fuente = "local"
    assert config.camara.destino == "/dev/video1"


def test_una_fuente_desconocida_no_impide_arrancar(defecto: Path, tmp_path: Path):
    usuario = tmp_path / "usuario.toml"
    usuario.write_text('[camara]\nfuente = "telepatia"\n', encoding="utf-8")
    assert cfg.cargar(defecto, usuario).camara.fuente == "local"


def test_guardar_la_camara_conserva_el_preprocesamiento(defecto: Path, tmp_path: Path):
    usuario = tmp_path / "usuario.toml"
    config = cfg.cargar(defecto, usuario)
    config.preproc.gamma = 0.42
    cfg.guardar_preprocesamiento(config.preproc, usuario)

    camara = cfg.ConfigCamara(indice="/dev/video2", url="http://10.0.0.5:8080/video", fuente="red")
    cfg.guardar_camara(camara, usuario)

    vuelta = cfg.cargar(defecto, usuario)
    assert vuelta.camara.fuente == "red"
    assert vuelta.camara.indice == "/dev/video2"
    # El guardado reescribe el archivo entero, asi que lo que importa es que no
    # se haya llevado por delante la seccion de la otra pestana.
    assert vuelta.preproc.gamma == 0.42
