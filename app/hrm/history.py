"""Historial de bpm con timestamp, para sincronizar el overlay del clip exportado."""

import bisect
import threading


class BpmHistory:
    """Guarda los últimos `max_seconds` de lecturas de bpm (timestamps monotónicos)."""

    def __init__(self, max_seconds: float = 2.0):
        self._max_seconds = max_seconds
        self._timestamps: list[float] = []
        self._values: list[int] = []
        self._lock = threading.Lock()

    def set_max_seconds(self, max_seconds: float) -> None:
        with self._lock:
            self._max_seconds = max(max_seconds, 2.0)
            if self._timestamps:
                self._evict_old(self._timestamps[-1])

    def push(self, timestamp: float, bpm: int) -> None:
        with self._lock:
            self._timestamps.append(timestamp)
            self._values.append(bpm)
            self._evict_old(timestamp)

    def _evict_old(self, now: float) -> None:
        cutoff = now - self._max_seconds
        idx = bisect.bisect_left(self._timestamps, cutoff)
        if idx > 0:
            del self._timestamps[:idx]
            del self._values[:idx]

    def get_nearest(self, target_time: float, max_age_seconds: float = 5.0) -> int | None:
        """Devuelve el bpm más cercano a target_time, o None si no hay lectura
        suficientemente próxima (por ejemplo, si el HRM no estaba conectado)."""
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
