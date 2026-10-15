"""Motor del protocolo de lineas, independiente del transporte.

El contrato de ``docs/protocolo.md`` es el mismo se hable por un cable USB o por
un socket TCP: una orden por linea terminada en ``\\n``, acuses con ``OK`` y
eventos espontaneos desde la placa. Lo que cambia entre un medio y otro son
cuatro operaciones: abrir, leer una linea, escribir una linea y cerrar.

Esta clase se queda con todo lo demas -la cola de envio, los tres hilos, el
saludo, el reparto a los escuchas y la reconexion- para que anadir un transporte
nuevo no obligue a reescribir doscientas lineas de concurrencia que despues se
desincronizan entre si.
"""

from __future__ import annotations

import queue
import threading
import time
from abc import abstractmethod

from ..ports.enlace_arduino import (
    CMD_ID,
    CMD_PING,
    MSG_BTN,
    ArduinoNoDisponible,
    EnlaceArduino,
    EscuchaArduino,
    es_saludo,
    nombre_en_id,
)

#: Cuanto se espera a que la placa salude despues de abrir el canal.
#: Al abrir un puerto serie la placa se reinicia por la senal DTR y tarda cerca
#: de dos segundos en arrancar, asi que el limite de las ordenes normales se
#: queda corto para el saludo.
SEGUNDOS_SALUDO = 4.0

#: Cada cuanto se manda PING para comprobar que el canal sigue vivo.
SEGUNDOS_LATIDO = 5.0

#: Espera entre intentos de reconexion.
SEGUNDOS_REINTENTO = 2.0


