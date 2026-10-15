"""Pruebas de la frase hablada y de las filas de la LCD."""

from __future__ import annotations

import pytest

from vision_contador.core.modelos import ConteoClase
from vision_contador.services import frase


def c(clase: str, cantidad: int) -> ConteoClase:
    return ConteoClase(clase=clase, cantidad=cantidad)


class TestGenerar:
    def test_cuatro_clases_distintas(self):
        conteos = [c("Botella", 1), c("Taza", 1), c("Celular", 1), c("Libro", 1)]
        assert (
            frase.generar(conteos)
            == "Se detectaron una botella, una taza, un celular y un libro"
        )

    def test_concordancia_de_genero(self):
        """'una' para las femeninas, 'un' para las masculinas."""
        assert frase.generar([c("Botella", 1)]) == "Se detectó una botella"
        assert frase.generar([c("Libro", 1)]) == "Se detectó un libro"

    def test_plural(self):
        assert (
            frase.generar([c("Botella", 2), c("Celular", 1)])
            == "Se detectaron dos botellas y un celular"
        )

    def test_verbo_singular_solo_con_un_objeto_en_total(self):
        assert frase.generar([c("Taza", 1)]).startswith("Se detectó ")
        assert frase.generar([c("Taza", 2)]).startswith("Se detectaron ")
        assert frase.generar([c("Taza", 1), c("Libro", 1)]).startswith("Se detectaron ")

    def test_sin_objetos(self):
        assert frase.generar([]) == frase.SIN_OBJETOS

    def test_cantidad_fuera_de_la_tabla_usa_la_cifra(self):
        assert frase.generar([c("Libro", 42)]) == "Se detectaron 42 libros"

    def test_clase_desconocida_no_rompe(self):
        """Preferimos un plural imperfecto antes que una excepcion en plena demo."""
        resultado = frase.generar([c("artefacto", 2)])
        assert "artefactos" in resultado


class TestLcd:
    def test_fila_total(self):
        assert frase.fila_lcd_total([c("Botella", 1)]) == "Total: 1 objeto"
        assert frase.fila_lcd_total([c("Botella", 2)]) == "Total: 2 objetos"
        assert frase.fila_lcd_total([]) == "Sin objetos"

    @pytest.mark.parametrize(
        "conteos",
        [
            [c("Botella", 1)],
            [c("Botella", 2), c("Celular", 1)],
            [c("Botella", 1), c("Taza", 1), c("Celular", 1), c("Libro", 1)],
            [c(n, 1) for n in ("Botella", "Taza", "Celular", "Libro", "Laptop", "Mouse")],
            [c(n, 12) for n in ("Botella", "Taza", "Celular", "Libro", "Laptop", "Silla")],
        ],
    )
    def test_las_dos_filas_caben_en_16_columnas(self, conteos):
        """La pantalla fisica tiene 16 columnas; nada puede desbordarla."""
        assert len(frase.fila_lcd_total(conteos)) <= 16
        assert len(frase.fila_lcd_detalle(conteos)) <= 16

    def test_usa_la_abreviatura_mas_larga_que_quepa(self):
        dos = [c("Botella", 2), c("Celular", 1)]
        assert frase.fila_lcd_detalle(dos) == "Bot2 Cel1"

        cuatro = [c("Botella", 1), c("Taza", 1), c("Celular", 1), c("Libro", 1)]
        assert frase.fila_lcd_detalle(cuatro) == "Bo1 Ta1 Ce1 Li1"

    def test_indica_cuantas_clases_quedaron_fuera(self):
        muchas = [c(n, 1) for n in ("Botella", "Taza", "Celular", "Libro", "Laptop", "Mouse", "Silla")]
        detalle = frase.fila_lcd_detalle(muchas)
        assert detalle.endswith(("+1", "+2", "+3", "+4"))

    def test_sin_objetos_deja_la_fila_vacia(self):
        assert frase.fila_lcd_detalle([]) == ""
