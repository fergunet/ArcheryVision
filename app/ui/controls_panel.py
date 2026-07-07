"""Panel de control: selección de cámara por slot, delay, Play/Pause y clip.

RF-1.1 Selección de cámara por slot.
RF-2.2 Delay configurable por cámara (0-60 s).
RF-5.1 / RF-5.2 Botón de guardar clip y duración configurable (5-60 s).
"""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt

from app.camera.manager import MAX_CAMERAS, MAX_DELAY_SECONDS
from app.ui.hrm_overlay import HRMPanel

NO_DEVICE_LABEL = "-- Sin cámara --"
MIN_CLIP_SECONDS = 5
MAX_CLIP_SECONDS = 60
DEFAULT_CLIP_SECONDS = 10


class SlotControl(QGroupBox):
    device_changed = Signal(int, object)  # slot_index, device_index|None
    delay_changed = Signal(int, float)  # slot_index, seconds
    name_changed = Signal(int, str)  # slot_index, name

    def __init__(self, slot_index: int):
        super().__init__(f"Cámara {slot_index + 1}")
        self.slot_index = slot_index

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText(f"Cámara {slot_index + 1}")
        self.name_edit.editingFinished.connect(self._on_name_edited)

        self.device_combo = QComboBox()
        self.device_combo.addItem(NO_DEVICE_LABEL, None)
        self.device_combo.currentIndexChanged.connect(self._on_device_changed)

        self.delay_slider = QSlider(Qt.Horizontal)
        self.delay_slider.setRange(0, int(MAX_DELAY_SECONDS))
        self.delay_slider.setSingleStep(1)
        self.delay_spin = QSpinBox()
        self.delay_spin.setRange(0, int(MAX_DELAY_SECONDS))
        self.delay_spin.setSuffix(" s")

        self.delay_slider.valueChanged.connect(self._on_slider_changed)
        self.delay_spin.valueChanged.connect(self._on_spin_changed)

        self.status_label = QLabel("Desconectada")
        self.status_label.setStyleSheet("color: gray;")

        delay_row = QHBoxLayout()
        delay_row.addWidget(QLabel("Delay:"))
        delay_row.addWidget(self.delay_slider)
        delay_row.addWidget(self.delay_spin)

        layout = QVBoxLayout()
        layout.addWidget(self.name_edit)
        layout.addWidget(self.device_combo)
        layout.addLayout(delay_row)
        layout.addWidget(self.status_label)
        self.setLayout(layout)

    def set_name(self, name: str) -> None:
        self.name_edit.blockSignals(True)
        self.name_edit.setText(name)
        self.name_edit.blockSignals(False)

    def set_delay(self, seconds: float) -> None:
        self.delay_slider.blockSignals(True)
        self.delay_spin.blockSignals(True)
        self.delay_slider.setValue(int(seconds))
        self.delay_spin.setValue(int(seconds))
        self.delay_slider.blockSignals(False)
        self.delay_spin.blockSignals(False)

    def _on_name_edited(self) -> None:
        self.name_changed.emit(self.slot_index, self.name_edit.text())

    def set_device(self, device_index: int | None) -> None:
        idx = self.device_combo.findData(device_index)
        self.device_combo.blockSignals(True)
        self.device_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.device_combo.blockSignals(False)

    def set_available_devices(self, devices: list[int]) -> None:
        current = self.device_combo.currentData()
        self.device_combo.blockSignals(True)
        self.device_combo.clear()
        self.device_combo.addItem(NO_DEVICE_LABEL, None)
        for dev in devices:
            self.device_combo.addItem(f"Dispositivo {dev}", dev)
        idx = self.device_combo.findData(current)
        self.device_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.device_combo.blockSignals(False)

    def set_status(self, connected: bool) -> None:
        if connected:
            self.status_label.setText("Conectada")
            self.status_label.setStyleSheet("color: green;")
        else:
            self.status_label.setText("Desconectada")
            self.status_label.setStyleSheet("color: gray;")

    def _on_device_changed(self, _index: int) -> None:
        self.device_changed.emit(self.slot_index, self.device_combo.currentData())

    def _on_slider_changed(self, value: int) -> None:
        self.delay_spin.blockSignals(True)
        self.delay_spin.setValue(value)
        self.delay_spin.blockSignals(False)
        self.delay_changed.emit(self.slot_index, float(value))

    def _on_spin_changed(self, value: int) -> None:
        self.delay_slider.blockSignals(True)
        self.delay_slider.setValue(value)
        self.delay_slider.blockSignals(False)
        self.delay_changed.emit(self.slot_index, float(value))