class EnlaceLineas(EnlaceArduino):
    """Base de los enlaces reales: implementa el protocolo, delega el medio."""

    def __init__(self, nombre: str, reconectar: bool = True) -> None:
        self._nombre = nombre
        self._configurado_reconectar = reconectar

        self._escuchas: list[EscuchaArduino] = []
        self._cola: queue.Queue[str] = queue.Queue()
        self._cerrojo = threading.Lock()
        self._activo = threading.Event()
        self._visto_saludo = threading.Event()
        self._hilos: dict[str, threading.Thread] = {}

        self._destino = ""
        self._abierto = False
        #: Queda en False cuando el usuario desconecta a mano, para que el
        #: vigilante no vuelva a abrir el canal por su cuenta.
        self._reconectar = False
        #: Lo que la placa contesto a ``ID``. Vacio si no lo soporta.
        self.identidad = ""

    # --- Lo que cada transporte debe implementar ---------------------------
    @abstractmethod
    def _abrir(self, destino: str) -> None:
        """Abre el canal o lanza ``ArduinoNoDisponible`` con un mensaje util."""

    @abstractmethod
    def _leer_linea(self) -> str | None:
        """Devuelve la siguiente linea, o ``None`` si expiro el tiempo de espera.

        Debe tener un tiempo de espera corto, de unas decimas, para que cerrar
        el enlace no tenga que esperar a que llegue un mensaje.
        """

    @abstractmethod
    def _escribir_linea(self, linea: str) -> None:
        """Envia una linea, ya sin el terminador."""

    @abstractmethod
    def _cerrar(self) -> None:
        """Cierra el canal. No debe lanzar."""

    def _destinos_del_transporte(self) -> list[str]:
        """Destinos que este transporte puede ofrecer ahora mismo."""
        return [self._destino] if self._destino else []

    # --- Interfaz publica --------------------------------------------------
    @property
    def nombre(self) -> str:
        return self._nombre

    def puertos_disponibles(self) -> list[str]:
        return self._destinos_del_transporte()

    def conectar(self, puerto: str, baudios: int = 9600) -> None:
        destino = puerto or self._destino
        with self._cerrojo:
            if self._abierto:
                return
            self._abrir(destino)
            self._abierto = True

        self._destino = destino
        self._reconectar = self._configurado_reconectar
        self._activo.set()
        self._arrancar_hilos()
        self._avisar_conexion(True, f"{self._nombre} en {destino}")
        self._saludar()

    def desconectar(self) -> None:
        self._reconectar = False
        self._activo.clear()
        self._cerrar_canal()
        self._avisar_conexion(False, "desconectado por el usuario")

    def enviar(self, orden: str) -> None:
        if not self.conectado:
            raise ArduinoNoDisponible(f"{self._nombre}: el canal no está abierto")
        self._cola.put(orden)

    def suscribir(self, escucha: EscuchaArduino) -> None:
        self._escuchas.append(escucha)

    @property
    def conectado(self) -> bool:
        return self._abierto

    @property
    def puerto_actual(self) -> str:
        return self._destino

    # --- Saludo ------------------------------------------------------------
    def _saludar(self) -> None:
        """Comprueba que al otro lado hay una placa con nuestro firmware.

        Se pregunta con ``ID``, que ademas dice cual es. Un firmware antiguo que
        no conozca la orden respondera ``ERR:orden desconocida``, asi que ese
        caso tambien vale como senal de vida.
        """
        self._visto_saludo.clear()
        self.enviar(CMD_ID)
        if not self._visto_saludo.wait(SEGUNDOS_SALUDO):
            self._avisar_conexion(
                True,
                f"{self._destino} abierto, pero {self._nombre} no respondió. "
                "¿Está cargado el sketch?",
            )

    # --- Hilos -------------------------------------------------------------
    def _arrancar_hilos(self) -> None:
        for clave, objetivo in (
            ("lector", self._bucle_lector),
            ("escritor", self._bucle_escritor),
            ("vigilante", self._bucle_vigilante),
        ):
            hilo = self._hilos.get(clave)
            if hilo is not None and hilo.is_alive():
                continue
            hilo = threading.Thread(
                target=objetivo, name=f"{self._nombre}-{clave}", daemon=True
            )
            self._hilos[clave] = hilo
            hilo.start()

    def _bucle_lector(self) -> None:
        while self._activo.is_set():
            if not self._abierto:
                time.sleep(0.1)
                continue
            try:
                linea = self._leer_linea()
            except Exception as error:
                self._al_perder_canal(str(error))
                continue
            if not linea:
                continue  # expiro el tiempo de espera, no es un error
            self._repartir(linea.strip())

    def _repartir(self, linea: str) -> None:
        if not linea:
            return
        if es_saludo(linea) or linea.startswith("ERR:"):
            self._visto_saludo.set()
        identidad = nombre_en_id(linea)
        if identidad:
            self.identidad = identidad

        for escucha in list(self._escuchas):
            escucha.al_recibir(linea)
        if linea == MSG_BTN:
            for escucha in list(self._escuchas):
                escucha.al_pulsar_boton()

    def _bucle_escritor(self) -> None:
        """Vacia la cola para que ``enviar`` no bloquee a quien llama."""
        while self._activo.is_set():
            try:
                orden = self._cola.get(timeout=0.2)
            except queue.Empty:
                continue
            if not self._abierto:
                continue
            try:
                self._escribir_linea(orden)
            except Exception as error:
                self._al_perder_canal(str(error))
                continue
            for escucha in list(self._escuchas):
                escucha.al_enviar(orden)

    def _bucle_vigilante(self) -> None:
        """Manda PING de vez en cuando y reabre el canal si se cayo."""
        while self._activo.is_set():
            time.sleep(SEGUNDOS_LATIDO)
            if not self._activo.is_set():
                break
            if self.conectado:
                try:
                    self.enviar(CMD_PING)
                except ArduinoNoDisponible:
                    pass
            elif self._reconectar:
                self._intentar_reconectar()

    def _intentar_reconectar(self) -> None:
        if self._destino not in self._destinos_del_transporte():
            return
        try:
            with self._cerrojo:
                self._abrir(self._destino)
                self._abierto = True
        except ArduinoNoDisponible:
            time.sleep(SEGUNDOS_REINTENTO)
            return
        self._avisar_conexion(True, f"{self._destino} reconectado")

    # --- Cierre ------------------------------------------------------------
    def _cerrar_canal(self) -> None:
        with self._cerrojo:
            if not self._abierto:
                return
            self._abierto = False
            try:
                self._cerrar()
            except Exception:
                pass

    def _al_perder_canal(self, detalle: str) -> None:
        """El cable se desconecto, la placa se reinicio o se cayo la red."""
        if not self._abierto:
            return
        self._cerrar_canal()
        for escucha in list(self._escuchas):
            escucha.al_recibir(f"ERR:se perdió la conexión ({detalle})")
        self._avisar_conexion(False, f"se perdió la conexión con {self._destino}")

    def _avisar_conexion(self, conectado: bool, detalle: str) -> None:
        for escucha in list(self._escuchas):
            escucha.al_cambiar_conexion(conectado, detalle)
