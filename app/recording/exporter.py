"""Exportación de clip compuesto 2x2 respetando delay y rotación (RF-5).

RF-5.1 Botón de guardar clip -> exporta los últimos X segundos de todas
       las cámaras activas simultáneamente.
RF-5.2 Duración configurable (5-60 s).
RF-5.3 Clip compuesto 2x2 sincronizado (sin delays) respetando rotaciones.
"""

import logging
import os
import time

import cv2
import numpy as np

from app.camera.manager import CameraSlot, TARGET_FPS
from app.hrm.history import BpmHistory

logger = logging.getLogger(__name__)

CELL_WIDTH = 640
CELL_HEIGHT = 360


def _rotate_frame(frame: np.ndarray, degrees: int) -> np.ndarray:
    degrees = degrees % 360
    if degrees == 90:
        return cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
    if degrees == 180:
        return cv2.rotate(frame, cv2.ROTATE_180)
    if degrees == 270:
        return cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
    return frame


def _fit_letterbox(frame: np.ndarray, width: int, height: int) -> np.ndarray:
    canvas = np.zeros((height, width, 3), dtype=np.uint8)
    fh, fw = frame.shape[:2]
    if fh == 0 or fw == 0:
        return canvas
    scale = min(width / fw, height / fh)
    new_w, new_h = max(int(fw * scale), 1), max(int(fh * scale), 1)
    resized = cv2.resize(frame, (new_w, new_h))
    x_off = (width - new_w) // 2
    y_off = (height - new_h) // 2
    canvas[y_off : y_off + new_h, x_off : x_off + new_w] = resized
    return canvas


def _draw_overlay(frame: np.ndarray, wall_time: float, bpm: int | None) -> None:
    timestamp_text = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(wall_time))
    bpm_text = f"{bpm} bpm" if bpm is not None else "-- bpm"
    text = f"{timestamp_text}   {bpm_text}"

    font, scale, thickness = cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2
    (text_w, text_h), baseline = cv2.getTextSize(text, font, scale, thickness)
    pad = 8
    cv2.rectangle(frame, (0, 0), (text_w + pad * 2, text_h + baseline + pad * 2), (0, 0, 0), -1)
    cv2.putText(
        frame, text, (pad, text_h + pad), font, scale, (255, 255, 255), thickness, cv2.LINE_AA
    )


def _blank_cell(width: int, height: int, text: str) -> np.ndarray:
    canvas = np.zeros((height, width, 3), dtype=np.uint8)
    cv2.putText(
        canvas,
        text,
        (20, height // 2),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.0,
        (120, 120, 120),
        2,
        cv2.LINE_AA,
    )
    return canvas


class ClipExporter:
    def __init__(self, output_folder: str):
        self.output_folder = output_folder

    def export(
        self,
        slots: list[CameraSlot],
        duration_seconds: float,
        trim_seconds: float,
        bpm_history: BpmHistory,
        wall_clock_ref: tuple[float, float],
    ) -> str | None:
        active_slots = [s for s in slots if s.is_connected and not s.buffer.is_empty()]
        if not active_slots:
            logger.warning("No hay cámaras activas para exportar el clip")
            return None

        os.makedirs(self.output_folder, exist_ok=True)
        reference_time = time.monotonic() - trim_seconds
        fps = TARGET_FPS
        n_frames = max(int(duration_seconds * fps), 1)
        mono_ref, wall_ref = wall_clock_ref

        filename = f"clip_{time.strftime('%Y%m%d_%H%M%S')}.mp4"
        output_path = os.path.join(self.output_folder, filename)

        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        grid_w, grid_h = CELL_WIDTH * 2, CELL_HEIGHT * 2
        writer = cv2.VideoWriter(output_path, fourcc, fps, (grid_w, grid_h))

        try:
            for i in range(n_frames):
                sample_time = reference_time - duration_seconds + (i / fps)
                cells = []
                for slot in slots:
                    cells.append(self._render_cell(slot, sample_time))
                grid_frame = np.vstack(
                    [np.hstack(cells[0:2]), np.hstack(cells[2:4])]
                )
                wall_time = wall_ref + (sample_time - mono_ref)
                bpm = bpm_history.get_nearest(sample_time)
                _draw_overlay(grid_frame, wall_time, bpm)
                writer.write(grid_frame)
        finally:
            writer.release()

        logger.info("Clip exportado: %s", output_path)
        return output_path

    def _render_cell(self, slot: CameraSlot, sample_time: float) -> np.ndarray:
        if not slot.is_connected or slot.buffer.is_empty():
            return _blank_cell(CELL_WIDTH, CELL_HEIGHT, "Sin señal")

        timed_frame = slot.buffer.get_nearest(sample_time)
        if timed_frame is None:
            return _blank_cell(CELL_WIDTH, CELL_HEIGHT, "Sin datos")

        frame = _rotate_frame(timed_frame.frame, slot.rotation_degrees)
        return _fit_letterbox(frame, CELL_WIDTH, CELL_HEIGHT)
