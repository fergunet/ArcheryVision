"""Detección de cámaras USB y captura continua a buffers circulares.

RF-1.1 Detección y conexión de cámaras USB.
RF-1.2 Visualización simultánea de 4 streams con baja latencia.
RNF-1  Rendimiento: 4 streams >= 30 fps, resolución mínima 720p.
"""

import logging
import time

import cv2
from PySide6.QtCore import QThread, Signal

from app.camera.buffer import FrameRingBuffer

logger = logging.getLogger(__name__)

MAX_CAMERAS = 4
MAX_DELAY_SECONDS = 60.0
TARGET_FPS = 30.0
TARGET_WIDTH = 1280
TARGET_HEIGHT = 720
MAX_PROBE_INDEX = 10


def detect_available_cameras(max_probe_index: int = MAX_PROBE_INDEX) -> list[int]:
    """Prueba índices de dispositivo y devuelve los que abren correctamente,
    hasta un máximo de MAX_CAMERAS (RF-1.1)."""
    found: list[int] = []
    for index in range(max_probe_index):
        if len(found) >= MAX_CAMERAS:
            break
        cap = cv2.VideoCapture(index, cv2.CAP_ANY)
        try:
            if cap.isOpened():
                ok, _ = cap.read()
                if ok:
                    found.append(index)
        finally:
            cap.release()
    return found


class CameraWorker(QThread):
    """Hilo de captura continua para una cámara física. Llena el buffer
    circular independientemente de que la reproducción esté en Play o
    Pause, para que el delay configurado siempre tenga histórico disponible.
    """

    frame_ready = Signal(int)
    error = Signal(int, str)
    fps_measured = Signal(int, float)

    def __init__(self, slot_index: int, device_index: int, buffer: FrameRingBuffer):
        super().__init__()
        self.slot_index = slot_index
        self.device_index = device_index
        self.buffer = buffer
        self._running = False

    def run(self) -> None:
        cap = cv2.VideoCapture(self.device_index, cv2.CAP_ANY)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, TARGET_WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, TARGET_HEIGHT)
        cap.set(cv2.CAP_PROP_FPS, TARGET_FPS)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # minimiza latencia de captura

        if not cap.isOpened():
            self.error.emit(self.slot_index, f"No se pudo abrir la cámara {self.device_index}")
            return

        self._running = True
        frame_count = 0
        window_start = time.monotonic()
        try:
            while self._running:
                ok, frame = cap.read()
                if not ok:
                    self.error.emit(self.slot_index, "Pérdida de señal de la cámara")
                    time.sleep(0.2)
                    continue
                ts = time.monotonic()
                self.buffer.push(ts, frame)
                self.frame_ready.emit(self.slot_index)

                frame_count += 1
                elapsed = ts - window_start
                if elapsed >= 2.0:
                    self.fps_measured.emit(self.slot_index, frame_count / elapsed)
                    frame_count = 0
                    window_start = ts
        finally:
            cap.release()

    def stop(self) -> None:
        self._running = False
        self.wait(2000)


class CameraSlot:
    """Asociación lógica entre un slot de vista (0..3) y un dispositivo USB."""

    def __init__(self, slot_index: int):
        self.slot_index = slot_index
        self.device_index: int | None = None
        self.name = f"Cámara {slot_index + 1}"
        self.delay_seconds: float = 0.0
        self.rotation_degrees: int = 0
        self.buffer = FrameRingBuffer(max_seconds=MAX_DELAY_SECONDS, expected_fps=TARGET_FPS)
        self.worker: CameraWorker | None = None

    @property
    def is_connected(self) -> bool:
        return self.worker is not None and self.worker.isRunning()


class CameraManager:
    """Gestiona hasta MAX_CAMERAS slots, cada uno con su worker de captura."""

    def __init__(self):
        self.slots: list[CameraSlot] = [CameraSlot(i) for i in range(MAX_CAMERAS)]

    def available_devices(self) -> list[int]:
        """Dispositivos detectables más los ya asignados a un slot activo.

        Una cámara en uso por un CameraWorker no se puede volver a abrir
        para probarla (el sistema operativo bloquea el acceso exclusivo),
        así que el sondeo la descartaría aunque siga conectada. Se añaden
        de vuelta los dispositivos ya conectados para no perderlos del
        desplegable al pulsar "Buscar cámaras".
        """
        probed = set(detect_available_cameras())
        connected = {
            slot.device_index
            for slot in self.slots
            if slot.is_connected and slot.device_index is not None
        }
        return sorted(probed | connected)

    def assign_device(self, slot_index: int, device_index: int | None) -> CameraSlot:
        slot = self.slots[slot_index]
        self.disconnect_slot(slot_index)
        slot.device_index = device_index
        if device_index is not None:
            slot.worker = CameraWorker(slot_index, device_index, slot.buffer)
            slot.worker.start()
        return slot

    def disconnect_slot(self, slot_index: int) -> None:
        slot = self.slots[slot_index]
        if slot.worker is not None:
            slot.worker.stop()
            slot.worker = None

    def shutdown(self) -> None:
        for i in range(len(self.slots)):
            self.disconnect_slot(i)
