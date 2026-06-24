"""Reloj de sincronía único compartido por todos los streams (RF-2.3, RNF-2)."""

import time

from PySide6.QtCore import QObject, Signal


class SyncClock(QObject):
    """Reloj monotónico compartido. Al reproducir, todas las cámaras leen
    de este mismo reloj y restan su propio delay para decidir qué frame
    mostrar, garantizando que están ancladas al mismo instante de captura.
    """

    started = Signal()
    paused = Signal()

    def __init__(self):
        super().__init__()
        self._playing = False

    def play(self) -> None:
        self._playing = True
        self.started.emit()

    def pause(self) -> None:
        self._playing = False
        self.paused.emit()

    @property
    def is_playing(self) -> bool:
        return self._playing

    @staticmethod
    def now() -> float:
        return time.monotonic()
