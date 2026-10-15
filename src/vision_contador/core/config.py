"""Carga y guardado de la configuracion en TOML."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .modelos import ETAPAS_CONFIGURABLES, EtapaPreproc, ParametrosPreproc, Rect

RAIZ = Path(__file__).resolve().parents[3]
RUTA_DEFECTO = RAIZ / "config" / "default.toml"
RUTA_USUARIO = RAIZ / "config" / "usuario.toml"

#: Nombre TOML de cada etapa configurable.
_CLAVE_ETAPA = {
    EtapaPreproc.GEOMETRICA: "geometrica",
    EtapaPreproc.GAMMA: "gamma",
    EtapaPreproc.ECUALIZACION: "ecualizacion",
    EtapaPreproc.SUAVIZADO: "suavizado",
    EtapaPreproc.MASCARA_ROI: "mascara_roi",
}


#: Valores validos de ``[camara].fuente``. Una imagen subida no se recuerda
#: entre sesiones: es siempre una eleccion del momento.
FUENTES = ("local", "red")


@dataclass(slots=True)
class ConfigCamara:
    """De donde salen los cuadros y con que ajustes se piden.

    ``fuente`` decide cual de los dos destinos se usa: ``indice`` para una
    camara conectada a la maquina y ``url`` para una de red, que es como se
    conecta la camara del telefono.
    """

    #: Indice de la camara (``0``) o ruta del dispositivo (``"/dev/video1"``):
    #: en Linux la ruta es mas estable que el numero, que baila al conectar y
    #: desconectar camaras.
    indice: int | str = 0
    ancho: int = 1280
    alto: int = 720
    fps: int = 30
    cuadros_a_descartar: int = 5
    url: str = ""
    fuente: str = "local"

    @property
    def destino(self) -> int | str:
        """Lo que hay que abrir: la camara local o la de red."""
        if self.fuente == "red" and self.url:
            return self.url
        return self.indice


@dataclass(slots=True)
class ConfigDetector:
    backend: str = "mock"
    confianza_minima: float = 0.50
    modelo: str = "YOLO11n"
    pesos: str = "yolo11n.pt"
    api: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ConfigPlaca:
    """Una placa actuadora: como se llama, por donde se habla con ella y a donde.

    ``destino`` es una cadena generica en vez de un nombre de puerto, porque no
    todas las placas se conectan por cable: para una de serie es ``/dev/ttyACM0``
    o ``COM3``, y para una de red ``tcp://192.168.4.1:3333``.
    """

    nombre: str = "Arduino"
    transporte: str = "serie"   # "serie" | "tcp"
    destino: str = ""           # vacio = autodetectar (solo tiene sentido en serie)
    baudios: int = 9600
    reconectar: bool = True


@dataclass(slots=True)
class ConfigArduino:
    """Configuracion de una sola placa por cable.

    Se conserva para que una configuracion anterior a ``[[placas]]`` siga
    arrancando sin tocarla.
    """

    puerto: str = ""
    baudios: int = 9600
    tiempo_limite_s: float = 2.0
    reconectar: bool = True

    def a_placa(self) -> ConfigPlaca:
        return ConfigPlaca(
            nombre="Arduino",
            transporte="serie",
            destino=self.puerto,
            baudios=self.baudios,
            reconectar=self.reconectar,
        )


@dataclass(slots=True)
class ConfigVoz:
    backend: str = "mock"
    voz: str = "es-PE-CamilaNeural"
    carpeta_cache: str = "cache/voz"


@dataclass(slots=True)
class Config:
    """Configuracion completa de la aplicacion."""

    modo: str = "demo"
    carpeta_registro: str = "capturas"
    camara: ConfigCamara = field(default_factory=ConfigCamara)
    detector: ConfigDetector = field(default_factory=ConfigDetector)
    arduino: ConfigArduino = field(default_factory=ConfigArduino)
    voz: ConfigVoz = field(default_factory=ConfigVoz)
    preproc: ParametrosPreproc = field(default_factory=ParametrosPreproc)
    placas: list[ConfigPlaca] = field(default_factory=list)

    @property
    def es_demo(self) -> bool:
        return self.modo == "demo"

    @property
    def ruta_registro(self) -> Path:
        return RAIZ / self.carpeta_registro


def _fundir(base: dict[str, Any], encima: dict[str, Any]) -> dict[str, Any]:
    """Mezcla recursiva de dos diccionarios TOML."""
    salida = dict(base)
    for clave, valor in encima.items():
        if isinstance(valor, dict) and isinstance(salida.get(clave), dict):
            salida[clave] = _fundir(salida[clave], valor)
        else:
            salida[clave] = valor
    return salida


def _leer(ruta: Path) -> dict[str, Any]:
    if not ruta.is_file():
        return {}
    with ruta.open("rb") as f:
        return tomllib.load(f)


def cargar(ruta_defecto: Path = RUTA_DEFECTO, ruta_usuario: Path = RUTA_USUARIO) -> Config:
    """Lee default.toml y le superpone usuario.toml si existe."""
    datos = _fundir(_leer(ruta_defecto), _leer(ruta_usuario))

    general = datos.get("general", {})
    pre = datos.get("preprocesamiento", {})
    etapas_toml = pre.get("etapas", {})
    roi_toml = pre.get("roi", {})
    det = datos.get("detector", {})

    preproc = ParametrosPreproc(
        activo=pre.get("activo", True),
        gamma=float(pre.get("gamma", 0.65)),
        kernel_suavizado=int(pre.get("kernel_suavizado", 3)),
        umbral_brillo=int(pre.get("umbral_brillo", 90)),
        umbral_contraste=int(pre.get("umbral_contraste", 40)),
        confianza_minima=float(det.get("confianza_minima", 0.50)),
        modo_adaptativo=pre.get("modo_adaptativo", True),
        etapas_activas={
            etapa: bool(etapas_toml.get(_CLAVE_ETAPA[etapa], True))
            for etapa in ETAPAS_CONFIGURABLES
        },
        roi=Rect(
            int(roi_toml.get("x", 120)),
            int(roi_toml.get("y", 80)),
            int(roi_toml.get("ancho", 1040)),
            int(roi_toml.get("alto", 560)),
        ),
    )

    cam = datos.get("camara", {})
    ard = datos.get("arduino", {})
    voz = datos.get("voz", {})
    placas = [_leer_placa(entrada) for entrada in datos.get("placas", [])]

    return Config(
        modo=general.get("modo", "demo"),
        carpeta_registro=general.get("carpeta_registro", "capturas"),
        camara=ConfigCamara(
            indice=_destino_local(cam.get("indice", 0)),
            ancho=int(cam.get("ancho", 1280)),
            alto=int(cam.get("alto", 720)),
            fps=int(cam.get("fps", 30)),
            cuadros_a_descartar=int(cam.get("cuadros_a_descartar", 5)),
            url=str(cam.get("url", "")),
            fuente=_fuente_valida(cam.get("fuente", "local")),
        ),
        detector=ConfigDetector(
            backend=det.get("backend", "mock"),
            confianza_minima=float(det.get("confianza_minima", 0.50)),
            modelo=det.get("modelo", "YOLO11n"),
            pesos=det.get("pesos", "yolo11n.pt"),
            api=det.get("api", {}),
        ),
        arduino=ConfigArduino(
            puerto=ard.get("puerto", ""),
            baudios=int(ard.get("baudios", 9600)),
            tiempo_limite_s=float(ard.get("tiempo_limite_s", 2.0)),
            reconectar=ard.get("reconectar", True),
        ),
        voz=ConfigVoz(
            backend=voz.get("backend", "mock"),
            voz=voz.get("voz", "es-PE-CamilaNeural"),
            carpeta_cache=voz.get("carpeta_cache", "cache/voz"),
        ),
        preproc=preproc,
        placas=placas,
    )


def _destino_local(valor: object) -> int | str:
    """``0``, ``"1"`` y ``"/dev/video1"`` son todos destinos locales validos."""
    texto = str(valor).strip()
    return int(texto) if texto.isdigit() else texto


def _fuente_valida(valor: object) -> str:
    """Una fuente desconocida en el TOML no debe impedir arrancar."""
    texto = str(valor)
    return texto if texto in FUENTES else "local"


def _leer_placa(entrada: dict[str, Any]) -> ConfigPlaca:
    return ConfigPlaca(
        nombre=str(entrada.get("nombre", "Placa")),
        transporte=str(entrada.get("transporte", "serie")),
        destino=str(entrada.get("destino", "")),
        baudios=int(entrada.get("baudios", 9600)),
        reconectar=bool(entrada.get("reconectar", True)),
    )


def _bloque_preprocesamiento(preproc: ParametrosPreproc) -> str:
    etapas = "\n".join(
        f"{_CLAVE_ETAPA[etapa]} = {str(preproc.etapa_activa(etapa) if preproc.activo else preproc.etapas_activas.get(etapa, True)).lower()}"
        for etapa in ETAPAS_CONFIGURABLES
    )
    return f"""[preprocesamiento]
