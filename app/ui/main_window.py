"""Ventana principal: integra cámaras, sincronía, HRM y exportación de clips."""

import logging
import os

from PySide6.QtCore import QThread, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QDockWidget,
    QMainWindow,
    QMdiArea,
    QMessageBox,
)

from app.camera.manager import CameraManager, MAX_CAMERAS
from app.config.persistence import ConfigStore
from app.hrm.ble_client import HRMClient
from app.recording.exporter import ClipExporter
from app.sync.clock import SyncClock
from app.ui.camera_view import CameraSubWindow
from app.ui.controls_panel import ControlsPanel, DEFAULT_CLIP_SECONDS
from app.ui.hrm_overlay import HRMOverlay

logger = logging.getLogger(__name__)

DISPLAY_REFRESH_MS = 33  # ~30 fps


class ClipExportWorker(QThread):
    finished_ok = Signal(str)
    failed = Signal(str)

    def __init__(self, exporter: ClipExporter, slots, duration_seconds: float):
        super().__init__()
        self._exporter = exporter
        self._slots = slots
        self._duration_seconds = duration_seconds

    def run(self) -> None:
        try:
            path = self._exporter.export(self._slots, self._duration_seconds)
            if path:
                self.finished_ok.emit(path)
            else:
                self.failed.emit("No hay cámaras activas con datos suficientes para exportar.")
        except Exception as exc:  # noqa: BLE001 - reportar cualquier fallo de export al usuario
            logger.exception("Fallo exportando clip")
            self.failed.emit(str(exc))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ArcheryVision — Vídeo multi-cámara para arquería")
        self.resize(1280, 800)

        self.camera_manager = CameraManager()
        self.sync_clock = SyncClock()
        self.hrm_client = HRMClient()
        self.config_store = ConfigStore()
        self.clip_duration_seconds = DEFAULT_CLIP_SECONDS
        self.output_folder = os.path.join(os.path.expanduser("~"), "ArcheryVision", "clips")
        self._export_worker: ClipExportWorker | None = None

        self.mdi_area = QMdiArea()
        self.setCentralWidget(self.mdi_area)

        self.sub_windows: list[CameraSubWindow] = []
        for i in range(MAX_CAMERAS):
            sub = CameraSubWindow(i, f"Cámara {i + 1}")
            sub.view.rotation_changed.connect(self._on_rotation_changed)
            self.mdi_area.addSubWindow(sub)
            self.sub_windows.append(sub)

        self.controls_panel = ControlsPanel()
        dock = QDockWidget("Controles", self)
        dock.setWidget(self.controls_panel)
        self.addDockWidget(Qt.RightDockWidgetArea, dock)

        restored_geometry = self._restore_config()
        for sub in self.sub_windows:
            sub.show()
        if not restored_geometry:
            self.mdi_area.tileSubWindows()

        self.hrm_overlay = HRMOverlay(parent=self.mdi_area.viewport())
        self.hrm_overlay.move(10, 10)
        self.hrm_overlay.raise_()
        self.mdi_area.subWindowActivated.connect(lambda _sw: self.hrm_overlay.raise_())

        self._connect_signals()
        self._refresh_available_devices()

        self.display_timer = QTimer(self)
        self.display_timer.timeout.connect(self._update_displays)
        self.display_timer.start(DISPLAY_REFRESH_MS)

        self.hrm_client.start()

    def _connect_signals(self) -> None:
        cp = self.controls_panel
        cp.device_changed.connect(self._on_device_changed)
        cp.delay_changed.connect(self._on_delay_changed)
        cp.name_changed.connect(self._on_name_changed)
        cp.play_clicked.connect(self.sync_clock.play)
        cp.pause_clicked.connect(self.sync_clock.pause)
        cp.rescan_clicked.connect(self._refresh_available_devices)
        cp.save_clip_clicked.connect(self._on_save_clip)
        cp.clip_duration_changed.connect(self._on_clip_duration_changed)
        cp.output_folder_changed.connect(self._on_output_folder_changed)

        self.hrm_client.status_changed.connect(self._on_hrm_status_changed)
        self.hrm_client.bpm_updated.connect(self.hrm_overlay.set_bpm)

    def _refresh_available_devices(self) -> None:
        devices = self.camera_manager.available_devices()
        self.controls_panel.update_available_devices(devices)

    def _on_device_changed(self, slot_index: int, device_index) -> None:
        slot = self.camera_manager.assign_device(slot_index, device_index)
        self.controls_panel.set_slot_status(slot_index, slot.is_connected)
        if not slot.is_connected:
            self.sub_windows[slot_index].view.clear()

    def _on_delay_changed(self, slot_index: int, seconds: float) -> None:
        self.camera_manager.slots[slot_index].delay_seconds = seconds
        self._persist_camera_settings(slot_index)

    def _on_rotation_changed(self, slot_index: int, degrees: int) -> None:
        self.camera_manager.slots[slot_index].rotation_degrees = degrees
        self._persist_camera_settings(slot_index)

    def _on_name_changed(self, slot_index: int, name: str) -> None:
        slot = self.camera_manager.slots[slot_index]
        slot.name = name or f"Cámara {slot_index + 1}"
        self.sub_windows[slot_index].setWindowTitle(slot.name)
        self._persist_camera_settings(slot_index)

    def _persist_camera_settings(self, slot_index: int) -> None:
        slot = self.camera_manager.slots[slot_index]
        self.config_store.save_camera_settings(
            slot_index, slot.name, slot.delay_seconds, slot.rotation_degrees
        )

    def _restore_config(self) -> bool:
        """Aplica delay/nombre/rotación y geometría de ventana guardados.

        Devuelve True si había geometría de ventana guardada, para que el
        llamador decida si hace falta el tileSubWindows() por defecto.
        """
        any_geometry_restored = False
        for slot in self.camera_manager.slots:
            i = slot.slot_index
            cam_settings = self.config_store.load_camera_settings(i)
            if cam_settings is not None:
                slot.name = cam_settings["name"] or slot.name
                slot.delay_seconds = cam_settings["delay_seconds"]
                slot.rotation_degrees = cam_settings["rotation_degrees"]
                self.controls_panel.set_slot_name(i, slot.name)
                self.controls_panel.set_slot_delay(i, slot.delay_seconds)
                self.sub_windows[i].view.set_rotation(slot.rotation_degrees)
                self.sub_windows[i].setWindowTitle(slot.name)

            geometry = self.config_store.load_window_geometry(i)
            if geometry is not None:
                x, y, width, height = geometry
                self.sub_windows[i].setGeometry(x, y, width, height)
                any_geometry_restored = True
        return any_geometry_restored

    def _on_clip_duration_changed(self, seconds: int) -> None:
        self.clip_duration_seconds = seconds

    def _on_output_folder_changed(self, folder: str) -> None:
        self.output_folder = folder

    def _update_displays(self) -> None:
        self.hrm_overlay.raise_()
        if not self.sync_clock.is_playing:
            return
        now = self.sync_clock.now()
        for slot in self.camera_manager.slots:
            if not slot.is_connected:
                continue
            target_time = now - slot.delay_seconds
            timed_frame = slot.buffer.get_nearest(target_time)
            if timed_frame is not None:
                self.sub_windows[slot.slot_index].view.display_frame(timed_frame.frame)

    def _on_save_clip(self) -> None:
        if self._export_worker is not None and self._export_worker.isRunning():
            QMessageBox.information(self, "Exportando", "Ya se está exportando un clip.")
            return
        exporter = ClipExporter(self.output_folder)
        self._export_worker = ClipExportWorker(
            exporter, self.camera_manager.slots, self.clip_duration_seconds
        )
        self._export_worker.finished_ok.connect(self._on_export_finished)
        self._export_worker.failed.connect(self._on_export_failed)
        self._export_worker.start()

    def _on_export_finished(self, path: str) -> None:
        QMessageBox.information(self, "Clip guardado", f"Clip exportado correctamente:\n{path}")

    def _on_export_failed(self, message: str) -> None:
        QMessageBox.warning(self, "Error al exportar", message)

    def _on_hrm_status_changed(self, status: str) -> None:
        # El overlay (RF-4.3) ya comunica "Bluetooth no disponible" en rojo
        # de forma permanente; evitamos un QMessageBox modal porque, al
        # llegar por una señal en cola desde el hilo BLE, puede aparecer en
        # cualquier momento (incluso al cerrar la ventana) y bloquear toda
        # la interfaz hasta que alguien lo cierre manualmente.
        self.hrm_overlay.set_status(status)

    def closeEvent(self, event) -> None:
        for sub in self.sub_windows:
            geo = sub.geometry()
            self.config_store.save_window_geometry(
                sub.slot_index, geo.x(), geo.y(), geo.width(), geo.height()
            )
        self.config_store.sync()
        self.display_timer.stop()
        self.camera_manager.shutdown()
        self.hrm_client.stop()
        super().closeEvent(event)
