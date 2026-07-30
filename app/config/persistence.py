"""Persistencia de configuración (RNF-4).

Guarda y restaura automáticamente delay, nombre, rotación y dispositivo
asignado de cada cámara, y posición/tamaño/maximizado de cada ventana,
usando QSettings (registro de Windows / .plist en macOS / fichero .ini
en Linux, según plataforma).
"""

from PySide6.QtCore import QSettings

from app.pose.view_modes import Handedness, ViewMode

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

    def save_clip_settings(self, duration_seconds: int, trim_seconds: int) -> None:
        self._settings.beginGroup("clip")
        self._settings.setValue("duration_seconds", duration_seconds)
        self._settings.setValue("trim_seconds", trim_seconds)
        self._settings.endGroup()

    def load_clip_settings(self) -> dict | None:
        self._settings.beginGroup("clip")
        has_data = self._settings.contains("duration_seconds")
        result = None
        if has_data:
            result = {
                "duration_seconds": self._settings.value("duration_seconds", type=int),
                "trim_seconds": self._settings.value("trim_seconds", type=int),
            }
        self._settings.endGroup()
        return result

    def save_controls_visible(self, visible: bool) -> None:
        self._settings.setValue("controls_visible", visible)

    def load_controls_visible(self) -> bool | None:
        if not self._settings.contains("controls_visible"):
            return None
        return self._settings.value("controls_visible", type=bool)

    def save_pose_settings(
        self,
        view_mode: ViewMode,
        handedness: Handedness,
        device_index: int | None,
        delay_seconds: float,
        clip_duration_seconds: float,
        trim_seconds: float,
        output_folder: str,
        sound_enabled: bool,
        rotation_degrees: int,
    ) -> None:
        self._settings.beginGroup("pose")
        self._settings.setValue("view_mode", view_mode.value)
        self._settings.setValue("handedness", handedness.value)
        self._settings.setValue("device_index", device_index if device_index is not None else -1)
        self._settings.setValue("delay_seconds", delay_seconds)
        self._settings.setValue("clip_duration_seconds", clip_duration_seconds)
        self._settings.setValue("trim_seconds", trim_seconds)
        self._settings.setValue("output_folder", output_folder)
        self._settings.setValue("sound_enabled", sound_enabled)
        self._settings.setValue("rotation_degrees", rotation_degrees)
        self._settings.endGroup()

    def load_pose_settings(self) -> dict | None:
        self._settings.beginGroup("pose")
        has_data = self._settings.contains("view_mode")
        result = None
        if has_data:
            device_index = self._settings.value("device_index", type=int)
            result = {
                "view_mode": ViewMode(self._settings.value("view_mode", type=str)),
                "handedness": Handedness(self._settings.value("handedness", type=str)),
                "device_index": None if device_index < 0 else device_index,
                "delay_seconds": self._settings.value("delay_seconds", type=float),
                "clip_duration_seconds": self._settings.value("clip_duration_seconds", type=float),
                "trim_seconds": self._settings.value("trim_seconds", type=float),
                "output_folder": self._settings.value("output_folder", type=str),
                "sound_enabled": self._settings.value("sound_enabled", type=bool),
                "rotation_degrees": self._settings.value("rotation_degrees", type=int),
            }
        self._settings.endGroup()
        return result

    def clear_all(self) -> None:
        self._settings.clear()
        self._settings.sync()

    def sync(self) -> None:
        self._settings.sync()
