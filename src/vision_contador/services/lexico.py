"""Lexico espanol de las clases detectables.

El detector trabaja con los nombres en ingles de COCO; la interfaz, la frase
hablada y la LCD trabajan en espanol. Este modulo es el unico puente entre
ambos, para que agregar una clase nueva sea editar una linea.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EntradaLexico:
    """Como se nombra una clase en espanol."""

    singular: str
    plural: str
    femenino: bool
    #: Abreviatura de 3 letras para la segunda fila de la LCD 16x2.
    abreviatura: str

    @property
    def articulo(self) -> str:
        return "una" if self.femenino else "un"


def _e(singular: str, plural: str, femenino: bool, abreviatura: str) -> EntradaLexico:
    return EntradaLexico(singular, plural, femenino, abreviatura)


#: Clave: nombre de clase de COCO en ingles, en minusculas.
LEXICO: dict[str, EntradaLexico] = {
    "bottle": _e("botella", "botellas", True, "Bot"),
    "cup": _e("taza", "tazas", True, "Taz"),
    "cell phone": _e("celular", "celulares", False, "Cel"),
    "book": _e("libro", "libros", False, "Lib"),
    "laptop": _e("laptop", "laptops", True, "Lap"),
    "mouse": _e("mouse", "mouses", False, "Mou"),
    "keyboard": _e("teclado", "teclados", False, "Tec"),
    "remote": _e("control remoto", "controles remotos", False, "Ctl"),
    "scissors": _e("tijera", "tijeras", True, "Tij"),
    "clock": _e("reloj", "relojes", False, "Rel"),
    "vase": _e("florero", "floreros", False, "Flo"),
    "bowl": _e("tazón", "tazones", False, "Tzn"),
    "spoon": _e("cuchara", "cucharas", True, "Cuc"),
    "fork": _e("tenedor", "tenedores", False, "Ten"),
    "knife": _e("cuchillo", "cuchillos", False, "Cuh"),
    "wine glass": _e("copa", "copas", True, "Cop"),
    "banana": _e("plátano", "plátanos", False, "Pla"),
    "apple": _e("manzana", "manzanas", True, "Man"),
    "orange": _e("naranja", "naranjas", True, "Nar"),
    "backpack": _e("mochila", "mochilas", True, "Moc"),
    "chair": _e("silla", "sillas", True, "Sil"),
    "person": _e("persona", "personas", True, "Per"),
    "tv": _e("televisor", "televisores", False, "Tel"),
}


def entrada(clase: str) -> EntradaLexico:
    """Devuelve la entrada de una clase, en ingles o ya en espanol.

    Si la clase es desconocida se construye una entrada masculina con plural en
    ``-s``: es preferible decir 'dos tenedors' que romper la aplicacion en plena
    demostracion.
    """
    clave = clase.strip().lower()
    if clave in LEXICO:
        return LEXICO[clave]
    for ent in LEXICO.values():
        if ent.singular == clave:
            return ent
    plural = clave if clave.endswith("s") else f"{clave}s"
    return EntradaLexico(clave, plural, False, clave[:3].capitalize())


def nombre_es(clase: str) -> str:
    """Nombre en espanol capitalizado, para la lista de conteo: 'Botella'."""
    return entrada(clase).singular.capitalize()
