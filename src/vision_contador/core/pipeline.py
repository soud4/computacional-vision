"""Orquestador del flujo completo de una captura.

Es el unico lugar que conoce el orden de los pasos descritos en la seccion 4.3
del documento del proyecto. No sabe nada de Qt ni de hardware: habla solo con
los puertos, asi que la misma clase sirve en modo demo y con el equipo real.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime

from ..ports.camara import FuenteVideo
from ..ports.detector import Detector
from ..ports.enlace_arduino import CMD_PENSANDO, EnlaceArduino, cmd_lcd, cmd_led
from ..ports.preprocesador import Preprocesador
from ..ports.voz import SintetizadorVoz
from ..services import contador, frase, histograma
from ..services.lexico import nombre_es
from ..services.registro import Registro
from .modelos import Led, ParametrosPreproc, ResultadoCaptura

#: Pasos del flujo, en el orden en que se informan por ``al_progresar``.
PASOS = (
    "Capturando imagen…",
    "Aplicando preprocesamiento…",
    "Ejecutando YOLO…",
    "Contando objetos…",
    "Enviando al Arduino…",
)


@dataclass(slots=True)
class Dependencias:
    """Los adaptadores con los que trabaja el pipeline."""

    camara: FuenteVideo
    preprocesador: Preprocesador
    detector: Detector
    arduino: EnlaceArduino
    voz: SintetizadorVoz
    registro: Registro | None = None


class Pipeline:
    """Captura → preproceso → deteccion → conteo → frase → actuadores → registro."""

    def __init__(self, deps: Dependencias) -> None:
        self._deps = deps

    def ejecutar(
        self,
        params: ParametrosPreproc,
        al_progresar: Callable[[int, str], None] | None = None,
    ) -> ResultadoCaptura:
        """Corre una pasada completa y devuelve el resultado.

        Bloquea el hilo que la llama durante cientos de milisegundos, asi que la
        interfaz la invoca siempre desde un hilo de trabajo.
        """
        avisar = al_progresar or (lambda _i, _t: None)
        deps = self._deps

        # El Arduino muestra "Pensando..." antes de que empiece el trabajo pesado,
        # para que la respuesta fisica sea inmediata al pulsador.
        if deps.arduino.conectado:
            deps.arduino.enviar(CMD_PENSANDO)
            deps.arduino.enviar(cmd_led(Led.AMARILLO))

        avisar(0, PASOS[0])
        momento = datetime.now()
        capturada = deps.camara.capturar_estable()
        hist_antes = histograma.calcular(capturada)

        avisar(1, PASOS[1])
        preproc = deps.preprocesador.procesar(capturada, params)
        hist_despues = histograma.calcular(preproc.final)

        avisar(2, PASOS[2])
        inicio = time.perf_counter()
        deteccion = deps.detector.detectar(preproc.final, params.confianza_minima)
        ms = deteccion.ms or int((time.perf_counter() - inicio) * 1000)

        avisar(3, PASOS[3])
        # El detector trabaja con los nombres de COCO en ingles. Se traducen aqui,
        # en la frontera del nucleo, para que todo lo que sale del pipeline -las
        # etiquetas de las cajas, la lista de conteo, la frase y el CSV- hable un
        # solo idioma.
        detecciones = [
            replace(d, clase=nombre_es(d.clase))
            for d in contador.filtrar(deteccion.detecciones, params.confianza_minima)
        ]
        conteos = contador.contar(detecciones)
        texto = frase.generar(conteos)

        resultado = ResultadoCaptura(
            momento=momento,
            capturada=capturada,
            etapas=preproc.etapas,
            etapas_aplicadas=preproc.aplicadas,
            detecciones=detecciones,
            conteos=conteos,
            frase=texto,
            modelo=deteccion.modelo,
            ms_inferencia=ms,
            histograma_antes=hist_antes,
            histograma_despues=hist_despues,
        )

        avisar(4, PASOS[4])
        self._notificar_arduino(resultado)
        deps.voz.decir(texto)

        if deps.registro is not None:
            deps.registro.anotar(resultado)

        return resultado

    def _notificar_arduino(self, resultado: ResultadoCaptura) -> None:
        """Envia el resumen a la LCD y enciende el LED que corresponde.

        Verde si hubo detecciones, rojo si no hubo ninguna. Si el puerto esta
        caido no se intenta nada: capturar debe seguir funcionando sin Arduino.
        """
        arduino = self._deps.arduino
        if not arduino.conectado:
            return
        arduino.enviar(cmd_lcd(1, frase.fila_lcd_total(resultado.conteos)))
        arduino.enviar(cmd_lcd(2, frase.fila_lcd_detalle(resultado.conteos)))
        arduino.enviar(cmd_led(Led.VERDE if resultado.conteos else Led.ROJO))
