"""Ventana flotante de cámara dentro del QMdiArea.

RF-3.1 Ventanas flotantes y arrastrables (delegado en QMdiSubWindow).
RF-3.2 Redimensionado manteniendo relación de aspecto (letterbox en el render).
RF-3.3 Rotación en incrementos de 90°.
"""

import cv2
import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QImage, QPixmap, QTransform
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMdiSubWindow,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

PLACEHOLDER_TEXT = "Sin señal"


def _bgr_to_qpixmap(frame: np.ndarray) -> QPixmap:
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    h, w, _ = rgb.shape
    image = QImage(rgb.data, w, h, rgb.strides[0], QImage.Format_RGB888)
    return QPixmap.fromImage(image.copy())


class VideoLabel(QLabel):
    """Renderiza el frame actual manteniendo la relación de aspecto
    (letterbox) sea cual sea el tamaño al que se redimensione la ventana."""

    def __init__(self):
        super().__init__()
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("background-color: black; color: #888;")
        self.setMinimumSize(160, 90)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._source_pixmap: QPixmap | None = None
        self.setText(PLACEHOLDER_TEXT)

    def set_frame(self, frame: np.ndarray, rotation_degrees: int) -> None:
        pixmap = _bgr_to_qpixmap(frame)
        if rotation_degrees:
            pixmap = pixmap.transformed(QTransform().rotate(rotation_degrees))
        self._source_pixmap = pixmap
        self._refresh_scaled()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._refresh_scaled()

    def _refresh_scaled(self) -> None:
        if self._source_pixmap is None:
            return
        scaled = self._source_pixmap.scaled(
            self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        self.setPixmap(scaled)


class CameraViewWidget(QWidget):
    rotation_changed = Signal(int, int)

    def __init__(self, slot_index: int):
        super().__init__()
        self.slot_index = slot_index
        self.rotation_degrees = 0

        self.video_label = VideoLabel()

        rotate_left_btn = QPushButton("⟲ 90°")
        rotate_right_btn = QPushButton("⟳ 90°")
        rotate_left_btn.clicked.connect(lambda: self.rotate(-90))
        rotate_right_btn.clicked.connect(lambda: self.rotate(90))

        toolbar = QHBoxLayout()
        toolbar.addWidget(rotate_left_btn)
        toolbar.addWidget(rotate_right_btn)
        toolbar.addStretch()

        toolbar_frame = QFrame()
        toolbar_frame.setLayout(toolbar)
        toolbar_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        layout = QVBoxLayout()
        layout.setContentsMargins(2, 2, 2, 2)
        layout.addWidget(toolbar_frame, 0)
        layout.addWidget(self.video_label, 1)
        self.setLayout(layout)

        self._last_frame: np.ndarray | None = None

    def rotate(self, delta_degrees: int) -> None:
        self.rotation_degrees = (self.rotation_degrees + delta_degrees) % 360
        if self._last_frame is not None:
            self.video_label.set_frame(self._last_frame, self.rotation_degrees)
        self.rotation_changed.emit(self.slot_index, self.rotation_degrees)

    def set_rotation(self, degrees: int) -> None:
        """Fija la rotación sin emitir rotation_changed (restauración inicial)."""
        self.rotation_degrees = degrees % 360
        if self._last_frame is not None:
            self.video_label.set_frame(self._last_frame, self.rotation_degrees)

    def display_frame(self, frame: np.ndarray) -> None:
        self._last_frame = frame
        self.video_label.set_frame(frame, self.rotation_degrees)

    def clear(self) -> None:
        self._last_frame = None
        self.video_label.setPixmap(QPixmap())
        self.video_label.setText(PLACEHOLDER_TEXT)


class CameraSubWindow(QMdiSubWindow):
    """Ventana flotante de cámara.

    Recuerda su última geometría "normal" (no maximizada) para que, al
    restaurar la sesión, una ventana maximizada se pueda volver a
    maximizar y, si el usuario la desmaximiza luego, recupere un tamaño
    sensato en vez del que tuviera por casualidad en ese instante.
    """

    def __init__(self, slot_index: int, title: str):
        super().__init__()
        self.slot_index = slot_index
        self.view = CameraViewWidget(slot_index)
        self.setWidget(self.view)
        self.setWindowTitle(title)
        self.resize(480, 320)
        self._normal_geometry = self.geometry()

    @property
    def normal_geometry(self):
        return self._normal_geometry

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if not self.isMaximized():
            self._normal_geometry = self.geometry()

    def moveEvent(self, event) -> None:
        super().moveEvent(event)
        if not self.isMaximized():
            self._normal_geometry = self.geometry()
