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
from app.hrm.ble_client import HRMClient, STATUS_BLE_UNAVAILABLE
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
        self.clip_duration_seconds = DEFAULT_CLIP_SECONDS
        self.output_folder = os.path.join(os.path.expanduser("~"), "ArcheryVision", "clips")
        self._export_worker: ClipExportWorker | None = None
        self._ble_unavailable_warned = False

        self.mdi_area = QMdiArea()
        self.setCentralWidget(self.mdi_area)

        self.sub_windows: list[CameraSubWindow] = []
        for i in range(MAX_CAMERAS):
            sub = CameraSubWindow(i, f"Cámara {i + 1}")
            sub.view.rotation_changed.connect(self._on_rotation_changed)
            self.mdi_area.addSubWindow(sub)
            sub.show()
            self.sub_windows.append(sub)
        self.mdi_area.tileSubWindows()

        self.controls_panel = ControlsPanel()
        dock = QDockWidget("Controles", self)
        dock.setWidget(self.controls_panel)
        self.addDockWidget(Qt.RightDockWidgetArea, dock)

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

    def _on_rotation_changed(self, slot_index: int, degrees: int) -> None:
        self.camera_manager.slots[slot_index].rotation_degrees = degrees

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
        self.hrm_overlay.set_status(status)
        if status == STATUS_BLE_UNAVAILABLE and not self._ble_unavailable_warned:
            self._ble_unavailable_warned = True
            QMessageBox.warning(
                self,
                "Bluetooth no disponible",
                "No se ha detectado un adaptador Bluetooth Low Energy (BLE) "
                "compatible. Conecta el cinturón HRM mediante un adaptador "
                "Bluetooth 4.0 o superior.",
            )

    def closeEvent(self, event) -> None:
        self.display_timer.stop()
        self.camera_manager.shutdown()
        self.hrm_client.stop()
        super().closeEvent(event)