activo = {str(preproc.activo).lower()}
gamma = {preproc.gamma:.2f}
kernel_suavizado = {preproc.kernel_suavizado}
umbral_brillo = {preproc.umbral_brillo}
umbral_contraste = {preproc.umbral_contraste}
modo_adaptativo = {str(preproc.modo_adaptativo).lower()}

[preprocesamiento.etapas]
{etapas}

[preprocesamiento.roi]
x = {preproc.roi.x}
y = {preproc.roi.y}
ancho = {preproc.roi.ancho}
alto = {preproc.roi.alto}

[detector]
confianza_minima = {preproc.confianza_minima:.2f}
"""


def _bloque_camara(camara: ConfigCamara) -> str:
    # Un indice se escribe como numero y una ruta de dispositivo entre comillas,
    # que es lo que espera TOML en cada caso.
    indice = camara.indice if isinstance(camara.indice, int) else f'"{camara.indice}"'
    return f"""[camara]
indice = {indice}
url = "{camara.url}"
fuente = "{camara.fuente}"
"""


def _escribir_usuario(
    ruta: Path,
    preproc: ParametrosPreproc | None = None,
    camara: ConfigCamara | None = None,
) -> None:
    """Reescribe usuario.toml conservando la seccion que no se esta guardando.

    El archivo se genera completo cada vez -es pequeno y de forma fija, y asi no
    hace falta una dependencia de escritura de TOML-, de modo que guardar el
    preprocesamiento borraria la camara, y al contrario, si no se releyera antes
    lo que ya hay.
    """
    actual = cargar(RUTA_DEFECTO, ruta)
    secciones = (
        _bloque_preprocesamiento(preproc if preproc is not None else actual.preproc),
        _bloque_camara(camara if camara is not None else actual.camara),
    )
    contenido = (
        "# Generado por Vision Contador desde la interfaz.\n"
        "# Se superpone a config/default.toml.\n\n" + "\n".join(secciones)
    )
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(contenido, encoding="utf-8")


def guardar_preprocesamiento(preproc: ParametrosPreproc, ruta: Path = RUTA_USUARIO) -> None:
    """Escribe en usuario.toml la seccion de preprocesamiento."""
    _escribir_usuario(ruta, preproc=preproc)


def guardar_camara(camara: ConfigCamara, ruta: Path = RUTA_USUARIO) -> None:
    """Escribe en usuario.toml la fuente de video elegida."""
    _escribir_usuario(ruta, camara=camara)
