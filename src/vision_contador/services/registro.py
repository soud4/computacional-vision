"""Registro de cada captura en CSV y en disco.

Lo que queda registrado es lo que despues sustenta el informe del curso: una
fila por captura con los conteos y las metricas, mas las imagenes original y
preprocesada.
"""

from __future__ import annotations

import csv
from pathlib import Path

from ..core.modelos import ResultadoCaptura
from .imagen_io import guardar_png

CABECERAS = [
    "momento",
    "total",
    "conteos",
    "frase",
    "modelo",
    "ms_inferencia",
    "brillo_antes",
    "brillo_despues",
    "contraste_antes",
    "contraste_despues",
    "etapas_aplicadas",
    "imagen_original",
    "imagen_preprocesada",
]


class Registro:
    """Acumula las capturas de la sesion en ``capturas/``."""

    def __init__(self, carpeta: Path) -> None:
        self.carpeta = carpeta
        self.csv = carpeta / "capturas.csv"
        self.imagenes = carpeta / "imagenes"

    def _asegurar_csv(self) -> None:
        if self.csv.is_file():
            return
        self.csv.parent.mkdir(parents=True, exist_ok=True)
        with self.csv.open("w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(CABECERAS)

    def anotar(self, resultado: ResultadoCaptura, guardar_imagenes: bool = True) -> None:
        """Agrega una fila al CSV y, si se pide, guarda las dos imagenes."""
        sello = resultado.momento.strftime("%Y%m%d-%H%M%S")
        ruta_original = ruta_preproc = ""

        if guardar_imagenes:
            ruta_original = str(
                guardar_png(resultado.capturada, self.imagenes / f"{sello}-original.png")
                .relative_to(self.carpeta)
            )
            ruta_preproc = str(
                guardar_png(resultado.preprocesada, self.imagenes / f"{sello}-preproc.png")
                .relative_to(self.carpeta)
            )

        self._asegurar_csv()
        aplicadas = ";".join(
            etapa.value for etapa, si in resultado.etapas_aplicadas.items() if si
        )
        with self.csv.open("a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(
                [
                    resultado.momento.isoformat(timespec="seconds"),
                    resultado.total,
                    ";".join(f"{c.clase}={c.cantidad}" for c in resultado.conteos),
                    resultado.frase,
                    resultado.modelo,
                    resultado.ms_inferencia,
                    f"{resultado.histograma_antes.brillo_medio:.1f}",
                    f"{resultado.histograma_despues.brillo_medio:.1f}",
                    f"{resultado.histograma_antes.contraste:.1f}",
                    f"{resultado.histograma_despues.contraste:.1f}",
                    aplicadas,
                    ruta_original,
                    ruta_preproc,
                ]
            )
