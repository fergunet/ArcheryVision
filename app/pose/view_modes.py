"""Vistas de cámara y lateralidad del arquero para el análisis de postura."""

from enum import Enum


class ViewMode(Enum):
    """Vista de cámara seleccionada (sección 3.1 / 6 de requisitos_modulo_vision.md).

    TRASERA: la cámara apunta al lado derecho del arquero y a la diana (nunca
    delante del arco, por seguridad). Corresponde a la "vista trasera" de 6.1.
    """

    TRASERA = "trasera"
    LATERAL = "lateral"
    SUPERIOR = "superior"


class Handedness(Enum):
    DIESTRO = "diestro"
    ZURDO = "zurdo"