class ControlsPanel(QWidget):
    device_changed = Signal(int, object)
    delay_changed = Signal(int, float)
    name_changed = Signal(int, str)
    play_clicked = Signal()
    pause_clicked = Signal()
    rescan_clicked = Signal()
    save_clip_clicked = Signal()
    clip_duration_changed = Signal(int)
    clip_trim_changed = Signal(int)
    output_folder_changed = Signal(str)
    reset_config_clicked = Signal()

    def __init__(self):
        super().__init__()
        self.slot_controls: list[SlotControl] = []

        self.hrm_panel = HRMPanel()

        grid = QGridLayout()
        for i in range(MAX_CAMERAS):
            slot = SlotControl(i)
            slot.device_changed.connect(self.device_changed)
            slot.delay_changed.connect(self.delay_changed)
            slot.name_changed.connect(self.name_changed)
            self.slot_controls.append(slot)
            grid.addWidget(slot, i // 2, i % 2)

        self.rescan_btn = QPushButton("Buscar cámaras")
        self.rescan_btn.clicked.connect(self.rescan_clicked)

        self.play_btn = QPushButton("▶ Play")
        self.pause_btn = QPushButton("⏸ Pause")
        self.play_btn.clicked.connect(self.play_clicked)
        self.pause_btn.clicked.connect(self.pause_clicked)

        playback_row = QHBoxLayout()
        playback_row.addWidget(self.play_btn)
        playback_row.addWidget(self.pause_btn)

        self.clip_duration_spin = QSpinBox()
        self.clip_duration_spin.setRange(MIN_CLIP_SECONDS, MAX_CLIP_SECONDS)
        self.clip_duration_spin.setValue(DEFAULT_CLIP_SECONDS)
        self.clip_duration_spin.setSuffix(" s")
        self.clip_duration_spin.valueChanged.connect(self.clip_duration_changed)

        self.clip_trim_spin = QSpinBox()
        self.clip_trim_spin.setRange(0, MAX_CLIP_SECONDS)
        self.clip_trim_spin.setValue(0)
        self.clip_trim_spin.setSuffix(" s")
        self.clip_trim_spin.valueChanged.connect(self.clip_trim_changed)

        self.output_folder_label = QLabel("Carpeta no seleccionada")
        self.output_folder_btn = QPushButton("Elegir carpeta de salida")
        self.output_folder_btn.clicked.connect(self._choose_output_folder)

        self.save_clip_btn = QPushButton("💾 Guardar clip")
        self.save_clip_btn.setStyleSheet("font-weight: bold; padding: 8px;")
        self.save_clip_btn.clicked.connect(self.save_clip_clicked)

        clip_row = QHBoxLayout()
        clip_row.addWidget(QLabel("Duración del clip:"))
        clip_row.addWidget(self.clip_duration_spin)

        trim_row = QHBoxLayout()
        trim_row.addWidget(QLabel("Recortar final:"))
        trim_row.addWidget(self.clip_trim_spin)

        self.reset_config_btn = QPushButton("Resetear configuración")
        self.reset_config_btn.setStyleSheet("color: red;")
        self.reset_config_btn.clicked.connect(self.reset_config_clicked)

        layout = QVBoxLayout()
        layout.addWidget(self.hrm_panel)
        layout.addWidget(self.rescan_btn)
        layout.addLayout(grid)
        layout.addLayout(playback_row)
        layout.addLayout(clip_row)
        layout.addLayout(trim_row)
        layout.addWidget(self.output_folder_btn)
        layout.addWidget(self.output_folder_label)
        layout.addWidget(self.save_clip_btn)
        layout.addStretch()
        layout.addWidget(self.reset_config_btn)
        self.setLayout(layout)

    def update_available_devices(self, devices: list[int]) -> None:
        for slot in self.slot_controls:
            slot.set_available_devices(devices)

    def set_slot_status(self, slot_index: int, connected: bool) -> None:
        self.slot_controls[slot_index].set_status(connected)

    def set_slot_name(self, slot_index: int, name: str) -> None:
        self.slot_controls[slot_index].set_name(name)

    def set_slot_delay(self, slot_index: int, seconds: float) -> None:
        self.slot_controls[slot_index].set_delay(seconds)

    def set_slot_device(self, slot_index: int, device_index: int | None) -> None:
        self.slot_controls[slot_index].set_device(device_index)

    def _choose_output_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Carpeta de salida de clips")
        if folder:
            self.output_folder_label.setText(folder)
            self.output_folder_changed.emit(folder)
