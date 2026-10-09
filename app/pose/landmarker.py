"""Envoltorio fino sobre MediaPipe Tasks PoseLandmarker (modo VIDEO)."""

import os

import cv2
import numpy as np
from mediapipe.tasks.python.core import base_options as base_options_lib
from mediapipe.tasks.python.vision import pose_landmarker as pose_landmarker_lib
from mediapipe.tasks.python.vision.core import image as image_lib
from mediapipe.tasks.python.vision.core import (
    vision_task_running_mode as running_mode_lib,
)

MODEL_PATH = os.path.join(os.path.dirname(__file__), "models", "pose_landmarker_lite.task")

PoseLandmarkerResult = pose_landmarker_lib.PoseLandmarkerResult


class PoseLandmarker:
    """Detección de pose en modo VIDEO: síncrono y ordenado por timestamp,
    pensado para invocarse una vez por frame dentro de un único hilo
    (evita la complejidad de los callbacks asíncronos del modo LIVE_STREAM).
    """

    def __init__(self, model_path: str = MODEL_PATH, num_poses: int = 1):
        base_options = base_options_lib.BaseOptions(model_asset_path=model_path)
        options = pose_landmarker_lib.PoseLandmarkerOptions(
            base_options=base_options,
            running_mode=running_mode_lib.VisionTaskRunningMode.VIDEO,
            num_poses=num_poses,
        )
        self._landmarker = pose_landmarker_lib.PoseLandmarker.create_from_options(options)

    def detect(self, frame_bgr: np.ndarray, timestamp_ms: int) -> PoseLandmarkerResult:
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        mp_image = image_lib.Image(image_format=image_lib.ImageFormat.SRGB, data=rgb)
        return self._landmarker.detect_for_video(mp_image, timestamp_ms)

    def close(self) -> None:
        self._landmarker.close()
