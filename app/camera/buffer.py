"""Buffer circular de frames con timestamp, thread-safe (RF-2.1)."""

import bisect
import threading
from dataclasses import dataclass

import numpy as np


@dataclass
class TimedFrame:
    timestamp: float
    frame: np.ndarray


class FrameRingBuffer:
    """Almacena los últimos `max_seconds` de vídeo de una cámara.

    Los timestamps son monotónicos crecientes (time.monotonic()), lo que
    permite búsqueda binaria por el frame más cercano a un instante dado.
    """

    def __init__(self, max_seconds: float, expected_fps: float = 30.0):
        self._max_seconds = max_seconds
        self._expected_fps = expected_fps
        capacity = max(int(expected_fps * max_seconds * 1.5), 30)
        self._timestamps: list[float] = []
        self._frames: list[np.ndarray] = []
        self._capacity = capacity
        self._lock = threading.Lock()

    def set_max_seconds(self, max_seconds: float) -> None:
        with self._lock:
            self._max_seconds = max(max_seconds, 2.0)
            self._capacity = max(int(self._expected_fps * self._max_seconds * 1.5), 30)
            if self._timestamps:
                self._evict_old(self._timestamps[-1])

    def push(self, timestamp: float, frame: np.ndarray) -> None:
        with self._lock:
            self._timestamps.append(timestamp)
            self._frames.append(frame)
            self._evict_old(timestamp)

    def _evict_old(self, now: float) -> None:
        cutoff = now - self._max_seconds
        idx = bisect.bisect_left(self._timestamps, cutoff)
        if idx > 0:
            del self._timestamps[:idx]
            del self._frames[:idx]
        overflow = len(self._timestamps) - self._capacity
        if overflow > 0:
            del self._timestamps[:overflow]
            del self._frames[:overflow]

    def get_nearest(self, target_time: float) -> TimedFrame | None:
        """Devuelve el frame cuyo timestamp está más cerca de target_time."""
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
            return TimedFrame(self._timestamps[best], self._frames[best])

    def get_last_seconds(self, seconds: float, reference_time: float) -> list[TimedFrame]:
        """Frames cuyo timestamp cae en [reference_time - seconds, reference_time]."""
        with self._lock:
            if not self._timestamps:
                return []
            lo = bisect.bisect_left(self._timestamps, reference_time - seconds)
            hi = bisect.bisect_right(self._timestamps, reference_time)
            return [
                TimedFrame(ts, fr)
                for ts, fr in zip(self._timestamps[lo:hi], self._frames[lo:hi])
            ]

    def latest_timestamp(self) -> float | None:
        with self._lock:
            return self._timestamps[-1] if self._timestamps else None

    def is_empty(self) -> bool:
        with self._lock:
            return not self._timestamps
