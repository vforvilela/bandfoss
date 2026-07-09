"""Ring buffer float32 [frames, canais], thread-safe, para áudio em streaming."""

from __future__ import annotations

import threading
from typing import Tuple

import numpy as np


class FloatRing:
    """Buffer circular produtor/consumidor. Overflow descarta o mais antigo."""

    def __init__(self, capacity_frames: int, channels: int = 2):
        self._cap = int(capacity_frames)
        self._ch = channels
        self._buf = np.zeros((self._cap, channels), dtype=np.float32)
        self._w = 0          # próxima posição de escrita
        self._count = 0      # frames válidos disponíveis
        self._cond = threading.Condition()
        self._closed = False

    def write(self, data: np.ndarray) -> None:
        data = np.ascontiguousarray(data, dtype=np.float32)
        n = len(data)
        if n == 0:
            return
        with self._cond:
            if n >= self._cap:                       # mantém só o final
                data = data[-self._cap:]
                n = self._cap
            end = self._w + n
            if end <= self._cap:
                self._buf[self._w:end] = data
            else:                                    # dá a volta
                k = self._cap - self._w
                self._buf[self._w:] = data[:k]
                self._buf[: end - self._cap] = data[k:]
            self._w = end % self._cap
            # se estourou a capacidade, o read pointer avança implicitamente
            self._count = min(self._cap, self._count + n)
            self._cond.notify_all()

    def read(self, n: int, block: bool = False) -> Tuple[np.ndarray, int]:
        """Retorna (array de tamanho `n` com zero-fill, nº de frames válidos).

        block=True espera até haver `n` frames ou o ring ser fechado.
        """
        out = np.zeros((n, self._ch), dtype=np.float32)
        with self._cond:
            if block:
                while self._count < n and not self._closed:
                    self._cond.wait()
            avail = min(n, self._count)
            if avail > 0:
                start = (self._w - self._count) % self._cap
                end = start + avail
                if end <= self._cap:
                    out[:avail] = self._buf[start:end]
                else:
                    k = self._cap - start
                    out[:k] = self._buf[start:]
                    out[k:avail] = self._buf[: end - self._cap]
                self._count -= avail
        return out, avail

    @property
    def available(self) -> int:
        with self._cond:
            return self._count

    def close(self) -> None:
        with self._cond:
            self._closed = True
            self._cond.notify_all()
