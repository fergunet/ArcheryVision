"""Panel de análisis de postura por visión artificial (requisitos_modulo_vision.md).

Vista de cámara en vivo con esqueleto superpuesto, selección de vista y
lateralidad, delay/recorte configurables, grabación y panel de estado.
"""

import logging
import os
import time

from PySide6.QtCore import QThread, QTimer, QUrl, Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtMultimedia import QSoundEffect
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.camera.buffer import FrameRingBuffer
from app.camera.manager import detect_available_cameras
from app.pose.exporter import PoseClipExporter
from app.pose.history import PoseResultHistory
from app.pose.view_modes import Handedness, ViewMode
from app.pose.worker import TARGET_FPS, PoseWorker
from app.ui.camera_view import PLACEHOLDER_TEXT, VideoLabel
from app.ui.controls_panel import DEFAULT_CLIP_SECONDS, MAX_CLIP_SECONDS, MIN_CLIP_SECONDS

logger = logging.getLogger(__name__)

DISPLAY_REFRESH_MS = 50
MAX_DELAY_SECONDS_POSE = 30.0
NO_DEVICE_LABEL = "-- Sin cámara --"
BEEP_PATH = os.path.join(os.path.dirname(__file__), "..", "pose", "assets", "beep.wav")

VIEW_MODE_LABELS = {
    ViewMode.TRASERA: "Trasera",
    ViewMode.LATERAL: "Lateral",
    ViewMode.SUPERIOR: "Superior",
}
HANDEDNESS_LABELS = {
    Handedness.DIESTRO: "Diestro",
    Handedness.ZURDO: "Zurdo",
}


class PoseClipExportWorker(QThread):
    finished_ok = Signal(str)
    failed = Signal(str)

    def __init__(
        self, exporter: PoseClipExporter, buffer: FrameRingBuffer, duration_seconds: float, trim_seconds: float
    ):
        super().__init__()
        self._exporter = exporter
        self._buffer = buffer
        self._duration_seconds = duration_seconds
        self._trim_seconds = trim_seconds

    def run(self) -> None:
        try:
            path = self._exporter.export(self._buffer, self._duration_seconds, self._trim_seconds)
            if path:
                self.finished_ok.emit(path)
            else:
                self.failed.emit("No hay suficientes frames en el buffer para exportar.")
        except Exception as exc:  # noqa: BLE001 - reportar cualquier fallo de export al usuario
            logger.exception("Fallo exportando vídeo de postura")
            self.failed.emit(str(exc))


