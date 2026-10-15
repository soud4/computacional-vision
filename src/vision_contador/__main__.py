"""Punto de entrada de la aplicacion."""

from __future__ import annotations

import argparse
import sys

from .core import config as config_mod


def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vision-contador",
        description="Detección, clasificación y conteo de objetos con webcam, PDI y Arduino.",
    )
    modo = parser.add_mutually_exclusive_group()
    modo.add_argument(
        "--demo",
        action="store_true",
        help="fuerza los adaptadores simulados (sin cámara, modelo ni Arduino)",
    )
    modo.add_argument(
        "--real",
        action="store_true",
        help="fuerza los adaptadores reales según config/default.toml",
    )
    parser.add_argument(
        "--estado",
        choices=("a", "b"),
        help="abre forzando una variante: a = procesando, b = Arduino desconectado",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = construir_parser().parse_args(argv)

    config = config_mod.cargar()
    if args.demo:
        config.modo = "demo"
    elif args.real:
        config.modo = "real"

    # Qt se importa despues de parsear los argumentos para que --help responda
    # al instante y sin necesitar un servidor grafico.
    from PySide6.QtWidgets import QApplication

    from . import fabrica
    from .ui import tema
    from .ui.ventana_principal import VentanaPrincipal

    app = QApplication(sys.argv[:1])
    app.setApplicationName("Visión Contador")
    tema.Fuentes.resolver()
    app.setStyleSheet(tema.qss())

    try:
        deps = fabrica.crear_dependencias(config)
    except fabrica.AdaptadorNoImplementado as error:
        print(f"No se pudo iniciar en modo «{config.modo}»: {error}", file=sys.stderr)
        return 2

    ventana = VentanaPrincipal(config, deps)
    ventana.show()

    if args.estado == "a":
        ventana.capturar()
    elif args.estado == "b":
        ventana.forzar_estado("sin_arduino")

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
