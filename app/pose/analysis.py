"""Criterios de postura de tiro por vista de cámara (sección 6 de
requisitos_modulo_vision.md).

Cada función `_analyze_*` recibe los 33 landmarks normalizados en el plano
de la imagen (`pose_landmarks`, x/y en [0,1], origen arriba-izquierda, Y
creciente hacia abajo como es convención en imágenes) y devuelve una lista
de `Finding`. Se usan los landmarks 2D de imagen y no los "world landmarks"
3D: MediaPipe no documenta que estos últimos estén alineados con la
vertical real del mundo (más bien son relativos al encuadre de la cámara),
así que un ángulo 2D respecto al propio encuadre es más simple y fiable
—y es el enfoque habitual en apps de corrección postural con una sola
cámara— siempre que la cámara esté nivelada (sin balanceo/roll).

Convención compartida por las 3 vistas: "arriba en la imagen" es el eje de
referencia. Para la vista Trasera con la cámara nivelada, arriba-en-imagen
coincide con la vertical real (gravedad). Para la vista Superior (cámara
sobre el arquero mirando hacia abajo), arriba-en-imagen es la dirección
horizontal hacia la que se montó la cámara, que se asume la diana.

Los umbrales angulares son heurísticas de primera versión dentro de los
rangos que da el documento (o, cuando el documento no da un número para un
criterio, un valor razonable marcado como ajustable); conviene afinarlos
con vídeo real de tiradores.

Limitación conocida: "pecho cerrado y bajo, manteniendo firme el core"
(6.1, 6.2, 7.4) no se evalúa — los 33 landmarks no incluyen rotación de
caja torácica ni tensión muscular, no hay forma fiable de derivarlo solo de
las articulaciones.
"""

import dataclasses
import math

import numpy as np

from app.pose.view_modes import Handedness, ViewMode

# Índices estándar de los 33 landmarks de BlazePose/MediaPipe Pose que se
# usan en estos cálculos (el resto de los 33 puntos no son relevantes aquí).
NOSE = 0
LEFT_EAR = 7
RIGHT_EAR = 8
LEFT_SHOULDER = 11
RIGHT_SHOULDER = 12
LEFT_ELBOW = 13
RIGHT_ELBOW = 14
LEFT_WRIST = 15
RIGHT_WRIST = 16
LEFT_HIP = 23
RIGHT_HIP = 24

# Tolerancias en grados salvo que se indique lo contrario. Cuando el
# documento da un rango, se usa un valor intermedio.
SPINE_TILT_TOLERANCE_DEG = 7.5  # doc: 5-10°
SHOULDER_LEVEL_TOLERANCE_DEG = 4.0  # doc: ±3-5°
ARM_LINE_TOLERANCE_DEG = 8.0  # heurística: no numérico en el doc
DRAW_ELBOW_HEIGHT_TOLERANCE_RATIO = 0.12  # heurística, fracción del torso (hombro-cadera)
TOP_ELBOW_ALIGNMENT_TOLERANCE_DEG = 15.0  # heurística: no numérico en el doc

# "Arriba" en coordenadas de imagen normalizadas (Y crece hacia abajo).
IMAGE_UP = np.array([0.0, -1.0])
IMAGE_RIGHT = np.array([1.0, 0.0])


@dataclasses.dataclass
class Finding:
    label: str
    ok: bool
    detail: str
    landmark_indices: tuple[int, ...]


@dataclasses.dataclass
class PoseAnalysisResult:
    overall_ok: bool
    findings: list[Finding]


def _xy(landmark) -> np.ndarray:
    return np.array([landmark.x, landmark.y], dtype=np.float64)


