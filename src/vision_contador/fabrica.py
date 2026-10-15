"""Fabrica de adaptadores.

Este es el unico lugar del programa donde se decide si se usa hardware real o
simulado. Todo lo demas habla con los puertos y no se entera de la diferencia.
"""

from __future__ import annotations

import importlib
from typing import Any

from .adapters.fuente_conmutable import FuenteConmutable
from .core.config import Config, ConfigPlaca
from .core.pipeline import Dependencias
from .ports.detector import Detector
from .ports.enlace_arduino import EnlaceArduino
from .ports.preprocesador import Preprocesador
from .ports.voz import SintetizadorVoz
from .services.registro import Registro


class AdaptadorNoImplementado(NotImplementedError):
    """No se pudo cargar el adaptador real pedido."""


def _cargar(modulo: str, clase: str, extra: str = "") -> Any:
    """Importa un adaptador diciendo con precision que es lo que falta.

    Importa saber si falta el archivo del adaptador o una dependencia de
    terceros, porque la solucion es muy distinta: escribir codigo o instalar un
    paquete. Un mensaje que ofrece las dos posibilidades a la vez manda al
    usuario a instalar algo que ya tiene.
    """
    try:
        return getattr(importlib.import_module(f".adapters.{modulo}", __package__), clase)
    except ImportError as error:
        ausente = getattr(error, "name", "") or ""
        if ausente.endswith(f"adapters.{modulo}"):
            raise AdaptadorNoImplementado(
                f"falta el archivo src/vision_contador/adapters/{modulo}.py. "
                f"La hoja de ruta para escribirlo está en docs/IMPLEMENTACION_REAL.md"
            ) from error
        sugerencia = f" (uv pip install -e '.[{extra}]')" if extra else ""
        raise AdaptadorNoImplementado(
            f"falta la dependencia «{ausente}»{sugerencia}"
        ) from error
    except AttributeError as error:
        raise AdaptadorNoImplementado(
            f"adapters/{modulo}.py no define la clase {clase}"
        ) from error


def crear_camara(config: Config) -> FuenteConmutable:
    """La fuente de video, envuelta para poder cambiarla en caliente.

    Se devuelve siempre un ``FuenteConmutable`` -tambien en modo demo- para que
    la interfaz pueda pasar a una imagen de archivo o a otra camara sin
    reconstruir las dependencias ni reiniciar el hilo de video.
    """
    if config.es_demo:
        from .adapters.camara_mock import CamaraMock

        return FuenteConmutable(CamaraMock(fps=config.camara.fps))

    return FuenteConmutable(
        _cargar("camara_opencv", "CamaraOpenCV", "vision")(config.camara)
    )


def crear_preprocesador(config: Config) -> Preprocesador:
    # El preprocesamiento en numpy es implementacion real, no simulada: sirve
    # igual en modo demo y con la camara de verdad.
    from .adapters.preproc_numpy import PreprocesadorNumpy

    return PreprocesadorNumpy()


def crear_detector(config: Config) -> Detector:
    backend = "mock" if config.es_demo else config.detector.backend

    if backend == "mock":
        from .adapters.detector_mock import DetectorMock

        return DetectorMock(nombre=config.detector.modelo)

    if backend == "yolo":
        return _cargar("detector_yolo", "DetectorYolo", "yolo")(config.detector)

    if backend == "api":
        return _cargar("detector_api", "DetectorApi", "api")(config.detector)

    raise ValueError(f"Backend de detector desconocido: {backend!r}")


#: Que adaptador implementa cada transporte de ``[[placas]]``.
TRANSPORTES = {
    "serie": ("enlace_serie", "EnlaceSerie", ""),
    "tcp": ("enlace_tcp", "EnlaceTcp", ""),
}


def crear_enlace_placa(placa: ConfigPlaca) -> EnlaceArduino:
    """Un enlace para una placa, segun su transporte."""
    try:
        modulo, clase, extra = TRANSPORTES[placa.transporte]
    except KeyError:
        raise ValueError(
            f"transporte desconocido «{placa.transporte}» en la placa «{placa.nombre}»; "
            f"válidos: {', '.join(sorted(TRANSPORTES))}"
        ) from None
    return _cargar(modulo, clase, extra)(placa)


def crear_arduino(config: Config) -> EnlaceArduino:
    """El canal hacia las placas actuadoras.

    Con una sola placa se devuelve su enlace directamente: el compuesto solo
    aporta cuando hay varias, y no conviene pagar una capa que no hace falta.
    """
    if config.es_demo:
        from .adapters.arduino_mock import ArduinoMock

        return ArduinoMock()

    # Sin ``[[placas]]`` se usa el ``[arduino]`` de siempre, para que una
    # configuracion anterior siga arrancando sin tocarla.
    placas = config.placas or [config.arduino.a_placa()]
    enlaces = {placa.nombre: crear_enlace_placa(placa) for placa in placas}

    if len(enlaces) == 1:
        return next(iter(enlaces.values()))

    return _cargar("enlace_multiple", "EnlaceMultiple")(enlaces)


def crear_voz(config: Config) -> SintetizadorVoz:
    backend = "mock" if config.es_demo else config.voz.backend

    if backend == "mock":
        from .adapters.voz_mock import VozMock

        return VozMock()

    if backend == "edge-tts":
        return _cargar("voz_edge_tts", "VozEdgeTts", "voz")(config.voz)

    raise ValueError(f"Backend de voz desconocido: {backend!r}")


def crear_dependencias(config: Config) -> Dependencias:
    """Arma el juego completo de adaptadores que necesita el pipeline."""
    return Dependencias(
        camara=crear_camara(config),
        preprocesador=crear_preprocesador(config),
        detector=crear_detector(config),
        arduino=crear_arduino(config),
        voz=crear_voz(config),
        # En modo demo tambien se registra: asi el CSV y las imagenes se pueden
        # revisar antes de tener el equipo delante.
        registro=Registro(config.ruta_registro),
    )
