"""Capture backend interface + reusable ring/thread plumbing + a fake backend.

Every backend produces stereo float32 PCM and exposes ``read_exact(n)``, which is
all ``LiveEngine`` needs. ``start()``/``stop()`` manage the backend lifecycle.
Concrete backends: PipeWire (Linux, ``live_source``) and WASAPI loopback
(Windows, ``wasapi_source``); ``FakeCapture`` is for tests.
"""

from __future__ import annotations

import threading
from typing import Protocol, runtime_checkable

import numpy as np

from ..config import CHANNELS, SAMPLE_RATE
from ..engine.ring import FloatRing


@runtime_checkable
class CaptureBackend(Protocol):
    """What LiveEngine and the UI rely on from any capture source."""

    samplerate: int
    channels: int

    def start(self) -> None: ...
    def read_exact(self, n: int) -> np.ndarray | None: ...
    def stop(self) -> None: ...


class BaseRingCapture:
    """Reader thread fills a FloatRing; ``read_exact`` drains it.

    Subclasses implement ``_open`` / ``_read_block`` / ``_close``. This keeps the
    thread + ring lifecycle in one place so each backend only writes the part
    that actually differs (a subprocess pipe, a WASAPI recorder, a test signal).
    """

    def __init__(
        self,
        samplerate: int = SAMPLE_RATE,
        channels: int = CHANNELS,
        ring_seconds: float = 8.0,
    ):
        self.samplerate = samplerate
        self.channels = channels
        self._ring = FloatRing(int(ring_seconds * samplerate), channels)
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    def start(self) -> None:
        self._open()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        try:
            while not self._stop.is_set():
                block = self._read_block()
                if block is None:          # source ended
                    break
                if len(block):
                    self._ring.write(block)
        finally:
            self._ring.close()

    def read_exact(self, n: int) -> np.ndarray | None:
        """Block until `n` frames are available; return None if capture ends."""
        arr, avail = self._ring.read(n, block=True)
        if avail < n:
            return None
        return arr

    @property
    def buffered_frames(self) -> int:
        return self._ring.available

    def stop(self) -> None:
        self._stop.set()
        self._ring.close()
        self._close()

    # ---- subclass hooks ---------------------------------------------------
    def _open(self) -> None:
        """Acquire the backend resource (may raise if unavailable)."""

    def _read_block(self) -> np.ndarray | None:
        """Return the next [frames, channels] block, or None when finished."""
        raise NotImplementedError

    def _close(self) -> None:
        """Release the backend resource."""


class FakeCapture(BaseRingCapture):
    """Deterministic in-memory capture for tests: streams a fixed signal.

    Feeds ``signal`` in blocks of ``block`` frames, then returns None so
    ``LiveEngine`` stops cleanly. Needs no audio hardware or OS backend.
    """

    def __init__(self, signal: np.ndarray, block: int = 2048, **kwargs):
        super().__init__(**kwargs)
        self._signal = np.ascontiguousarray(signal, dtype=np.float32)
        self._block = block
        self._pos = 0

    def _read_block(self) -> np.ndarray | None:
        if self._pos >= len(self._signal):
            return None
        end = min(self._pos + self._block, len(self._signal))
        chunk = self._signal[self._pos:end]
        self._pos = end
        return chunk
