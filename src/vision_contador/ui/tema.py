"""Tokens de diseno y hoja de estilos de la aplicacion.

Todo color, tamano o grosor que aparezca en la interfaz sale de aqui: si hay que
retocar la paleta se retoca en un solo archivo.

El sistema es una escala de grises sobre grafito, con las proporciones del modo
oscuro de macOS: el fondo no es negro sino un gris muy oscuro, y cada superficie
que se apoya encima sube un escalon. Las jerarquias se construyen con esos
niveles -fondo, panel, cabecera, hundido- y no con marcos: la linea de 1 px se
reserva para las pocas separaciones que de verdad hacen falta.

El redondeo sigue la misma escala: 10 px en paneles y tarjetas, 6 px en botones
y campos, 4 px en las etiquetas pequenas. Nada de pildoras ni circulos.

La unica excepcion al gris es el espejo del hardware: los tres LEDs de la
protoboard y la pantalla LCD conservan su color real, porque ahi el color no
decora, informa de lo que esta encendido sobre la mesa.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase, QPainter, QPen, QPixmap

# --- Paleta -------------------------------------------------------------------
#: Los cuatro niveles de superficie, del mas hundido al mas elevado.
FONDO = "#1C1C1E"
PANEL = "#2C2C2E"
PANEL_CABECERA = "#323234"
BORDE = "#3A3A3C"
#: Lo que se percibe como un hueco en la superficie: el area de la consola, los
#: campos de texto y el fondo de los visores.
HUNDIDO = "#171719"

TEXTO = "#F5F5F7"
TEXTO_SEC = "#9A9AA0"
TEXTO_APAGADO = "#68686E"

#: Fondo de los controles (botones, campos, desplegables). Un nivel por encima
#: del panel; es lo que los hace reconocibles sin necesidad de marco.
CONTROL = "#3A3A3C"
CONTROL_HOVER = "#48484A"
CONTROL_PULSADO = "#545456"

#: La accion primaria se distingue por inversion: fondo claro y tinta oscura.
ACENTO = "#E8E8EA"
ACENTO_HOVER = "#FFFFFF"
ACENTO_PULSADO = "#C8C8CC"
TINTA_INVERSA = "#1C1C1E"

#: Niveles de los tres estados. Al no haber tono que los separe, cada uno lleva
#: ademas su propia forma en ``PildoraEstado``: punto lleno, arco giratorio y
#: aspa.
OK = "#D8D8DC"
PROCESANDO = "#A0A0A6"
ERROR = "#FFFFFF"

#: Colores por severidad de estado, tal como los usa la pildora de la barra superior.
SEVERIDAD = {"ok": OK, "procesando": PROCESANDO, "error": ERROR}

# --- Excepcion: el espejo del hardware fisico ---------------------------------
#: Los LEDs y la LCD replican lo que se ve en la protoboard, asi que mantienen el
#: color del componente real aunque el resto de la interfaz sea neutra.
LED_ROJO = "#EF4444"
LED_AMARILLO = "#F5B700"
LED_VERDE = "#22C55E"

# --- Clases detectadas --------------------------------------------------------
#: Niveles de gris de las cajas de deteccion, en el orden en que se asignan por
#: clase. Seis grises seguidos son dificiles de distinguir, asi que cada nivel
#: viene emparejado con un trazo distinto en ``TRAZOS_CAJA``: la pareja
#: (gris, trazo) es lo que identifica a la clase, en la imagen y en la leyenda.
COLORES_CAJA = ("#FFFFFF", "#BFBFC4", "#86868B", "#E4E4E8", "#A3A3A8", "#6E6E73")
TRAZOS_CAJA = (
    Qt.PenStyle.SolidLine,
    Qt.PenStyle.DashLine,
    Qt.PenStyle.DotLine,
    Qt.PenStyle.DashDotLine,
    Qt.PenStyle.DashDotDotLine,
    Qt.PenStyle.SolidLine,
)

# --- Geometria ----------------------------------------------------------------
#: Escala de redondeo, de la superficie grande al detalle pequeno.
RADIO_PANEL = 10
RADIO = 6
RADIO_CHICO = 4
MARGEN = 12
SEPARACION = 12
ALTO_BARRA_SUPERIOR = 56
ALTO_CONSOLA = 170
ANCHO_COLUMNA_DERECHA = 440
ALTO_CABECERA_PANEL = 30
VENTANA = (1440, 900)

# --- Tipografia ---------------------------------------------------------------
FAMILIAS_UI = (
    "SF Pro Text", "SF Pro Display",   # en un Mac, la del sistema
    "Inter", "Segoe UI", "Noto Sans", "DejaVu Sans", "sans-serif",
)
FAMILIAS_MONO = ("JetBrains Mono", "Consolas", "DejaVu Sans Mono", "monospace")


def _primera_disponible(familias: tuple[str, ...], respaldo: str) -> str:
    instaladas = set(QFontDatabase.families())
    for familia in familias:
        if familia in instaladas:
            return familia
    return respaldo


class Fuentes:
    """Las familias que de verdad existen en esta maquina.

    Se resuelven una sola vez, despues de crear la QApplication, porque
    QFontDatabase no responde antes.
    """

    ui: str = "Sans Serif"
    mono: str = "Monospace"

    @classmethod
    def resolver(cls) -> None:
        cls.ui = _primera_disponible(FAMILIAS_UI, "Sans Serif")
        cls.mono = _primera_disponible(FAMILIAS_MONO, "Monospace")

    @classmethod
    def cuerpo(cls, tam: int = 13, negrita: bool = False) -> QFont:
        fuente = QFont(cls.ui, tam)
        fuente.setWeight(QFont.Weight.DemiBold if negrita else QFont.Weight.Normal)
        return fuente

    @classmethod
    def titulo_panel(cls) -> QFont:
        """Seminegrita, mayusculas y con espaciado amplio."""
        fuente = QFont(cls.ui, 10)
        fuente.setWeight(QFont.Weight.Bold)
        fuente.setCapitalization(QFont.Capitalization.AllUppercase)
        fuente.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 108)
        return fuente

    @classmethod
    def monoespaciada(cls, tam: int = 12, negrita: bool = False) -> QFont:
        fuente = QFont(cls.mono, tam)
        fuente.setWeight(QFont.Weight.DemiBold if negrita else QFont.Weight.Normal)
        return fuente


def color(nombre: str) -> QColor:
    return QColor(nombre)


def con_alfa(hexa: str, alfa: float) -> QColor:
    """El mismo color con transparencia, para fondos tenues y halos de LED."""
    c = QColor(hexa)
    c.setAlphaF(alfa)
    return c


def tinta_sobre(hexa: str) -> str:
    """Negro o blanco, el que se lea mejor sobre ese gris.

    Las etiquetas de las cajas de deteccion se pintan sobre seis grises
    distintos; con un unico color de texto, la mitad quedaria ilegible.
    """
    return TINTA_INVERSA if QColor(hexa).lightnessF() > 0.55 else TEXTO


_RUTA_PALOMITA: Path | None = None


def _palomita() -> str:
    """Ruta a la palomita de las casillas, dibujada y guardada al vuelo.

    Qt no carga imagenes desde un ``data:`` URI en la hoja de estilos, asi que
    la marca se dibuja con QPainter y se escribe a un PNG temporal al que el QSS
    sí puede apuntar. Va en tinta oscura porque la casilla marcada se rellena
    con el gris claro del acento. Se usa ``as_posix`` porque en Windows las
    barras invertidas de la ruta romperian la regla de estilo.
    """
    global _RUTA_PALOMITA
    if _RUTA_PALOMITA is None or not _RUTA_PALOMITA.is_file():
        lado = 28  # al doble, para que se vea nitida en pantallas HiDPI
        pixmap = QPixmap(lado, lado)
        pixmap.fill(Qt.GlobalColor.transparent)
        pintor = QPainter(pixmap)
        pintor.setRenderHint(QPainter.RenderHint.Antialiasing)
        pintor.setPen(
            QPen(QColor(TINTA_INVERSA), 3.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
                 Qt.PenJoinStyle.RoundJoin)
        )
        pintor.drawPolyline(
            [QPointF(6, 14.5), QPointF(11.5, 20), QPointF(22, 8)]
        )
        pintor.end()

        destino = Path(tempfile.gettempdir()) / "vision_contador_palomita.png"
        pixmap.save(str(destino), "PNG")
        _RUTA_PALOMITA = destino
    return _RUTA_PALOMITA.as_posix()


def qss() -> str:
    """Hoja de estilos global de la aplicacion."""
    return f"""
    /* Tipografia y tinta para todo; el fondo, no. Una regla de fondo que
       alcance a cualquier QWidget pinta tambien las filas y los contenedores
       sueltos, que deben dejar ver la tarjeta sobre la que se apoyan. */
    QWidget {{
        color: {TEXTO};
        font-family: "{Fuentes.ui}";
        font-size: 13px;
    }}
    QMainWindow, QDialog {{ background-color: {FONDO}; }}
    /* La pagina de cada pestana si lleva el fondo de la ventana: es lo que
       separa las tarjetas del panel que las contiene. */
    QWidget#ContenidoPestana {{ background-color: {FONDO}; }}

    /* --- Paneles ---------------------------------------------------------
       Sin marco: un panel se reconoce porque su fondo esta un nivel por
       encima del fondo de la ventana. */
    QFrame#Panel {{
        background-color: {PANEL};
        border: none;
        border-radius: {RADIO_PANEL}px;
    }}
    QFrame#CabeceraPanel {{
        background-color: {PANEL_CABECERA};
        border: none;
        border-bottom: 1px solid {BORDE};
        border-top-left-radius: {RADIO_PANEL}px;
        border-top-right-radius: {RADIO_PANEL}px;
    }}
    QLabel#TituloPanel {{
        color: {TEXTO_SEC};
        background: transparent;
    }}
    QLabel#TextoSecundario {{
        color: {TEXTO_SEC};
        background: transparent;
    }}
    QLabel#Hundido {{
        background-color: {HUNDIDO};
        border: none;
        border-radius: {RADIO}px;
    }}

    /* --- Botones --------------------------------------------------------- */
    QPushButton, QToolButton {{
        background-color: {CONTROL};
        border: none;
        border-radius: {RADIO}px;
        color: {TEXTO};
        padding: 6px 12px;
    }}
    QPushButton:hover:enabled, QToolButton:hover:enabled {{
        background-color: {CONTROL_HOVER};
    }}
    QPushButton:pressed:enabled, QToolButton:pressed:enabled {{
        background-color: {CONTROL_PULSADO};
    }}
    QPushButton:disabled, QToolButton:disabled {{
        background-color: #161616;
        color: {TEXTO_APAGADO};
    }}
    QToolButton:checked {{ background-color: {CONTROL_PULSADO}; }}
    QToolButton::menu-button {{
        border: none;
        /* Separador entre la accion y la flecha del menu, como en un boton
           partido de macOS: una linea tenue, no un borde completo. */
        border-left: 1px solid rgba(28, 28, 30, 0.28);
        border-top-right-radius: {RADIO}px;
        border-bottom-right-radius: {RADIO}px;
        width: 18px;
    }}

    QPushButton#Primario, QToolButton#Primario {{
        background-color: {ACENTO};
        border-radius: {RADIO}px;
        color: {TINTA_INVERSA};
        font-weight: 600;
        padding: 8px 18px;
    }}
    QPushButton#Primario:hover:enabled, QToolButton#Primario:hover:enabled {{
        background-color: {ACENTO_HOVER};
    }}
    QPushButton#Primario:pressed:enabled, QToolButton#Primario:pressed:enabled {{
        background-color: {ACENTO_PULSADO};
    }}
    QPushButton#Primario:disabled, QToolButton#Primario:disabled {{
        background-color: #2E2E2E;
        color: {TEXTO_APAGADO};
    }}

    /* --- Menus ----------------------------------------------------------- */
    QMenu {{
        background-color: {PANEL};
        border: 1px solid {BORDE};
        border-radius: {RADIO}px;
        padding: 5px;
    }}
    QMenu::item {{
        padding: 6px 22px 6px 12px;
        border-radius: {RADIO_CHICO}px;
        color: {TEXTO};
    }}
    QMenu::item:selected {{ background-color: {CONTROL_HOVER}; }}
    QMenu::item:disabled {{ color: {TEXTO_APAGADO}; }}
    QMenu::separator {{ height: 1px; background-color: {BORDE}; margin: 4px 0; }}

    /* --- Campos y desplegables ------------------------------------------- */
    QLineEdit, QPlainTextEdit, QTextEdit {{
        background-color: {HUNDIDO};
        border: 1px solid {BORDE};
        border-radius: {RADIO}px;
        color: {TEXTO};
        padding: 5px 8px;
        selection-background-color: {ACENTO};
        selection-color: {TINTA_INVERSA};
    }}
    QLineEdit:focus, QPlainTextEdit:focus {{ border-color: {TEXTO_SEC}; }}
    QLineEdit:disabled {{ color: {TEXTO_APAGADO}; }}

    QComboBox {{
        background-color: {CONTROL};
        border: none;
        border-radius: {RADIO}px;
        color: {TEXTO};
        padding: 4px 8px;
        font-family: "{Fuentes.mono}";
        font-size: 12px;
    }}
    QComboBox:hover:enabled {{ background-color: {CONTROL_HOVER}; }}
    QComboBox:disabled {{ color: {TEXTO_APAGADO}; }}
    QComboBox::drop-down {{ border: none; width: 18px; }}
    QComboBox::down-arrow {{
        image: none;
        border-left: 4px solid transparent;
        border-right: 4px solid transparent;
        border-top: 5px solid {TEXTO_SEC};
        margin-right: 6px;
    }}
    QComboBox QAbstractItemView {{
        background-color: {PANEL};
        border: 1px solid {BORDE};
        border-radius: {RADIO}px;
        color: {TEXTO};
        selection-background-color: {CONTROL_PULSADO};
        outline: none;
    }}

    /* --- Pestanas -------------------------------------------------------- */
    QTabWidget::pane {{
        background-color: {PANEL};
        border: none;
        border-bottom-left-radius: {RADIO_PANEL}px;
        border-bottom-right-radius: {RADIO_PANEL}px;
        top: -1px;
    }}
    QTabBar::tab {{
        background-color: {PANEL_CABECERA};
        border: none;
        color: {TEXTO_SEC};
        padding: 7px 18px;
        margin-right: 2px;
    }}
    QTabBar::tab:first {{ border-top-left-radius: {RADIO_PANEL}px; }}
    QTabBar::tab:last {{ border-top-right-radius: {RADIO_PANEL}px; }}
    QTabBar::tab:selected {{
        background-color: {PANEL};
        border-top: 2px solid {TEXTO};
        color: {TEXTO};
    }}
    QTabBar::tab:hover:!selected {{ color: {TEXTO}; }}

    /* --- Casillas y radios ----------------------------------------------- */
    QCheckBox, QRadioButton {{ spacing: 8px; background: transparent; }}
    QCheckBox:disabled, QRadioButton:disabled {{ color: {TEXTO_APAGADO}; }}
    QCheckBox::indicator, QRadioButton::indicator {{
        width: 14px; height: 14px;
        background-color: {HUNDIDO};
        border: 1px solid {TEXTO_SEC};
        border-radius: {RADIO_CHICO}px;
    }}
    /* El radio es lo unico redondo del sistema: es la forma que lo distingue
       de una casilla, y macOS la respeta igual. */
    QRadioButton::indicator {{ border-radius: 7px; }}
    QCheckBox::indicator:checked {{
        background-color: {ACENTO};
        border-color: {ACENTO};
        image: url({_palomita()});
    }}
    QRadioButton::indicator:checked {{
        background-color: {ACENTO};
        border: 3px solid {HUNDIDO};
    }}
    QCheckBox::indicator:disabled, QRadioButton::indicator:disabled {{
        border-color: #1E1E1E;
    }}

    /* --- Deslizadores ---------------------------------------------------- */
    QSlider::groove:horizontal {{
        background-color: {HUNDIDO};
        border: none;
        border-radius: 3px;
        height: 5px;
    }}
    QSlider::sub-page:horizontal {{
        background-color: {TEXTO_SEC};
        border-radius: 3px;
    }}
    QSlider::handle:horizontal {{
        background-color: {TEXTO};
        border: none;
        border-radius: 7px;
        width: 14px;
        margin: -5px 0;
    }}
    QSlider::handle:horizontal:disabled {{ background-color: {TEXTO_APAGADO}; }}
    QSlider::sub-page:horizontal:disabled {{ background-color: #2B2B2B; }}

    /* --- Barra de progreso ----------------------------------------------- */
    QProgressBar {{
        background-color: {HUNDIDO};
        border: none;
        border-radius: 3px;
        height: 6px;
        text-align: center;
        color: transparent;
    }}
    QProgressBar::chunk {{ background-color: {TEXTO_SEC}; border-radius: 3px; }}

    /* --- Desplazamiento -------------------------------------------------- */
    QScrollArea {{ background: transparent; border: none; }}
    QScrollBar:vertical {{ background: transparent; width: 10px; margin: 0; }}
    QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 0; }}
    QScrollBar::handle:vertical, QScrollBar::handle:horizontal {{
        background-color: {CONTROL_PULSADO};
        border-radius: 4px;
    }}
    QScrollBar::handle:vertical {{ min-height: 28px; }}
    QScrollBar::handle:horizontal {{ min-width: 28px; }}
    QScrollBar::handle:hover {{ background-color: {TEXTO_SEC}; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
    QScrollBar::add-page, QScrollBar::sub-page {{ background: none; }}

    QToolTip {{
        background-color: {PANEL_CABECERA};
        border: 1px solid {BORDE};
        border-radius: {RADIO_CHICO}px;
        color: {TEXTO};
        padding: 5px 7px;
    }}
    """
