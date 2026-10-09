"""Dibuja el esqueleto coloreado y el panel de estado sobre el frame
(RF 3.2/3.3 de requisitos_modulo_vision.md)."""

import cv2
from mediapipe.tasks.python.vision import pose_landmarker as pose_landmarker_lib

from app.pose.analysis import PoseAnalysisResult

POSE_CONNECTIONS = [
    (c.start, c.end) for c in pose_landmarker_lib.PoseLandmarksConnections.POSE_LANDMARKS
]

COLOR_OK = (0, 200, 0)  # verde (BGR)
COLOR_ERROR = (0, 0, 220)  # rojo (BGR)


def draw_skeleton(frame, landmarks, analysis_result: PoseAnalysisResult | None) -> None:
    """Dibuja el esqueleto (coloreado en verde/rojo por hallazgo) y el panel
    de texto con el estado de la postura directamente sobre `frame`
    (mutación in-place). `landmarks` son los normalizados de imagen
    (result.pose_landmarks[0]) o None si no se detectó a nadie."""
    if not landmarks:
        draw_placeholder(frame, "Sin detección")
        return

    height, width = frame.shape[:2]
    points = [(int(lm.x * width), int(lm.y * height)) for lm in landmarks]

    bad_indices: set[int] = set()
    if analysis_result is not None:
        for finding in analysis_result.findings:
            if not finding.ok:
                bad_indices.update(finding.landmark_indices)

    for start, end in POSE_CONNECTIONS:
        if start >= len(points) or end >= len(points):
            continue
        color = COLOR_ERROR if (start in bad_indices or end in bad_indices) else COLOR_OK
        cv2.line(frame, points[start], points[end], color, 3, cv2.LINE_AA)

    for idx, (x, y) in enumerate(points):
        color = COLOR_ERROR if idx in bad_indices else COLOR_OK
        cv2.circle(frame, (x, y), 4, color, -1, cv2.LINE_AA)

    _draw_status_panel(frame, analysis_result)


def _draw_status_panel(frame, analysis_result: PoseAnalysisResult | None) -> None:
    if analysis_result is None:
        lines = ["Sin detección"]
        ok = False
    elif analysis_result.overall_ok:
        lines = ["Postura correcta"]
        ok = True
    else:
        lines = [f.detail for f in analysis_result.findings if not f.ok]
        ok = False

    font, scale, thickness = cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1
    line_height = 22
    pad = 8
    text_w = max(cv2.getTextSize(line, font, scale, thickness)[0][0] for line in lines)
    panel_h = pad * 2 + line_height * len(lines)
    cv2.rectangle(frame, (0, 0), (text_w + pad * 2, panel_h), (0, 0, 0), -1)
    color = COLOR_OK if ok else COLOR_ERROR
    for i, line in enumerate(lines):
        y = pad + line_height * (i + 1) - 6
        cv2.putText(frame, line, (pad, y), font, scale, color, thickness, cv2.LINE_AA)


def draw_placeholder(frame, text: str) -> None:
    height, width = frame.shape[:2]
    cv2.putText(
        frame,
        text,
        (20, height // 2),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.0,
        (120, 120, 120),
        2,
        cv2.LINE_AA,
    )
