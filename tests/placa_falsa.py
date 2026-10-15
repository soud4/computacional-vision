"""Una placa de mentira que habla el protocolo de verdad.

No es un doble de pruebas que finge: es un servidor TCP real, en un hilo, que
implementa ``docs/protocolo.md``. El adaptador que se prueba contra el abre un
socket, escribe bytes y los lee, exactamente igual que haria contra un ESP32.
"""

from __future__ import annotations

import socket
import threading

from vision_contador.ports.enlace_arduino import (
    CMD_ID,
    MSG_BTN,
    MSG_OK,
    MSG_READY,
    PREFIJO_ID,
)


class PlacaFalsaTcp:
    """Servidor TCP de un solo cliente que responde como el firmware."""

    def __init__(self, identidad: str = "ESP32", saludar: bool = True) -> None:
        self.identidad = identidad
        self.saludar = saludar
        self.recibidas: list[str] = []
        self._recibida = threading.Event()

        self._servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._servidor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._servidor.bind(("127.0.0.1", 0))
        self._servidor.listen(1)
        self._servidor.settimeout(0.3)

        self._cliente: socket.socket | None = None
        self._activo = threading.Event()
        self._activo.set()
        self._hilo = threading.Thread(target=self._atender, daemon=True)
        self._hilo.start()

    @property
    def destino(self) -> str:
        anfitrion, puerto = self._servidor.getsockname()
        return f"tcp://{anfitrion}:{puerto}"

    def _atender(self) -> None:
        while self._activo.is_set():
            try:
                cliente, _ = self._servidor.accept()
            except (TimeoutError, OSError):
                continue
            self._cliente = cliente
            cliente.settimeout(0.3)
            if self.saludar:
                self._responder(MSG_READY)
            self._leer_del_cliente(cliente)

    def _leer_del_cliente(self, cliente: socket.socket) -> None:
        resto = b""
        while self._activo.is_set():
            try:
                trozo = cliente.recv(1024)
            except (TimeoutError, OSError):
                continue
            if not trozo:
                break
            resto += trozo
            while b"\n" in resto:
                linea, _, resto = resto.partition(b"\n")
                self._procesar(linea.decode().strip())
        self._cliente = None

    def _procesar(self, orden: str) -> None:
        if not orden:
            return
        self.recibidas.append(orden)
        self._recibida.set()
        self._responder(f"{PREFIJO_ID}{self.identidad}" if orden == CMD_ID else MSG_OK)

    def _responder(self, linea: str) -> None:
        if self._cliente is None:
            return
        try:
            self._cliente.sendall(f"{linea}\n".encode())
        except OSError:
            pass

    # --- Utilidades para las pruebas --------------------------------------
    def pulsar_boton(self) -> None:
        """La placa avisa por su cuenta, sin que nadie se lo pida."""
        self._responder(MSG_BTN)

    def esperar_orden(self, orden: str, segundos: float = 3.0) -> bool:
        """Espera a que llegue una orden concreta."""
        limite = threading.Event()
        timer = threading.Timer(segundos, limite.set)
        timer.daemon = True
        timer.start()
        try:
            while not limite.is_set():
                if orden in self.recibidas:
                    return True
                self._recibida.wait(0.05)
                self._recibida.clear()
            return orden in self.recibidas
        finally:
            timer.cancel()

    def cortar(self) -> None:
        """Corta la conexión de golpe, como un cable arrancado."""
        if self._cliente is not None:
            try:
                self._cliente.close()
            except OSError:
                pass
            self._cliente = None

    def cerrar(self) -> None:
        self._activo.clear()
        self.cortar()
        try:
            self._servidor.close()
        except OSError:
            pass
        self._hilo.join(timeout=2)


class EscuchaDePrueba:
    """Registra todo lo que el enlace reporta."""

    def __init__(self) -> None:
        self.recibidas: list[str] = []
        self.enviadas: list[str] = []
        self.conexiones: list[tuple[bool, str]] = []
        self.pulsaciones = 0

    def al_recibir(self, linea: str) -> None:
        self.recibidas.append(linea)

    def al_enviar(self, linea: str) -> None:
        self.enviadas.append(linea)

    def al_cambiar_conexion(self, conectado: bool, detalle: str) -> None:
        self.conexiones.append((conectado, detalle))

    def al_pulsar_boton(self) -> None:
        self.pulsaciones += 1
