"""Exportación de clip de una única cámara con el esqueleto ya superpuesto
(RF 3.5 de requisitos_modulo_vision.md).

Los frames del buffer ya llevan el overlay dibujado (ver PoseWorker), así
que aquí solo hace falta volcarlos a disco con cv2.VideoWriter — sin la
composición 2x2 de app/recording/exporter.py, porque este módulo trabaja
con una única cámara.
"""

import logging
import os
import time

import cv2

from app.camera.buffer import FrameRingBuffer
from app.pose.worker import TARGET_FPS

logger = logging.getLogger(__name__)


class PoseClipExporter:
    def __init__(self, output_folder: str):
        self.output_folder = output_folder

    def export(
        self, buffer: FrameRingBuffer, duration_seconds: float, trim_seconds: float = 0.0
    ) -> str | None:
        reference_time = time.monotonic() - trim_seconds
        frames = buffer.get_last_seconds(duration_seconds, reference_time)
        if not frames:
            logger.warning("No hay frames en el buffer para exportar")
            return None

        os.makedirs(self.output_folder, exist_ok=True)
        filename = f"postura_{time.strftime('%Y%m%d_%H%M%S')}.mp4"
        output_path = os.path.join(self.output_folder, filename)

        height, width = frames[0].frame.shape[:2]
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(output_path, fourcc, TARGET_FPS, (width, height))
        try:
            for timed_frame in frames:
                writer.write(timed_frame.frame)
        finally:
            writer.release()

        logger.info("Clip de postura exportado: %s", output_path)
        return output_path
