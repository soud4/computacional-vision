"""Ventana principal: ensambla las cuatro zonas y gobierna la maquina de estados."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QMainWindow,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..adapters.fuente_imagen import FuenteImagen
from ..core.config import Config, guardar_camara, guardar_preprocesamiento
from ..core.modelos import (
    Direccion,
    EstadoApp,
    EtapaPreproc,
    Imagen,
    Led,
    ParametrosPreproc,
    Rect,
    ResultadoCaptura,
)
from ..core.pipeline import Dependencias, Pipeline
from ..ports.enlace_arduino import ArduinoNoDisponible, cmd_lcd, cmd_led
from . import iconos, imagen_qt, tema
from .espejo import EspejoHardware
from .hilos import HiloCamara, HiloCaptura, HiloCargaModelo, HiloProbarFuente, PuenteArduino
from .paneles.tab_arduino import TabArduino
from .paneles.tab_fuente import TabFuente
from .paneles.tab_preprocesamiento import TabPreprocesamiento
from .paneles.tab_resultados import TabResultados
from .widgets.barra_superior import BarraSuperior
from .widgets.consola_serial import ConsolaSerial
from .widgets.franja_aviso import FranjaAviso
from .widgets.panel import Panel, etiqueta_sec
from .widgets.visor_imagen import VisorImagen

AVISO_SIN_ARDUINO = (
    "No se encontró el Arduino en {puerto}. Puede seguir capturando con el botón Capturar"
)

AVISO_SIN_PUERTOS = (
    "No se encontró ningún puerto serie. Conecte el Arduino por USB y pulse Reintentar. "
    "Mientras tanto puede seguir capturando con el botón Capturar"
)

#: Extensiones que Qt sabe decodificar y que tiene sentido ofrecer.
FILTRO_IMAGENES = "Imágenes (*.png *.jpg *.jpeg *.bmp *.webp);;Todos los archivos (*)"

#: Las mismas extensiones, para decidir si lo que se arrastra sobre la ventana
#: es una imagen que se pueda abrir.
EXTENSIONES_IMAGEN = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}


class VentanaPrincipal(QMainWindow):
    """La pantalla unica de la aplicacion."""

    def __init__(self, config: Config, deps: Dependencias, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.config = config
        self.deps = deps
        self.pipeline = Pipeline(deps)
        self.params = config.preproc

        self._estado = EstadoApp.LISTO
        self._resultado: ResultadoCaptura | None = None
        self._captura: HiloCaptura | None = None
        self._ultimo_cuadro: Imagen | None = None
        self._fps = 0.0
        #: True mientras la fuente activa es una imagen de archivo y no una camara.
        self._fuente_archivo = False
        self._prueba: HiloProbarFuente | None = None
        self.espejo = EspejoHardware()

        self.setWindowTitle("Visión Contador")
        self.resize(*tema.VENTANA)
        self.setMinimumSize(QSize(1180, 740))
        self.setWindowIcon(iconos.obturador(32, tema.TEXTO))
        # Arrastrar una imagen a la ventana es la via corta de "Subir imagen...".
        self.setAcceptDrops(True)

        self._construir()
        self._conectar()
        self._iniciar_servicios()
        self._aplicar_estado(EstadoApp.LISTO)

    # --- Construccion ------------------------------------------------------
    def _construir(self) -> None:
        central = QWidget(self)
        raiz = QVBoxLayout(central)
        raiz.setContentsMargins(tema.MARGEN, tema.MARGEN, tema.MARGEN, tema.MARGEN)
        raiz.setSpacing(tema.SEPARACION)

        self.barra = BarraSuperior(central)
        self.aviso = FranjaAviso(central)
        raiz.addWidget(self.barra)
        raiz.addWidget(self.aviso)

        medio = QHBoxLayout()
        medio.setSpacing(tema.SEPARACION)
        medio.addWidget(self._construir_cuadricula(central), 1)
        medio.addWidget(self._construir_columna_derecha(central), 0)
        raiz.addLayout(medio, 1)

        self.consola = ConsolaSerial(central)
        self.consola.setFixedHeight(tema.ALTO_CONSOLA)
        raiz.addWidget(self.consola)

        self.setCentralWidget(central)

    def _construir_cuadricula(self, parent: QWidget) -> QWidget:
        contenedor = QWidget(parent)
        rejilla = QGridLayout(contenedor)
        rejilla.setContentsMargins(0, 0, 0, 0)
        rejilla.setSpacing(tema.SEPARACION)

        self.visor_vivo = VisorImagen()
        self.visor_captura = VisorImagen()
        self.visor_preproc = VisorImagen()
        self.visor_deteccion = VisorImagen()

        self.selector_etapa = QComboBox()
        for etapa in EtapaPreproc:
            self.selector_etapa.addItem(etapa.etiqueta, etapa)
        self.selector_etapa.setCurrentText(EtapaPreproc.RESULTADO.etiqueta)

        paneles = (
            # "FUENTE" y no "VIDEO EN VIVO" porque el mismo panel muestra tanto
            # la camara como la imagen subida.
            (Panel("FUENTE", margenes=(1, 1, 1, 1)), self.visor_vivo, 0, 0),
            (Panel("CAPTURA", margenes=(1, 1, 1, 1)), self.visor_captura, 0, 1),
            (
                Panel(
                    "PREPROCESADA",
                    acciones=[etiqueta_sec("Etapa:", 11), self.selector_etapa],
                    margenes=(1, 1, 1, 1),
                ),
                self.visor_preproc,
                1,
                0,
            ),
            (Panel("DETECCIÓN", margenes=(1, 1, 1, 1)), self.visor_deteccion, 1, 1),
        )
        for panel, visor, fila, columna in paneles:
            panel.setParent(contenedor)
            panel.cuerpo.addWidget(visor)
            rejilla.addWidget(panel, fila, columna)

        for i in range(2):
            rejilla.setRowStretch(i, 1)
            rejilla.setColumnStretch(i, 1)

        self.visor_vivo.fijar_marcador("Sin fuente de video")
        self.visor_captura.fijar_marcador("Sin captura")
        self.visor_preproc.fijar_marcador("Sin captura")
        self.visor_deteccion.fijar_marcador("Sin captura")
        return contenedor

    def _construir_columna_derecha(self, parent: QWidget) -> QWidget:
        self.pestanas = QTabWidget(parent)
        self.pestanas.setFixedWidth(tema.ANCHO_COLUMNA_DERECHA)

        self.tab_resultados = TabResultados()
        self.tab_preproc = TabPreprocesamiento(self.params)
        self.tab_fuente = TabFuente()
        self.tab_arduino = TabArduino()

        for widget, titulo in (
            (self.tab_resultados, "Resultados"),
            (self.tab_preproc, "Preprocesamiento"),
            (self.tab_fuente, "Fuente"),
            (self.tab_arduino, "Arduino"),
        ):
            widget.setObjectName("ContenidoPestana")
            desplazable = QScrollArea(self.pestanas)
            desplazable.setWidget(widget)
            desplazable.setWidgetResizable(True)
            desplazable.setFrameShape(QScrollArea.Shape.NoFrame)
            # La columna tiene ancho fijo: lo que no quepa se envuelve, no se
            # desplaza de lado.
            desplazable.setHorizontalScrollBarPolicy(
                Qt.ScrollBarPolicy.ScrollBarAlwaysOff
            )
            self.pestanas.addTab(desplazable, titulo)

        return self.pestanas

    # --- Cableado ----------------------------------------------------------
    def _conectar(self) -> None:
        self.barra.capturar.connect(self.capturar)
        self.barra.subir_imagen.connect(self.subir_imagen)
        self.barra.volver_camara.connect(self.volver_camara)
        self.aviso.accion_pulsada.connect(self.conectar_arduino)
        self.selector_etapa.currentIndexChanged.connect(self._mostrar_etapa)

        self.tab_resultados.reproducir.connect(self._reproducir_frase)

        self.tab_preproc.parametros_cambiados.connect(self._al_cambiar_parametros)
        self.tab_preproc.restablecer.connect(self._restablecer_parametros)
        self.tab_preproc.guardar.connect(self._guardar_parametros)
        self.tab_preproc.definir_roi.connect(self._definir_roi)

        self.tab_fuente.buscar.connect(self.refrescar_dispositivos)
        self.tab_fuente.probar.connect(self._probar_fuente)
        self.tab_fuente.usar.connect(self.usar_camara)
        self.tab_fuente.abrir_imagen.connect(self.subir_imagen)

        self.tab_arduino.conectar.connect(self.conectar_arduino)
        self.tab_arduino.desconectar.connect(self.desconectar_arduino)
        self.tab_arduino.buscar_puertos.connect(self.refrescar_puertos)
        self.tab_arduino.enviar_lcd.connect(self._enviar_lcd)
        self.tab_arduino.led_cambiado.connect(self._cambiar_led)
        self.tab_arduino.apagar_leds.connect(lambda: self._enviar(cmd_led(None)))

        self.consola.conectar_pulsado.connect(self.conectar_arduino)
        self.consola.desconectar_pulsado.connect(self.desconectar_arduino)
        self.consola.enviar_pulsado.connect(self._enviar)

        self.puente = PuenteArduino(self)
        self.puente.linea.connect(self._al_llegar_linea)
        self.puente.conexion_cambiada.connect(self._al_cambiar_conexion)
        self.puente.boton_pulsado.connect(self._al_pulsar_boton_fisico)
        self.deps.arduino.suscribir(self.puente)

        # Atajos para la presentacion en aula.
        for tecla, accion in (
            ("Space", self.capturar),
            ("Ctrl+O", self.subir_imagen),
            ("F1", lambda: self.forzar_estado("listo")),
            ("F2", lambda: self.forzar_estado("pensando")),
            ("F3", lambda: self.forzar_estado("sin_arduino")),
            ("F4", lambda: self.forzar_estado("sin_deteccion")),
        ):
            QShortcut(QKeySequence(tecla), self, activated=accion)

    def _iniciar_servicios(self) -> None:
        self.tab_preproc.fijar_estados(None)
        self.barra.fijar_arduino(False)
        self.tab_arduino.fijar_conectado(False)
        self._refrescar_estado_arduino()
        self._precargar_modelo()

        self.hilo_camara: HiloCamara | None = None
        try:
            self.deps.camara.abrir()
            disponible = self.deps.camara.disponible
        except Exception as error:
            disponible = False
            self.consola.registrar(Direccion.ERROR, f"Cámara: {error}")

        self.barra.fijar_camara(disponible, self._nombre_fuente() if disponible else "")
        if disponible:
            self._arrancar_hilo_camara()

        self.visor_vivo.fijar_roi(self.params.roi)
        self.refrescar_puertos()
        self.refrescar_dispositivos()
        self._preparar_pestana_fuente()
        # Se intenta conectar al arrancar; si no hay Arduino, la franja de aviso
        # lo dice y la aplicacion sigue funcionando igual.
        QTimer.singleShot(120, self.conectar_arduino)

    def _precargar_modelo(self) -> None:
        """Carga los pesos en segundo plano, con la ventana ya visible."""
        detector = self.deps.detector
        if detector.listo:
            self.barra.fijar_modelo(detector.nombre, True)
            return

        self.barra.fijar_modelo(f"{detector.nombre} (cargando…)", False)
        self.consola.registrar(Direccion.INFO, f"Cargando el modelo {detector.nombre}…")

        self.hilo_modelo = HiloCargaModelo(detector, self)
        self.hilo_modelo.listo.connect(self._al_cargar_modelo)
        self.hilo_modelo.fallo.connect(self._al_fallar_modelo)
        self.hilo_modelo.start()

    def _al_cargar_modelo(self, nombre: str) -> None:
        self.barra.fijar_modelo(nombre, True)
        self.consola.registrar(Direccion.INFO, f"Modelo {nombre} listo")

    def _al_fallar_modelo(self, mensaje: str) -> None:
        self.barra.fijar_modelo("no disponible", False)
        self.consola.registrar(Direccion.ERROR, f"Modelo: {mensaje}")
        self.aviso.mostrar(
            f"No se pudo cargar el modelo de detección: {mensaje}", accion=""
        )

    # --- Camara ------------------------------------------------------------
    def _al_llegar_cuadro(self, cuadro: Imagen) -> None:
        self._ultimo_cuadro = cuadro
        self.visor_vivo.fijar_imagen(cuadro)

    def _al_medir_fps(self, fps: float) -> None:
        self._fps = fps
        if not self._fuente_archivo:
            self.visor_vivo.fijar_en_vivo(True, fps)

    def _arrancar_hilo_camara(self) -> None:
        """Pone en marcha el hilo de video, si no lo estaba ya.

        Se llama tambien al elegir una camara desde la pestana Fuente: si la
        aplicacion arranco sin camara, el hilo todavia no existe.
        """
        if self.hilo_camara is not None:
            self.hilo_camara.pausado = False
            self.visor_vivo.fijar_en_vivo(True, self._fps or self.config.camara.fps)
            return

        self.hilo_camara = HiloCamara(self.deps.camara, self.config.camara.fps, self)
        self.hilo_camara.cuadro_listo.connect(self._al_llegar_cuadro)
        self.hilo_camara.fps_medidos.connect(self._al_medir_fps)
        self.hilo_camara.fallo.connect(
            lambda e: self.consola.registrar(Direccion.ERROR, f"Cámara: {e}")
        )
        self.hilo_camara.start()
        self.visor_vivo.fijar_en_vivo(True, self.config.camara.fps)

    def _nombre_fuente(self) -> str:
        """Como se llama la fuente activa, para el chip de la barra superior."""
        activa = self.deps.camara.activa
        if isinstance(activa, FuenteImagen):
            return activa.nombre
        destino = getattr(activa, "destino", None)
        if destino is not None:
            return str(destino)
        return "escena simulada" if self.config.es_demo else "cámara"

    # --- Seleccion de la fuente --------------------------------------------
    def refrescar_dispositivos(self) -> None:
        """Vuelca en la pestana Fuente las camaras que ve el sistema."""
        try:
            from ..adapters.camara_opencv import dispositivos
        except ImportError:
            # Sin OpenCV no hay forma de enumerar ni de abrir camaras; la
            # pestana se queda solo con la imagen de archivo.
            self.tab_fuente.entrada.deshabilitar_camaras()
            return

        encontrados = dispositivos()
        self.tab_fuente.entrada.fijar_dispositivos(
            encontrados, str(self.config.camara.indice)
        )
        if not encontrados:
            self.tab_fuente.entrada.fijar_mensaje("No se encontró ninguna cámara conectada")

    def _preparar_pestana_fuente(self) -> None:
        """Deja la pestana mostrando la fuente con la que se arranco."""
        entrada = self.tab_fuente.entrada
        entrada.url.setText(self.config.camara.url)
        if self.config.camara.fuente == "red" and self.config.camara.url:
            entrada.opcion_red.setChecked(True)

    def _probar_fuente(self, destino: str) -> None:
        if not destino:
            self.tab_fuente.entrada.fijar_mensaje(
                "Elija una cámara o escriba la dirección del teléfono", error=True
            )
            return
        self.tab_fuente.entrada.fijar_probando(True)
        self.tab_fuente.entrada.fijar_mensaje(f"Probando {destino}…")
        self._prueba = HiloProbarFuente(destino, self)
        self._prueba.terminado.connect(self._al_probar_fuente)
        self._prueba.start()

    def _al_probar_fuente(self, ok: bool, resumen: str) -> None:
        self.tab_fuente.entrada.fijar_probando(False)
        self.tab_fuente.entrada.fijar_mensaje(resumen, error=not ok)
        self.consola.registrar(
            Direccion.INFO if ok else Direccion.ERROR, f"Prueba de fuente: {resumen}"
        )

    def usar_camara(self, destino: str) -> None:
        """Cambia la fuente activa a la camara indicada, local o de red."""
        if not destino:
            self.tab_fuente.entrada.fijar_mensaje(
                "Elija una cámara o escriba la dirección del teléfono", error=True
            )
            return

        try:
            from ..adapters.camara_opencv import CamaraOpenCV, es_url, normalizar
        except ImportError:
            self.tab_fuente.entrada.deshabilitar_camaras()
            return

        try:
            self.deps.camara.cambiar(CamaraOpenCV(self.config.camara, destino))
        except Exception as error:
            # La fuente anterior sigue en pie: ``cambiar`` solo descarta la vieja
            # cuando la nueva ha abierto bien.
            self.tab_fuente.entrada.fijar_mensaje(str(error), error=True)
            self.consola.registrar(Direccion.ERROR, f"Fuente: {error}")
            return

        es_red = es_url(destino)
        self.config.camara.fuente = "red" if es_red else "local"
        if es_red:
            self.config.camara.url = destino
        else:
            self.config.camara.indice = normalizar(destino)
        guardar_camara(self.config.camara)

        self._fuente_archivo = False
        self.barra.fijar_fuente_archivo(False)
        self.barra.fijar_camara(True, str(destino))
        self.visor_vivo.fijar_esquina("")
        self.visor_vivo.fijar_marcador("Sin fuente de video")
        self._fps = 0.0
        self._arrancar_hilo_camara()
        self.tab_fuente.entrada.fijar_mensaje(f"Fuente activa: {destino}")
        self.consola.registrar(Direccion.INFO, f"Fuente de video: {destino}")

    def subir_imagen(self) -> None:
        """Abre una imagen del disco, la deja como fuente y la procesa."""
        ruta, _ = QFileDialog.getOpenFileName(
            self, "Subir imagen", str(self.config.ruta_registro), FILTRO_IMAGENES
        )
        if not ruta:
            return
        self.usar_imagen(ruta)

    def usar_imagen(self, ruta: str) -> None:
        nombre = Path(ruta).name
        try:
            imagen = imagen_qt.desde_archivo(ruta)
        except Exception as error:
            self.consola.registrar(Direccion.ERROR, f"Imagen: {error}")
            self.aviso.mostrar(f"No se pudo abrir «{nombre}»: {error}", accion="")
            return

        fuente = FuenteImagen(imagen, nombre)
        try:
            self.deps.camara.cambiar(fuente)
        except Exception as error:
            self.consola.registrar(Direccion.ERROR, f"Imagen: {error}")
            return

        # La imagen no se guarda en la configuracion: la fuente recordada sigue
        # siendo la camara, para que la proxima sesion arranque con video.
        self._fuente_archivo = True

        ancho, alto = fuente.tamano
        self._reescalar_roi(ancho, alto)
        # El hilo de video puede no existir -si se arranco sin camara- asi que la
        # imagen se pinta aqui mismo en lugar de esperar a que alguien la lea.
        self._ultimo_cuadro = imagen
        self.visor_vivo.fijar_en_vivo(False)
        self.visor_vivo.fijar_imagen(imagen)
        self.visor_vivo.fijar_esquina(nombre)
        self.visor_vivo.fijar_roi(self.params.roi, referencia=(ancho, alto))

        self.barra.fijar_camara(True, nombre)
        self.barra.fijar_fuente_archivo(True)
        self.tab_fuente.entrada.opcion_archivo.setChecked(True)
        self.tab_fuente.entrada.fijar_archivo(ruta)
        self.tab_fuente.entrada.fijar_mensaje(f"{nombre} · {ancho} x {alto}")
        self.aviso.ocultar()
        self.consola.registrar(Direccion.INFO, f"Imagen cargada: {nombre} ({ancho} x {alto})")

        self.capturar()

    def volver_camara(self) -> None:
        """Deshace la subida de imagen y vuelve a la fuente de siempre."""
        if not self._fuente_archivo:
            return
        try:
            self.deps.camara.cambiar(self.deps.camara.original)
        except Exception as error:
            self.consola.registrar(Direccion.ERROR, f"Cámara: {error}")
            self.aviso.mostrar(f"No se pudo volver a la cámara: {error}")
            return

        self._fuente_archivo = False
        self.barra.fijar_fuente_archivo(False)
        self.barra.fijar_camara(True, self._nombre_fuente())
        self.visor_vivo.fijar_esquina("")
        self.visor_vivo.fijar_roi(self.params.roi)
        self._fps = 0.0
        self._arrancar_hilo_camara()
        self.tab_fuente.entrada.opcion_local.setChecked(
            self.config.camara.fuente == "local"
        )
        self.consola.registrar(Direccion.INFO, "Fuente de video: cámara")

    def _reescalar_roi(self, ancho: int, alto: int) -> None:
        """Lleva la region de interes a la escala de la imagen nueva.

        La region se guarda en pixeles de la camara (1280x720 por defecto); con
        una imagen de otro tamano, dejarla tal cual la pondria fuera de sitio o
        directamente fuera de la imagen.
        """
        base_ancho, base_alto = self.config.camara.ancho, self.config.camara.alto
        if (ancho, alto) == (base_ancho, base_alto) or not base_ancho or not base_alto:
            return
        ex, ey = ancho / base_ancho, alto / base_alto
        roi = self.params.roi
        self.params.roi = Rect(
            round(roi.x * ex), round(roi.y * ey), round(roi.ancho * ex), round(roi.alto * ey)
        )
        self.tab_preproc.fijar_roi(self.params.roi)

    # --- Arrastrar y soltar ------------------------------------------------
    def dragEnterEvent(self, evento) -> None:
        """Arrastrar una imagen sobre la ventana equivale a subirla."""
        if self._ruta_arrastrada(evento) is not None:
            evento.acceptProposedAction()

    def dropEvent(self, evento) -> None:
        ruta = self._ruta_arrastrada(evento)
        if ruta is not None:
            evento.acceptProposedAction()
            self.usar_imagen(ruta)

    @staticmethod
    def _ruta_arrastrada(evento) -> str | None:
        datos = evento.mimeData()
        if not datos.hasUrls():
            return None
        for url in datos.urls():
            if not url.isLocalFile():
                continue
            ruta = url.toLocalFile()
            if Path(ruta).suffix.lower() in EXTENSIONES_IMAGEN:
                return ruta
        return None

    # --- Arduino -----------------------------------------------------------
    def refrescar_puertos(self) -> None:
        puertos = self.deps.arduino.puertos_disponibles()
        actual = self.config.arduino.puerto or (puertos[0] if puertos else "")
        self.consola.fijar_puertos(puertos, actual)
        self.tab_arduino.conexion.fijar_puertos(puertos, actual)
        if not puertos:
            self.consola.registrar(Direccion.INFO, "No se encontraron puertos serie")

    def conectar_arduino(self) -> None:
        puerto = self.tab_arduino.conexion.puerto or self.consola.puerto
        baudios = self.tab_arduino.conexion.velocidad
        if not puerto or puerto.startswith("("):
            # No hay ningún puerto que ofrecer: el mensaje tiene que decir qué
            # hacer, no repetir un nombre de puerto inventado.
            self.aviso.mostrar(AVISO_SIN_PUERTOS)
            return
        try:
            self.deps.arduino.conectar(puerto, baudios)
        except ArduinoNoDisponible as error:
            self.consola.registrar(Direccion.ERROR, f"Error: {error}")
            self._mostrar_aviso_arduino(puerto)

    def desconectar_arduino(self) -> None:
        self.deps.arduino.desconectar()

    def _mostrar_aviso_arduino(self, puerto: str) -> None:
        self.aviso.mostrar(AVISO_SIN_ARDUINO.format(puerto=puerto))

    def _al_cambiar_conexion(self, conectado: bool, detalle: str) -> None:
        # ``conectadas`` solo existe en el enlace compuesto; con una sola placa
        # el valor por defecto deja el indicador como siempre.
        placas = getattr(self.deps.arduino, "conectadas", 1)
        self.barra.fijar_arduino(conectado, self.deps.arduino.puerto_actual, placas)
        self.consola.fijar_conectado(conectado)
        self.tab_arduino.fijar_conectado(conectado, detalle)
        self.consola.registrar(
            Direccion.INFO if conectado else Direccion.ERROR,
            f"{'Conectado' if conectado else 'Desconectado'}: {detalle}",
        )
        if conectado:
            self.aviso.ocultar()
        else:
            self.espejo.reiniciar()
        self._refrescar_estado_arduino()

    def _al_llegar_linea(self, direccion: Direccion, texto: str) -> None:
        self.consola.registrar(direccion, texto)
        if direccion is Direccion.ENVIADO:
            self.espejo.al_enviar(texto)
        self._refrescar_estado_arduino()

    def _al_pulsar_boton_fisico(self) -> None:
        self.espejo.anotar_pulsacion()
        self._refrescar_estado_arduino()
        self.capturar()

    def _enviar(self, orden: str) -> None:
        try:
            self.deps.arduino.enviar(orden)
        except ArduinoNoDisponible as error:
            self.consola.registrar(Direccion.ERROR, f"Error: {error}")

    def _enviar_lcd(self, fila1: str, fila2: str) -> None:
        self._enviar(cmd_lcd(1, fila1))
        self._enviar(cmd_lcd(2, fila2))

    def _cambiar_led(self, led: Led, encendido: bool) -> None:
        # El protocolo enciende un LED a la vez, como el hardware: apagar el que
        # esta encendido equivale a no encender ninguno.
        self._enviar(cmd_led(led if encendido else None))

    def _refrescar_estado_arduino(self) -> None:
        """Vuelca el espejo del hardware en las dos tarjetas que lo muestran."""
        self.tab_arduino.lcd.mostrar(*self.espejo.lcd)
        self.tab_arduino.leds.mostrar(self.espejo.leds)
        self.tab_resultados.leds.mostrar(self.espejo.leds)
        self.tab_arduino.pulsador.mostrar(
            self.espejo.ultima_pulsacion, self.espejo.pulsaciones
        )

    # --- Captura -----------------------------------------------------------
    def capturar(self) -> None:
        if self._estado is EstadoApp.PENSANDO:
            return
        self.params = self.tab_preproc.leer()
        self.params.roi = self.tab_preproc._params.roi

        # El panel DETECCION muestra el ultimo cuadro atenuado bajo la barra de
        # progreso, en lugar de quedarse en blanco mientras corre el modelo.
        if self._ultimo_cuadro is not None:
            self.visor_deteccion.fijar_imagen(self._ultimo_cuadro)
            self.visor_deteccion.fijar_detecciones([])
            self.visor_deteccion.fijar_insignias([])
            self.visor_deteccion.fijar_atenuacion(0.45)

        self._aplicar_estado(EstadoApp.PENSANDO)
        if self.hilo_camara is not None:
            self.hilo_camara.pausado = True

        self._captura = HiloCaptura(self.pipeline, self.params, self)
        self._captura.progreso.connect(self._al_progresar)
        self._captura.terminado.connect(self._al_terminar)
        self._captura.fallo.connect(self._al_fallar)
        self._captura.start()

    def _al_progresar(self, indice: int, texto: str) -> None:
        # El paso en curso se lee sobre el panel DETECCION; repetirlo en la
        # barra superior solo alargaba la pildora a cada paso.
        self.visor_deteccion.fijar_ocupado(True, texto)

    def _al_terminar(self, resultado: ResultadoCaptura) -> None:
        self._resultado = resultado
        if self.hilo_camara is not None:
            self.hilo_camara.pausado = False

        ancho, alto = resultado.resolucion
        self.visor_captura.fijar_imagen(resultado.capturada)
        self.visor_captura.fijar_esquina(resultado.hora)
        self.visor_captura.fijar_pie(f"Resolución {ancho} x {alto}")

        self._mostrar_etapa()
        self.visor_preproc.fijar_roi(self.params.roi, referencia=(ancho, alto))

        self.visor_deteccion.fijar_ocupado(False)
        self.visor_deteccion.fijar_atenuacion(0.0)
        self.visor_deteccion.fijar_imagen(resultado.preprocesada)
        self.visor_deteccion.fijar_detecciones(resultado.detecciones)
        sustantivo = "objeto" if resultado.total == 1 else "objetos"
        self.visor_deteccion.fijar_insignias(
            [
                (f"{resultado.total} {sustantivo}", tema.OK if resultado.total else tema.ERROR),
                (f"Inferencia: {resultado.ms_inferencia} ms", tema.TEXTO_SEC),
            ]
        )

        self.tab_resultados.mostrar(resultado, self.deps.voz.descripcion)
        self.tab_preproc.fijar_estados(resultado.etapas_aplicadas)
        if not self.deps.arduino.conectado:
            # Sin Arduino el pipeline no envió ninguna orden, así que el espejo
            # se quedaría con el amarillo de "Pensando". Se fija aquí el LED que
            # se habría encendido: la tarjeta muestra la conclusión del sistema.
            self.espejo.encender(Led.VERDE if resultado.conteos else Led.ROJO)
        self._refrescar_estado_arduino()

        self._aplicar_estado(
            EstadoApp.MOSTRANDO if resultado.conteos else EstadoApp.SIN_DETECCION
        )

    def _al_fallar(self, mensaje: str) -> None:
        if self.hilo_camara is not None:
            self.hilo_camara.pausado = False
        if not self.deps.arduino.conectado:
            self.espejo.encender(Led.ROJO)
            self._refrescar_estado_arduino()
        self.visor_deteccion.fijar_ocupado(False)
        self.consola.registrar(Direccion.ERROR, f"Error: {mensaje}")
        self._aplicar_estado(EstadoApp.ERROR, f"Error: {mensaje}")

    def _mostrar_etapa(self) -> None:
        """Pinta en el panel PREPROCESADA la etapa elegida en el desplegable."""
        if self._resultado is None:
            return
        etapa = self.selector_etapa.currentData()
        imagen = self._resultado.etapas.get(etapa)
        if imagen is not None:
            self.visor_preproc.fijar_imagen(imagen)

    def _reproducir_frase(self) -> None:
        if self._resultado is not None:
            self.deps.voz.decir(self._resultado.frase)
            self.consola.registrar(Direccion.INFO, f"Voz: «{self._resultado.frase}»")

    # --- Parametros --------------------------------------------------------
    def _al_cambiar_parametros(self) -> None:
        self.params = self.tab_preproc.leer()
        self.visor_vivo.fijar_roi(self.params.roi)

    def _restablecer_parametros(self) -> None:
        self.tab_preproc.escribir(ParametrosPreproc())
        self.consola.registrar(Direccion.INFO, "Parámetros restablecidos")

    def _guardar_parametros(self) -> None:
        guardar_preprocesamiento(self.tab_preproc.leer())
        self.consola.registrar(Direccion.INFO, "Configuración guardada en config/usuario.toml")

    def _definir_roi(self) -> None:
        self.consola.registrar(
            Direccion.INFO,
            "Definir región: pendiente de implementar la selección sobre el video",
        )

    # --- Maquina de estados ------------------------------------------------
    def _aplicar_estado(self, estado: EstadoApp, texto: str | None = None) -> None:
        """Un unico sitio decide como se ve la aplicacion en cada estado."""
        self._estado = estado
        self.barra.fijar_estado(estado, texto)
        self.barra.habilitar_captura(estado is not EstadoApp.PENSANDO)

        if estado is EstadoApp.PENSANDO:
            self.tab_resultados.mostrar_carga()
            self.visor_deteccion.fijar_ocupado(True, "Ejecutando YOLO…")
            self.espejo.encender(Led.AMARILLO)
            self.tab_resultados.leds.mostrar(self.espejo.leds)
        else:
            self.visor_deteccion.fijar_ocupado(False)

    def forzar_estado(self, nombre: str) -> None:
        """Atajos de la demostracion para mostrar cada variante del diseno."""
        if nombre == "listo":
            self.aviso.ocultar()
            self._aplicar_estado(EstadoApp.LISTO)
        elif nombre == "pensando":
            self._aplicar_estado(EstadoApp.PENSANDO)
        elif nombre == "sin_arduino":
            self.desconectar_arduino()
            self._mostrar_aviso_arduino(self.deps.arduino.puerto_actual or "COM3")
            self.consola.registrar(
                Direccion.ERROR,
                f"Error: puerto {self.deps.arduino.puerto_actual or 'COM3'} no disponible",
            )
        elif nombre == "sin_deteccion":
            detector = self.deps.detector
            if hasattr(detector, "sin_detecciones"):
                detector.sin_detecciones = not detector.sin_detecciones
                self.consola.registrar(
                    Direccion.INFO,
                    f"Detector simulado: sin_detecciones = {detector.sin_detecciones}",
                )

    # --- Cierre ------------------------------------------------------------
    def closeEvent(self, evento) -> None:
        if self.hilo_camara is not None:
            self.hilo_camara.detener()
        if self._captura is not None and self._captura.isRunning():
            self._captura.wait(2000)
        if self._prueba is not None and self._prueba.isRunning():
            self._prueba.wait(5000)
        hilo_modelo = getattr(self, "hilo_modelo", None)
        if hilo_modelo is not None and hilo_modelo.isRunning():
            hilo_modelo.wait(5000)
        self.deps.camara.cerrar()
        self.deps.arduino.desconectar()
        super().closeEvent(evento)
