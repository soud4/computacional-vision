"""Pruebas del filtrado por confianza y del conteo por clase."""

from __future__ import annotations

from vision_contador.core.modelos import Deteccion, Rect
from vision_contador.services import contador


def d(clase: str, confianza: float) -> Deteccion:
    return Deteccion(clase=clase, confianza=confianza, caja=Rect(0, 0, 10, 10))


class TestFiltrar:
    def test_descarta_por_debajo_del_umbral(self):
        detecciones = [d("bottle", 0.91), d("bottle", 0.30), d("cup", 0.50)]
        assert len(contador.filtrar(detecciones, 0.50)) == 2

    def test_el_umbral_es_inclusivo(self):
        """Una confianza igual al umbral cuenta: el usuario puso 0.50, no 0.51."""
        assert len(contador.filtrar([d("cup", 0.50)], 0.50)) == 1

    def test_umbral_cero_no_descarta_nada(self):
        detecciones = [d("bottle", 0.01), d("cup", 0.99)]
        assert len(contador.filtrar(detecciones, 0.0)) == 2


class TestContar:
    def test_agrupa_y_traduce(self):
        conteos = contador.contar([d("bottle", 0.9), d("bottle", 0.8), d("cup", 0.7)])
        assert conteos[0].clase == "Botella"
        assert conteos[0].cantidad == 2
        assert conteos[1].clase == "Taza"
        assert conteos[1].cantidad == 1

    def test_ordena_por_cantidad_descendente(self):
        conteos = contador.contar([d("cup", 0.9), d("book", 0.9), d("book", 0.9)])
        assert [x.cantidad for x in conteos] == [2, 1]
        assert conteos[0].clase == "Libro"

    def test_a_igual_cantidad_respeta_el_orden_de_deteccion(self):
        """La lista y la frase deben seguir el orden en que el detector vio la escena."""
        detecciones = [d("bottle", 0.9), d("cup", 0.9), d("cell phone", 0.9), d("book", 0.9)]
        assert [x.clase for x in contador.contar(detecciones)] == [
            "Botella", "Taza", "Celular", "Libro",
        ]

    def test_acepta_clases_ya_en_espanol(self):
        """El pipeline traduce antes de contar; contar dos veces no debe romperlo."""
        assert contador.contar([d("Botella", 0.9)])[0].clase == "Botella"

    def test_sin_detecciones(self):
        assert contador.contar([]) == []
        assert contador.total([]) == 0
