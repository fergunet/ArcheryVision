"""Persistencia de configuración (RNF-4).

Guarda y restaura automáticamente delay, nombre, rotación y dispositivo
asignado de cada cámara, y posición/tamaño/maximizado de cada ventana,
usando QSettings (registro de Windows / .plist en macOS / fichero .ini
en Linux, según plataforma).
"""

from PySide6.QtCore import QSettings

ORG_NAME = "ArcheryVision"
APP_NAME = "ArcheryVision"


class ConfigStore:
    def __init__(self):
        self._settings = QSettings(ORG_NAME, APP_NAME)

    def save_camera_settings(
        self,
        slot_index: int,
        name: str,
        delay_seconds: float,
        rotation_degrees: int,
        device_index: int | None,
    ) -> None:
        self._settings.beginGroup(f"camera_{slot_index}")
        self._settings.setValue("name", name)
        self._settings.setValue("delay_seconds", delay_seconds)
        self._settings.setValue("rotation_degrees", rotation_degrees)
        self._settings.setValue("device_index", device_index if device_index is not None else -1)
        self._settings.endGroup()

    def load_camera_settings(self, slot_index: int) -> dict | None:
        self._settings.beginGroup(f"camera_{slot_index}")
        has_data = self._settings.contains("name")
        result = None
        if has_data:
            device_index = self._settings.value("device_index", type=int)
            result = {
                "name": self._settings.value("name", type=str),
                "delay_seconds": self._settings.value("delay_seconds", type=float),
                "rotation_degrees": self._settings.value("rotation_degrees", type=int),
                "device_index": None if device_index < 0 else device_index,
            }
        self._settings.endGroup()
        return result

    def save_window_geometry(
        self, slot_index: int, x: int, y: int, width: int, height: int, maximized: bool
    ) -> None:
        self._settings.beginGroup(f"window_{slot_index}")
        self._settings.setValue("x", x)
        self._settings.setValue("y", y)
        self._settings.setValue("width", width)
        self._settings.setValue("height", height)
        self._settings.setValue("maximized", maximized)
        self._settings.endGroup()

    def load_window_geometry(self, slot_index: int) -> dict | None:
        self._settings.beginGroup(f"window_{slot_index}")
        has_data = self._settings.contains("x")
        result = None
        if has_data:
            result = {
                "x": self._settings.value("x", type=int),
                "y": self._settings.value("y", type=int),
                "width": self._settings.value("width", type=int),
                "height": self._settings.value("height", type=int),
                "maximized": self._settings.value("maximized", type=bool),
            }
        self._settings.endGroup()
        return result

    def sync(self) -> None:
        self._settings.sync()
