"""Hilo de captura + inferencia de pose para una única cámara (RF 3.2/3.3 de
requisitos_modulo_vision.md). Sigue el mismo patrón que CameraWorker
(app/camera/manager.py): un único QThread hace cap.read() en bucle; aquí
además ejecuta la detección de pose, el análisis de postura y dibuja el
esqueleto anotado directamente sobre el frame antes de guardarlo en el
buffer, para que ese mismo buffer sirva tanto a la vista con delay como a
la grabación sin tener que recalcular el overlay al exportar.
"""

import logging
import time

import cv2
from PySide6.QtCore import QThread, Signal

from app.camera.buffer import FrameRingBuffer
from app.pose.analysis import PoseAnalysisResult, analyze
from app.pose.history import PoseResultHistory
from app.pose.landmarker import PoseLandmarker
from app.pose.overlay import draw_skeleton
from app.pose.view_modes import Handedness, ViewMode

logger = logging.getLogger(__name__)

CAPTURE_WIDTH = 640
CAPTURE_HEIGHT = 480
TARGET_FPS = 20.0


class PoseWorker(QThread):
    error = Signal(str)
    result_ready = Signal(object)  # PoseAnalysisResult | None

    def __init__(
        self,
        device_index: int,
        view_mode: ViewMode,
        handedness: Handedness,
        buffer: FrameRingBuffer,
        pose_history: PoseResultHistory,
    ):
        super().__init__()
        self.device_index = device_index
        self.view_mode = view_mode
        self.handedness = handedness
        self.buffer = buffer
        self.pose_history = pose_history
        self._running = False

    def run(self) -> None:
        cap = cv2.VideoCapture(self.device_index, cv2.CAP_ANY)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAPTURE_WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAPTURE_HEIGHT)
        cap.set(cv2.CAP_PROP_FPS, TARGET_FPS)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        if not cap.isOpened():
            self.error.emit(f"No se pudo abrir la cámara {self.device_index}")
            return

        landmarker = PoseLandmarker()
        self._running = True
        try:
            while self._running:
                ok, frame = cap.read()
                if not ok:
                    self.error.emit("Pérdida de señal de la cámara")
                    time.sleep(0.2)
                    continue

                ts = time.monotonic()
                timestamp_ms = int(ts * 1000)

                try:
                    detection = landmarker.detect(frame, timestamp_ms)
                    people = detection.pose_landmarks
                except Exception:  # noqa: BLE001 - una detección fallida no debe tumbar el hilo
                    logger.exception("Fallo detectando pose")
                    people = []

                landmarks = people[0] if people else None
                analysis_result: PoseAnalysisResult | None = (
                    analyze(landmarks, self.view_mode, self.handedness) if landmarks else None
                )

                annotated = frame.copy()
                draw_skeleton(annotated, landmarks, analysis_result)

                self.buffer.push(ts, annotated)
                self.pose_history.push(ts, analysis_result)
                self.result_ready.emit(analysis_result)
        finally:
            landmarker.close()
            cap.release()

    def stop(self) -> None:
        self._running = False
        self.wait(2000)
