"""Estado de ganho/mute/solo por stem, compartilhado entre mixer offline e ao vivo."""

from __future__ import annotations

import threading
from typing import Dict, List, Optional

import numpy as np


class StemGains:
    """Ganhos por stem com mute/solo, thread-safe. Não guarda áudio — só estado."""

    def __init__(self, names: List[str]):
        self.names: List[str] = list(names)
        self._lock = threading.Lock()
        self._gain: Dict[str, float] = {n: 1.0 for n in self.names}
        self._muted: Dict[str, bool] = {n: False for n in self.names}
        self._solo: Optional[str] = None

    def set_gain(self, name: str, gain: float) -> None:
        with self._lock:
            self._gain[name] = max(0.0, float(gain))

    def set_muted(self, name: str, muted: bool) -> None:
        with self._lock:
            self._muted[name] = bool(muted)

    def set_solo(self, name: Optional[str]) -> None:
        with self._lock:
            self._solo = name

    def _effective(self, name: str) -> float:
        if self._solo is not None:
            return self._gain[name] if name == self._solo else 0.0
        if self._muted[name]:
            return 0.0
        return self._gain[name]

    def vector(self) -> np.ndarray:
        """Ganhos efetivos na ordem de `self.names`."""
        with self._lock:
            return np.array([self._effective(n) for n in self.names], dtype=np.float32)

    def mix(self, stacked: np.ndarray) -> np.ndarray:
        """Soma ponderada. `stacked`: [n_stems, frames, canais] -> [frames, canais]."""
        gains = self.vector()
        return np.tensordot(gains, stacked, axes=(0, 0)).astype(np.float32)
