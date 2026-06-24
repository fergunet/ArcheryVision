"""Overlay permanente de pulsaciones (RF-4.2, RF-4.3)."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from app.hrm.ble_client import (
    STATUS_BLE_UNAVAILABLE,
    STATUS_CONNECTED,
    STATUS_DISCONNECTED,
    STATUS_SCANNING,
)

_STATUS_COLORS = {
    STATUS_CONNECTED: "#2ecc71",
    STATUS_SCANNING: "#f1c40f",
    STATUS_DISCONNECTED: "#95a5a6",
    STATUS_BLE_UNAVAILABLE: "#e74c3c",
}


class HRMOverlay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(
            "background-color: rgba(0, 0, 0, 160); border-radius: 6px;"
        )

        self.bpm_label = QLabel("-- bpm")
        self.bpm_label.setStyleSheet("color: white; font-size: 20px; font-weight: bold;")

        self.status_label = QLabel(STATUS_DISCONNECTED)
        self._apply_status_color(STATUS_DISCONNECTED)

        layout = QHBoxLayout()
        layout.setContentsMargins(10, 6, 10, 6)
        layout.addWidget(QLabel("♥"))
        layout.addWidget(self.bpm_label)
        layout.addWidget(self.status_label)
        self.setLayout(layout)
        self.adjustSize()

    def set_bpm(self, bpm: int) -> None:
        self.bpm_label.setText(f"{bpm} bpm")

    def set_status(self, status: str) -> None:
        self.status_label.setText(status)
        self._apply_status_color(status)
        if status != STATUS_CONNECTED:
            self.bpm_label.setText("-- bpm")

    def _apply_status_color(self, status: str) -> None:
        color = _STATUS_COLORS.get(status, "#95a5a6")
        self.status_label.setStyleSheet(f"color: {color}; font-weight: bold;")
