"""Historial de resultados de análisis de postura con timestamp, para que
el panel de estado refleje el mismo instante que se muestra con delay
(mismo patrón que BpmHistory en app/hrm/history.py)."""

import bisect
import threading

from app.pose.analysis import PoseAnalysisResult


class PoseResultHistory:
    """Guarda los últimos `max_seconds` de PoseAnalysisResult (timestamps
    monotónicos)."""

    def __init__(self, max_seconds: float = 32.0):
        self._max_seconds = max_seconds
        self._timestamps: list[float] = []
        self._values: list[PoseAnalysisResult | None] = []
        self._lock = threading.Lock()

    def set_max_seconds(self, max_seconds: float) -> None:
        with self._lock:
            self._max_seconds = max(max_seconds, 2.0)
            if self._timestamps:
                self._evict_old(self._timestamps[-1])

    def push(self, timestamp: float, result: PoseAnalysisResult | None) -> None:
        with self._lock:
            self._timestamps.append(timestamp)
            self._values.append(result)
            self._evict_old(timestamp)

    def _evict_old(self, now: float) -> None:
        cutoff = now - self._max_seconds
        idx = bisect.bisect_left(self._timestamps, cutoff)
        if idx > 0:
            del self._timestamps[:idx]
            del self._values[:idx]

    def get_nearest(
        self, target_time: float, max_age_seconds: float = 2.0
    ) -> PoseAnalysisResult | None:
        """Devuelve el resultado más cercano a target_time, o None si no hay
        ninguno suficientemente próximo (p.ej. justo tras arrancar)."""
        with self._lock:
            if not self._timestamps:
                return None
            idx = bisect.bisect_left(self._timestamps, target_time)
            if idx <= 0:
                best = 0
            elif idx >= len(self._timestamps):
                best = len(self._timestamps) - 1
            else:
                before, after = self._timestamps[idx - 1], self._timestamps[idx]
                best = idx - 1 if (target_time - before) <= (after - target_time) else idx
            if abs(self._timestamps[best] - target_time) > max_age_seconds:
                return None
            return self._values[best]