def _midpoint(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return (a + b) / 2.0


def _angle_between_deg(v1: np.ndarray, v2: np.ndarray) -> float:
    n1, n2 = np.linalg.norm(v1), np.linalg.norm(v2)
    if n1 == 0 or n2 == 0:
        return 0.0
    cos_angle = np.clip(np.dot(v1, v2) / (n1 * n2), -1.0, 1.0)
    return math.degrees(math.acos(cos_angle))


def _angle_to_axis_deg(v: np.ndarray, axis: np.ndarray) -> float:
    """Ángulo mínimo entre v y la recta que define axis (ignora el sentido)."""
    return min(_angle_between_deg(v, axis), _angle_between_deg(v, -axis))


def _bow_and_draw_sides(handedness: Handedness) -> tuple[str, str]:
    """Devuelve (lado_arco, lado_tracción) como 'left'/'right'.

    Diestro: arco en la mano izquierda, tracción con la derecha. Zurdo: al
    revés. MediaPipe etiqueta left/right desde el punto de vista del propio
    sujeto (no de la imagen), así que esto es válido sin importar desde qué
    lado esté grabando la cámara.
    """
    if handedness == Handedness.DIESTRO:
        return "left", "right"
    return "right", "left"


def analyze(
    landmarks, view_mode: ViewMode, handedness: Handedness
) -> PoseAnalysisResult | None:
    """landmarks: result.pose_landmarks[0] (lista de 33 landmarks
    normalizados de una persona) o None/lista vacía si no se detectó a
    nadie."""
    if not landmarks:
        return None

    if view_mode == ViewMode.TRASERA:
        findings = _analyze_trasera(landmarks)
    elif view_mode == ViewMode.LATERAL:
        findings = _analyze_lateral(landmarks, handedness)
    else:
        findings = _analyze_superior(landmarks, handedness)

    return PoseAnalysisResult(overall_ok=all(f.ok for f in findings), findings=findings)


def _analyze_trasera(lm: list) -> list[Finding]:
    hip_mid = _midpoint(_xy(lm[LEFT_HIP]), _xy(lm[RIGHT_HIP]))
    shoulder_mid = _midpoint(_xy(lm[LEFT_SHOULDER]), _xy(lm[RIGHT_SHOULDER]))
    spine = shoulder_mid - hip_mid

    tilt = _angle_between_deg(spine, IMAGE_UP)
    ok = tilt <= SPINE_TILT_TOLERANCE_DEG
    detail = (
        f"Columna vertical ({tilt:.0f}°)"
        if ok
        else f"Columna inclinada {tilt:.0f}° (máx. {SPINE_TILT_TOLERANCE_DEG:.0f}°)"
    )
    return [
        Finding(
            label="Verticalidad de columna",
            ok=ok,
            detail=detail,
            landmark_indices=(LEFT_HIP, RIGHT_HIP, LEFT_SHOULDER, RIGHT_SHOULDER),
        )
    ]


def _analyze_lateral(lm: list, handedness: Handedness) -> list[Finding]:
    bow_side, draw_side = _bow_and_draw_sides(handedness)
    shoulder_idx = {"left": LEFT_SHOULDER, "right": RIGHT_SHOULDER}
    elbow_idx = {"left": LEFT_ELBOW, "right": RIGHT_ELBOW}
    wrist_idx = {"left": LEFT_WRIST, "right": RIGHT_WRIST}

    left_shoulder, right_shoulder = _xy(lm[LEFT_SHOULDER]), _xy(lm[RIGHT_SHOULDER])
    left_hip, right_hip = _xy(lm[LEFT_HIP]), _xy(lm[RIGHT_HIP])
    bow_wrist = _xy(lm[wrist_idx[bow_side]])
    draw_wrist = _xy(lm[wrist_idx[draw_side]])
    draw_shoulder = _xy(lm[shoulder_idx[draw_side]])
    draw_elbow = _xy(lm[elbow_idx[draw_side]])

    torso_scale = np.linalg.norm(_midpoint(left_shoulder, right_shoulder) - _midpoint(left_hip, right_hip))

    findings = []

    # Forma en "T": línea entre ambas muñecas, debe ser horizontal.
    arm_tilt = _angle_to_axis_deg(draw_wrist - bow_wrist, IMAGE_RIGHT)
    ok = arm_tilt <= ARM_LINE_TOLERANCE_DEG
    findings.append(
        Finding(
            label='Forma en "T" (brazos-hombros)',
            ok=ok,
            detail=(
                f"Brazos a la altura de los hombros ({arm_tilt:.0f}°)"
                if ok
                else f"Brazos desnivelados {arm_tilt:.0f}° (máx. {ARM_LINE_TOLERANCE_DEG:.0f}°)"
            ),
            landmark_indices=(
                shoulder_idx[bow_side],
                elbow_idx[bow_side],
                wrist_idx[bow_side],
                shoulder_idx[draw_side],
                elbow_idx[draw_side],
                wrist_idx[draw_side],
            ),
        )
    )

    # Hombros nivelados.
    shoulder_tilt = _angle_to_axis_deg(right_shoulder - left_shoulder, IMAGE_RIGHT)
    ok = shoulder_tilt <= SHOULDER_LEVEL_TOLERANCE_DEG
    findings.append(
        Finding(
            label="Hombros nivelados",
            ok=ok,
            detail=(
                f"Hombros nivelados ({shoulder_tilt:.0f}°)"
                if ok
                else f"Hombro elevado {shoulder_tilt:.0f}° (máx. {SHOULDER_LEVEL_TOLERANCE_DEG:.0f}°)"
            ),
            landmark_indices=(LEFT_SHOULDER, RIGHT_SHOULDER),
        )
    )

    # Codo de tracción a la altura del hombro/flecha o ligeramente por
    # encima (6.2, bullets 3 y 4: mismo chequeo de altura de codo). La
    # tolerancia se expresa como fracción del torso (hombro-cadera) para no
    # depender de a qué distancia esté la cámara.
    elbow_height_diff = draw_shoulder[1] - draw_elbow[1]  # imagen: Y menor = más arriba
    tolerance = DRAW_ELBOW_HEIGHT_TOLERANCE_RATIO * torso_scale
    ok = elbow_height_diff >= -tolerance
    findings.append(
        Finding(
            label="Codo de tracción alineado con la flecha",
            ok=ok,
            detail=(
                "Codo de tracción a la altura del hombro/flecha"
                if ok
                else "Codo del brazo de tracción caído por debajo de la flecha"
            ),
            landmark_indices=(shoulder_idx[draw_side], elbow_idx[draw_side], wrist_idx[draw_side]),
        )
    )

    return findings


def _analyze_superior(lm: list, handedness: Handedness) -> list[Finding]:
    """Vista superior: se asume que "arriba" en la imagen apunta hacia la
    diana, es decir, que la cámara está montada directamente sobre el
    arquero mirando hacia abajo con esa orientación. Si el montaje real
    difiere, este criterio debe ajustarse.
    """
    bow_side, draw_side = _bow_and_draw_sides(handedness)
    elbow_idx = {"left": LEFT_ELBOW, "right": RIGHT_ELBOW}
    shoulder_idx = {"left": LEFT_SHOULDER, "right": RIGHT_SHOULDER}
    wrist_idx = {"left": LEFT_WRIST, "right": RIGHT_WRIST}

    left_shoulder, right_shoulder = _xy(lm[LEFT_SHOULDER]), _xy(lm[RIGHT_SHOULDER])
    draw_shoulder = _xy(lm[shoulder_idx[draw_side]])
    draw_elbow = _xy(lm[elbow_idx[draw_side]])

    findings = []

    # Alineación hombros-línea de tiro: la línea de hombros debe ser
    # perpendicular al eje de tiro (asumido como "arriba" en la imagen).
    shoulder_line = right_shoulder - left_shoulder
    angle_to_shooting_axis = _angle_to_axis_deg(shoulder_line, IMAGE_UP)
    perpendicularity = abs(90.0 - angle_to_shooting_axis)
    ok = perpendicularity <= SHOULDER_LEVEL_TOLERANCE_DEG
    findings.append(
        Finding(
            label="Hombros alineados con la línea de tiro",
            ok=ok,
            detail=(
                "Hombros alineados con la línea de tiro"
                if ok
                else f"Hombros desviados {perpendicularity:.0f}° de la línea de tiro"
            ),
            landmark_indices=(LEFT_SHOULDER, RIGHT_SHOULDER),
        )
    )

    # Codo de tracción alineado con la flecha (o ligeramente por detrás):
    # el vector hombro->codo de tracción no debe desviarse mucho respecto
    # a la propia línea de hombros extendida.
    elbow_vector = draw_elbow - draw_shoulder
    reference = shoulder_line if draw_side == "right" else -shoulder_line
    elbow_deviation = _angle_between_deg(elbow_vector, reference)
    ok = elbow_deviation <= TOP_ELBOW_ALIGNMENT_TOLERANCE_DEG
    findings.append(
        Finding(
            label="Codo de tracción alineado con la flecha",
            ok=ok,
            detail=(
                "Codo de tracción en línea con la flecha"
                if ok
                else f"Codo de tracción adelantado {elbow_deviation:.0f}° respecto a la flecha"
            ),
            landmark_indices=(shoulder_idx[draw_side], elbow_idx[draw_side], wrist_idx[draw_side]),
        )
    )

    return findings
