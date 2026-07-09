"""Per-stem gain/mute/solo state, shared by the offline and live mixers."""

from __future__ import annotations

import threading

import numpy as np


class StemGains:
    """Thread-safe per-stem gains with mute/solo. Holds state only, no audio."""

    def __init__(self, names: list[str]):
        self.names: list[str] = list(names)
        self._lock = threading.Lock()
        self._gain: dict[str, float] = {n: 1.0 for n in self.names}
        self._muted: dict[str, bool] = {n: False for n in self.names}
        self._solo: str | None = None

    def set_gain(self, name: str, gain: float) -> None:
        with self._lock:
            self._gain[name] = max(0.0, float(gain))

    def set_muted(self, name: str, muted: bool) -> None:
        with self._lock:
            self._muted[name] = bool(muted)

    def set_solo(self, name: str | None) -> None:
        with self._lock:
            self._solo = name

    def _effective(self, name: str) -> float:
        if self._solo is not None:
            return self._gain[name] if name == self._solo else 0.0
        if self._muted[name]:
            return 0.0
        return self._gain[name]

    def vector(self) -> np.ndarray:
        """Effective gains in the order of `self.names`."""
        with self._lock:
            return np.array([self._effective(n) for n in self.names], dtype=np.float32)

    def mix(self, stacked: np.ndarray) -> np.ndarray:
        """Weighted sum. `stacked`: [n_stems, frames, channels] -> [frames, channels]."""
        gains = self.vector()
        return np.tensordot(gains, stacked, axes=(0, 0)).astype(np.float32)
