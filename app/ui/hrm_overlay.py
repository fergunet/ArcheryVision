"""Monitorización de pulsaciones en el panel de control (RF-4.2, RF-4.3)."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGroupBox, QHBoxLayout, QLabel, QVBoxLayout

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


class HRMPanel(QGroupBox):
    def __init__(self, parent=None):
        super().__init__("Pulsaciones", parent)

        self.bpm_label = QLabel("-- bpm")
        self.bpm_label.setAlignment(Qt.AlignCenter)
        self.bpm_label.setStyleSheet("font-size: 40px; font-weight: bold;")

        self.status_label = QLabel(STATUS_DISCONNECTED)
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("font-size: 14px;")
        self._apply_status_color(STATUS_DISCONNECTED)

        heart_label = QLabel("♥")
        heart_label.setStyleSheet("font-size: 40px; color: #e74c3c;")
        heart_label.setAlignment(Qt.AlignCenter)

        bpm_row = QHBoxLayout()
        bpm_row.addWidget(heart_label)
        bpm_row.addWidget(self.bpm_label)

        layout = QVBoxLayout()
        layout.addLayout(bpm_row)
        layout.addWidget(self.status_label)
        self.setLayout(layout)

    def set_bpm(self, bpm: int) -> None:
        self.bpm_label.setText(f"{bpm} bpm")

    def set_status(self, status: str) -> None:
        self.status_label.setText(status)
        self._apply_status_color(status)
        if status != STATUS_CONNECTED:
            self.bpm_label.setText("-- bpm")

    def _apply_status_color(self, status: str) -> None:
        color = _STATUS_COLORS.get(status, "#95a5a6")
        self.status_label.setStyleSheet(f"font-size: 14px; color: {color}; font-weight: bold;")
