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

logger = logging.getLogger(__name__)

DISPLAY_REFRESH_MS = 50  # ~20 fps


class ClipExportWorker(QThread):
    finished_ok = Signal(str)
    failed = Signal(str)

    def __init__(
        self, exporter: ClipExporter, slots, duration_seconds: float, trim_seconds: float
    ):
        super().__init__()
        self._exporter = exporter
        self._slots = slots
        self._duration_seconds = duration_seconds
        self._trim_seconds = trim_seconds

    def run(self) -> None:
        try:
            path = self._exporter.export(self._slots, self._duration_seconds, self._trim_seconds)
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
        self.clip_trim_seconds = 0
        self.output_folder = os.path.join(os.path.expanduser("~"), "ArcheryVision", "clips")
        self._export_worker: ClipExportWorker | None = None
        self._persist_timers: dict[int, QTimer] = {}

        self.mdi_area = QMdiArea()
        self.setCentralWidget(self.mdi_area)

        self.sub_windows: list[CameraSubWindow] = []
        for i in range(MAX_CAMERAS):
            sub = CameraSubWindow(i, f"Cámara {i + 1}")
            sub.view.rotation_changed.connect(self._on_rotation_changed)
            self.mdi_area.addSubWindow(sub)
            self.sub_windows.append(sub)

        self.controls_panel = ControlsPanel()
        self.controls_dock = QDockWidget("Controles", self)
        self.controls_dock.setWidget(self.controls_panel)
        self.addDockWidget(Qt.RightDockWidgetArea, self.controls_dock)

        view_menu = self.menuBar().addMenu("Ver")
        view_menu.addAction(self.controls_dock.toggleViewAction())

        self._refresh_available_devices()
        restored_geometry = self._restore_config()
        self._apply_restored_devices_to_ui()
        for sub in self.sub_windows:
            sub.show()
        if not restored_geometry:
            self.mdi_area.tileSubWindows()

        self._connect_signals()

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
        cp.clip_trim_changed.connect(self._on_clip_trim_changed)
        cp.reset_config_clicked.connect(self._on_reset_config)

        self.hrm_client.status_changed.connect(self._on_hrm_status_changed)
        self.hrm_client.bpm_updated.connect(self.controls_panel.hrm_panel.set_bpm)

    def _refresh_available_devices(self) -> None:
        devices = self.camera_manager.available_devices()
        self.controls_panel.update_available_devices(devices)

    def _on_device_changed(self, slot_index: int, device_index) -> None:
        slot = self.camera_manager.assign_device(slot_index, device_index)
        if slot.worker is not None:
            slot.worker.error.connect(self._on_camera_error)
        self.controls_panel.set_slot_status(slot_index, slot.is_connected)
        if not slot.is_connected:
            self.sub_windows[slot_index].view.clear()
        self._persist_camera_settings(slot_index)

    def _on_camera_error(self, slot_index: int, message: str) -> None:
        logger.warning("Error en cámara %d: %s", slot_index, message)
        self.controls_panel.set_slot_status(slot_index, False)

    def _on_delay_changed(self, slot_index: int, seconds: float) -> None:
        slot = self.camera_manager.slots[slot_index]
        slot.delay_seconds = seconds
        self._update_buffer_size(slot_index)
        self._schedule_persist(slot_index)

    def _update_buffer_size(self, slot_index: int) -> None:
        slot = self.camera_manager.slots[slot_index]
        needed = max(slot.delay_seconds, self.clip_duration_seconds + self.clip_trim_seconds)
        slot.buffer.set_max_seconds(needed + 2.0)

    def _schedule_persist(self, slot_index: int) -> None:
        if slot_index not in self._persist_timers:
            timer = QTimer(self)
            timer.setSingleShot(True)
            timer.timeout.connect(lambda i=slot_index: self._persist_camera_settings(i))
            self._persist_timers[slot_index] = timer
        self._persist_timers[slot_index].start(400)

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
            slot_index, slot.name, slot.delay_seconds, slot.rotation_degrees, slot.device_index
        )

    def _restore_config(self) -> bool:
        """Aplica delay/nombre/rotación/cámara y geometría de ventana guardados.

        La cámara asignada se restaura aquí directamente sobre CameraManager
        (no a través de _on_device_changed) porque el desplegable del panel
        de control todavía no tiene poblada la lista de dispositivos en este
        punto; se refleja en la UI después, en _apply_restored_devices_to_ui().

        Devuelve True si había geometría de ventana guardada, para que el
        llamador decida si hace falta el tileSubWindows() por defecto.
        """
        clip_settings = self.config_store.load_clip_settings()
        if clip_settings is not None:
            self.clip_duration_seconds = clip_settings["duration_seconds"]
            self.clip_trim_seconds = clip_settings["trim_seconds"]
            self.controls_panel.set_clip_duration(self.clip_duration_seconds)
            self.controls_panel.set_clip_trim(self.clip_trim_seconds)

        any_geometry_restored = False
        for slot in self.camera_manager.slots:
            i = slot.slot_index
            cam_settings = self.config_store.load_camera_settings(i)
            if cam_settings is not None:
                slot.name = cam_settings["name"] or slot.name
                slot.delay_seconds = cam_settings["delay_seconds"]
                needed = max(slot.delay_seconds, self.clip_duration_seconds + self.clip_trim_seconds)
                slot.buffer.set_max_seconds(needed + 2.0)
                slot.rotation_degrees = cam_settings["rotation_degrees"]
                self.controls_panel.set_slot_name(i, slot.name)
                self.controls_panel.set_slot_delay(i, slot.delay_seconds)
                self.sub_windows[i].view.set_rotation(slot.rotation_degrees)
                self.sub_windows[i].setWindowTitle(slot.name)
                if cam_settings["device_index"] is not None:
                    restored_slot = self.camera_manager.assign_device(i, cam_settings["device_index"])
                    if restored_slot.worker is not None:
                        restored_slot.worker.error.connect(self._on_camera_error)

            window_state = self.config_store.load_window_geometry(i)
            if window_state is not None:
                sub = self.sub_windows[i]
                sub.setGeometry(
                    window_state["x"], window_state["y"], window_state["width"], window_state["height"]
                )
                if window_state["maximized"]:
                    sub.showMaximized()
                any_geometry_restored = True
        return any_geometry_restored

    def _apply_restored_devices_to_ui(self) -> None:
        for slot in self.camera_manager.slots:
            if slot.device_index is not None:
                self.controls_panel.set_slot_device(slot.slot_index, slot.device_index)
                self.controls_panel.set_slot_status(slot.slot_index, slot.is_connected)

    def _on_clip_duration_changed(self, seconds: int) -> None:
        self.clip_duration_seconds = seconds
        for i in range(len(self.camera_manager.slots)):
            self._update_buffer_size(i)
        self._persist_clip_settings()

    def _on_clip_trim_changed(self, seconds: int) -> None:
        self.clip_trim_seconds = seconds
        for i in range(len(self.camera_manager.slots)):
            self._update_buffer_size(i)
        self._persist_clip_settings()

    def _persist_clip_settings(self) -> None:
        self.config_store.save_clip_settings(self.clip_duration_seconds, self.clip_trim_seconds)

    def _on_output_folder_changed(self, folder: str) -> None:
        self.output_folder = folder

    def _update_displays(self) -> None:
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
            exporter, self.camera_manager.slots, self.clip_duration_seconds, self.clip_trim_seconds
        )
        self._export_worker.finished_ok.connect(self._on_export_finished)
        self._export_worker.failed.connect(self._on_export_failed)
        self._export_worker.start()

    def _on_export_finished(self, path: str) -> None:
        QMessageBox.information(self, "Clip guardado", f"Clip exportado correctamente:\n{path}")

    def _on_export_failed(self, message: str) -> None:
        QMessageBox.warning(self, "Error al exportar", message)

    def _on_reset_config(self) -> None:
        reply = QMessageBox.question(
            self,
            "Resetear configuración",
            "¿Seguro que quieres borrar toda la configuración?\n"
            "Se perderán los delays, cámaras asignadas, nombres y posición de ventanas.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        for timer in self._persist_timers.values():
            timer.stop()

        self.config_store.clear_all()

        for i, slot in enumerate(self.camera_manager.slots):
            self.camera_manager.assign_device(i, None)
            slot.delay_seconds = 0.0
            slot.buffer.set_max_seconds(self.clip_duration_seconds + self.clip_trim_seconds + 2.0)
            slot.rotation_degrees = 0
            default_name = f"Cámara {i + 1}"
            slot.name = default_name
            self.controls_panel.set_slot_name(i, default_name)
            self.controls_panel.set_slot_delay(i, 0.0)
            self.controls_panel.set_slot_device(i, None)
            self.controls_panel.set_slot_status(i, False)
            self.sub_windows[i].setWindowTitle(default_name)
            self.sub_windows[i].view.set_rotation(0)
            self.sub_windows[i].view.clear()

        self.mdi_area.tileSubWindows()

    def _on_hrm_status_changed(self, status: str) -> None:
        # El panel de pulsaciones (RF-4.3) ya comunica "Bluetooth no
        # disponible" en rojo de forma permanente; evitamos un QMessageBox
        # modal porque, al llegar por una señal en cola desde el hilo BLE,
        # puede aparecer en cualquier momento (incluso al cerrar la ventana)
        # y bloquear toda la interfaz hasta que alguien lo cierre manualmente.
        self.controls_panel.hrm_panel.set_status(status)

    def closeEvent(self, event) -> None:
        for sub in self.sub_windows:
            geo = sub.normal_geometry
            self.config_store.save_window_geometry(
                sub.slot_index, geo.x(), geo.y(), geo.width(), geo.height(), sub.isMaximized()
            )
        self.config_store.sync()
        self.display_timer.stop()
        self.camera_manager.shutdown()
        self.hrm_client.stop()
        super().closeEvent(event)