class PoseAnalysisWidget(QWidget):
    view_mode_changed = Signal(object)  # ViewMode
    handedness_changed = Signal(object)  # Handedness
    device_changed = Signal(object)  # int | None
    delay_changed = Signal(float)
    clip_duration_changed = Signal(float)
    trim_changed = Signal(float)
    output_folder_changed = Signal(str)
    sound_enabled_changed = Signal(bool)

    def __init__(self):
        super().__init__()
        self.view_mode = ViewMode.TRASERA
        self.handedness = Handedness.DIESTRO
        self.device_index: int | None = None
        self.delay_seconds = 0.0
        self.clip_duration_seconds = float(DEFAULT_CLIP_SECONDS)
        self.trim_seconds = 0.0
        self.output_folder = os.path.join(os.path.expanduser("~"), "ArcheryVision", "posturas")
        self.sound_enabled = False

        self.buffer = FrameRingBuffer(max_seconds=2.0, expected_fps=TARGET_FPS)
        self.pose_history = PoseResultHistory(max_seconds=2.0)
        self.worker: PoseWorker | None = None
        self._export_worker: PoseClipExportWorker | None = None
        self._last_overall_ok: bool | None = None

        self._sound_effect = QSoundEffect()
        self._sound_effect.setSource(QUrl.fromLocalFile(os.path.abspath(BEEP_PATH)))
        self._sound_effect.setVolume(0.6)

        # --- widgets ---
        self.video_label = VideoLabel()

        self.view_combo = QComboBox()
        for mode in ViewMode:
            self.view_combo.addItem(VIEW_MODE_LABELS[mode], mode)
        self.view_combo.currentIndexChanged.connect(self._on_view_changed)

        self.handedness_combo = QComboBox()
        for h in Handedness:
            self.handedness_combo.addItem(HANDEDNESS_LABELS[h], h)
        self.handedness_combo.currentIndexChanged.connect(self._on_handedness_changed)

        self.device_combo = QComboBox()
        self.device_combo.addItem(NO_DEVICE_LABEL, None)
        self.device_combo.currentIndexChanged.connect(self._on_device_changed)
        self.rescan_btn = QPushButton("Buscar cámaras")
        self.rescan_btn.clicked.connect(self.refresh_devices)

        self.delay_slider = QSlider(Qt.Horizontal)
        self.delay_slider.setRange(0, int(MAX_DELAY_SECONDS_POSE))
        self.delay_spin = QSpinBox()
        self.delay_spin.setRange(0, int(MAX_DELAY_SECONDS_POSE))
        self.delay_spin.setSuffix(" s")
        self.delay_slider.valueChanged.connect(self._on_delay_slider_changed)
        self.delay_spin.valueChanged.connect(self._on_delay_spin_changed)

        self.clip_duration_spin = QSpinBox()
        self.clip_duration_spin.setRange(MIN_CLIP_SECONDS, MAX_CLIP_SECONDS)
        self.clip_duration_spin.setValue(DEFAULT_CLIP_SECONDS)
        self.clip_duration_spin.setSuffix(" s")
        self.clip_duration_spin.valueChanged.connect(self._on_clip_duration_changed)

        self.trim_spin = QSpinBox()
        self.trim_spin.setRange(0, MAX_CLIP_SECONDS)
        self.trim_spin.setSuffix(" s")
        self.trim_spin.valueChanged.connect(self._on_trim_changed)

        self.sound_checkbox = QCheckBox("Aviso sonoro")
        self.sound_checkbox.toggled.connect(self._on_sound_toggled)

        self.output_folder_label = QLabel("Carpeta no seleccionada")
        self.output_folder_btn = QPushButton("Elegir carpeta de salida")
        self.output_folder_btn.clicked.connect(self._choose_output_folder)

        self.save_clip_btn = QPushButton("💾 Guardar clip")
        self.save_clip_btn.setStyleSheet("font-weight: bold; padding: 8px;")
        self.save_clip_btn.clicked.connect(self.save_clip)

        self.clip_status_label = QLabel("")
        self.clip_status_label.setWordWrap(True)
        self.clip_status_label.hide()

        self.status_panel = QLabel("Sin detección")
        self.status_panel.setWordWrap(True)
        self.status_panel.setStyleSheet("font-size: 16px; font-weight: bold; padding: 6px; color: gray;")

        # --- layout ---
        controls_box = QGroupBox("Controles")
        form = QVBoxLayout()

        view_row = QHBoxLayout()
        view_row.addWidget(QLabel("Vista:"))
        view_row.addWidget(self.view_combo)

        hand_row = QHBoxLayout()
        hand_row.addWidget(QLabel("Mano dominante:"))
        hand_row.addWidget(self.handedness_combo)

        device_row = QHBoxLayout()
        device_row.addWidget(QLabel("Cámara:"))
        device_row.addWidget(self.device_combo)

        delay_row = QHBoxLayout()
        delay_row.addWidget(QLabel("Delay:"))
        delay_row.addWidget(self.delay_slider)
        delay_row.addWidget(self.delay_spin)

        clip_duration_row = QHBoxLayout()
        clip_duration_row.addWidget(QLabel("Duración del clip:"))
        clip_duration_row.addWidget(self.clip_duration_spin)

        trim_row = QHBoxLayout()
        trim_row.addWidget(QLabel("Recortar final:"))
        trim_row.addWidget(self.trim_spin)

        form.addLayout(view_row)
        form.addLayout(hand_row)
        form.addLayout(device_row)
        form.addWidget(self.rescan_btn)
        form.addLayout(delay_row)
        form.addLayout(clip_duration_row)
        form.addLayout(trim_row)
        form.addWidget(self.sound_checkbox)
        form.addWidget(self.output_folder_btn)
        form.addWidget(self.output_folder_label)
        form.addWidget(self.save_clip_btn)
        form.addWidget(self.clip_status_label)
        controls_box.setLayout(form)

        status_box = QGroupBox("Estado de la postura")
        status_layout = QVBoxLayout()
        status_layout.addWidget(self.status_panel)
        status_box.setLayout(status_layout)

        side_panel = QVBoxLayout()
        side_panel.addWidget(controls_box)
        side_panel.addWidget(status_box)
        side_panel.addStretch()
        self.side_container = QWidget()
        self.side_container.setLayout(side_panel)

        main_layout = QHBoxLayout()
        main_layout.addWidget(self.video_label, 2)
        main_layout.addWidget(self.side_container, 1)
        self.setLayout(main_layout)

        self.display_timer = QTimer(self)
        self.display_timer.timeout.connect(self._update_display)

        self._clip_status_timer = QTimer(self)
        self._clip_status_timer.setSingleShot(True)
        self._clip_status_timer.timeout.connect(lambda: self._set_clip_status(""))

        self._update_buffer_size()

    # --- API pública usada por MainWindow ---

    def refresh_devices(self) -> None:
        devices = detect_available_cameras()
        current = self.device_combo.currentData()
        self.device_combo.blockSignals(True)
        self.device_combo.clear()
        self.device_combo.addItem(NO_DEVICE_LABEL, None)
        for dev in devices:
            self.device_combo.addItem(f"Dispositivo {dev}", dev)
        idx = self.device_combo.findData(current)
        self.device_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.device_combo.blockSignals(False)

    def start_capture(self) -> None:
        if self.device_index is None:
            return
        self._start_worker()
        self.display_timer.start(DISPLAY_REFRESH_MS)

    def stop_capture(self) -> None:
        self.display_timer.stop()
        self._stop_worker()
        self.video_label.setPixmap(QPixmap())
        self.video_label.setText(PLACEHOLDER_TEXT)
        self._last_overall_ok = None
        self.status_panel.setText("Sin detección")
        self.status_panel.setStyleSheet("font-size: 16px; font-weight: bold; padding: 6px; color: gray;")

    def set_controls_visible(self, visible: bool) -> None:
        self.side_container.setVisible(visible)

    def set_view_mode(self, view_mode: ViewMode) -> None:
        self.view_mode = view_mode
        self.view_combo.blockSignals(True)
        idx = self.view_combo.findData(view_mode)
        self.view_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.view_combo.blockSignals(False)

    def set_handedness(self, handedness: Handedness) -> None:
        self.handedness = handedness
        self.handedness_combo.blockSignals(True)
        idx = self.handedness_combo.findData(handedness)
        self.handedness_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.handedness_combo.blockSignals(False)

    def set_device(self, device_index: int | None) -> None:
        self.device_index = device_index
        idx = self.device_combo.findData(device_index)
        self.device_combo.blockSignals(True)
        self.device_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.device_combo.blockSignals(False)

    def set_delay(self, seconds: float) -> None:
        self.delay_seconds = seconds
        self.delay_slider.blockSignals(True)
        self.delay_spin.blockSignals(True)
        self.delay_slider.setValue(int(seconds))
        self.delay_spin.setValue(int(seconds))
        self.delay_slider.blockSignals(False)
        self.delay_spin.blockSignals(False)
        self._update_buffer_size()

    def set_clip_duration(self, seconds: float) -> None:
        self.clip_duration_seconds = seconds
        self.clip_duration_spin.blockSignals(True)
        self.clip_duration_spin.setValue(int(seconds))
        self.clip_duration_spin.blockSignals(False)
        self._update_buffer_size()

    def set_trim(self, seconds: float) -> None:
        self.trim_seconds = seconds
        self.trim_spin.blockSignals(True)
        self.trim_spin.setValue(int(seconds))
        self.trim_spin.blockSignals(False)
        self._update_buffer_size()

    def set_output_folder(self, folder: str) -> None:
        self.output_folder = folder
        self.output_folder_label.setText(folder)

    def set_sound_enabled(self, enabled: bool) -> None:
        self.sound_enabled = enabled
        self.sound_checkbox.blockSignals(True)
        self.sound_checkbox.setChecked(enabled)
        self.sound_checkbox.blockSignals(False)

    # --- internos ---

    def _start_worker(self) -> None:
        self._stop_worker()
        self.worker = PoseWorker(
            self.device_index, self.view_mode, self.handedness, self.buffer, self.pose_history
        )
        self.worker.error.connect(self._on_worker_error)
        self.worker.start()

    def _stop_worker(self) -> None:
        if self.worker is not None:
            self.worker.stop()
            self.worker = None

    def _on_worker_error(self, message: str) -> None:
        self.status_panel.setText(message)
        self.status_panel.setStyleSheet("font-size: 16px; font-weight: bold; padding: 6px; color: red;")

    def _on_view_changed(self, _index: int) -> None:
        mode = self.view_combo.currentData()
        self.view_mode = mode
        if self.worker is not None:
            self.worker.view_mode = mode
        self.view_mode_changed.emit(mode)

    def _on_handedness_changed(self, _index: int) -> None:
        handedness = self.handedness_combo.currentData()
        self.handedness = handedness
        if self.worker is not None:
            self.worker.handedness = handedness
        self.handedness_changed.emit(handedness)

    def _on_device_changed(self, _index: int) -> None:
        device_index = self.device_combo.currentData()
        self.device_index = device_index
        if self.display_timer.isActive():
            # la pestaña está activa: reiniciar la captura con la nueva cámara
            if device_index is None:
                self._stop_worker()
                self.video_label.setPixmap(QPixmap())
                self.video_label.setText(PLACEHOLDER_TEXT)
            else:
                self._start_worker()
        self.device_changed.emit(device_index)

    def _on_delay_slider_changed(self, value: int) -> None:
        self.delay_spin.blockSignals(True)
        self.delay_spin.setValue(value)
        self.delay_spin.blockSignals(False)
        self.delay_seconds = float(value)
        self._update_buffer_size()
        self.delay_changed.emit(self.delay_seconds)

    def _on_delay_spin_changed(self, value: int) -> None:
        self.delay_slider.blockSignals(True)
        self.delay_slider.setValue(value)
        self.delay_slider.blockSignals(False)
        self.delay_seconds = float(value)
        self._update_buffer_size()
        self.delay_changed.emit(self.delay_seconds)

    def _on_clip_duration_changed(self, value: int) -> None:
        self.clip_duration_seconds = float(value)
        self._update_buffer_size()
        self.clip_duration_changed.emit(self.clip_duration_seconds)

    def _on_trim_changed(self, value: int) -> None:
        self.trim_seconds = float(value)
        self._update_buffer_size()
        self.trim_changed.emit(self.trim_seconds)

    def _update_buffer_size(self) -> None:
        needed = max(self.delay_seconds, self.clip_duration_seconds + self.trim_seconds) + 2.0
        self.buffer.set_max_seconds(needed)
        self.pose_history.set_max_seconds(needed)

    def _on_sound_toggled(self, checked: bool) -> None:
        self.sound_enabled = checked
        self.sound_enabled_changed.emit(checked)

    def _choose_output_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Carpeta de salida de posturas")
        if folder:
            self.output_folder = folder
            self.output_folder_label.setText(folder)
            self.output_folder_changed.emit(folder)

    def _update_display(self) -> None:
        target_time = time.monotonic() - self.delay_seconds
        timed_frame = self.buffer.get_nearest(target_time)
        if timed_frame is not None:
            self.video_label.set_frame(timed_frame.frame, 0)

        result = self.pose_history.get_nearest(target_time)
        self._update_status_panel(result)
        self._maybe_play_sound(result)

    def _update_status_panel(self, result) -> None:
        if result is None:
            self.status_panel.setText("Sin detección")
            self.status_panel.setStyleSheet("font-size: 16px; font-weight: bold; padding: 6px; color: gray;")
        elif result.overall_ok:
            self.status_panel.setText("Postura correcta")
            self.status_panel.setStyleSheet("font-size: 16px; font-weight: bold; padding: 6px; color: green;")
        else:
            text = "\n".join(f.detail for f in result.findings if not f.ok)
            self.status_panel.setText(text)
            self.status_panel.setStyleSheet("font-size: 16px; font-weight: bold; padding: 6px; color: red;")

    def _maybe_play_sound(self, result) -> None:
        overall_ok = result.overall_ok if result is not None else None
        if self.sound_enabled and overall_ok is False and self._last_overall_ok is not False:
            self._sound_effect.play()
        self._last_overall_ok = overall_ok

    def _set_clip_status(self, message: str, level: str = "info") -> None:
        colors = {"info": "gray", "success": "green", "error": "red"}
        self.clip_status_label.setStyleSheet(f"color: {colors.get(level, 'gray')};")
        self.clip_status_label.setText(message)
        self.clip_status_label.setVisible(bool(message))
        if message:
            self._clip_status_timer.start(8000)

    def save_clip(self) -> None:
        if self._export_worker is not None and self._export_worker.isRunning():
            self._set_clip_status("Ya se está exportando un vídeo.", "info")
            return
        exporter = PoseClipExporter(self.output_folder)
        self._export_worker = PoseClipExportWorker(
            exporter, self.buffer, self.clip_duration_seconds, self.trim_seconds
        )
        self._export_worker.finished_ok.connect(self._on_export_finished)
        self._export_worker.failed.connect(self._on_export_failed)
        self._export_worker.start()
        self._set_clip_status("Exportando vídeo…")

    def _on_export_finished(self, path: str) -> None:
        self._set_clip_status(f"Vídeo exportado correctamente: {path}", "success")

    def _on_export_failed(self, message: str) -> None:
        self._set_clip_status(f"Error al exportar: {message}", "error")
