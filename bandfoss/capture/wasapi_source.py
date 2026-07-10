"""Windows system-audio capture via WASAPI loopback (using `soundcard`).

Records the loopback of an output device (what is playing) and feeds a FloatRing.
Whole-system capture needs no kernel driver.

Avoiding self-capture (feedback): WASAPI loopback of a device records EVERYTHING
going to it — including BandFOSS's own output. So the processed mix must be
played to a DIFFERENT device than the one being captured. The cleanest setup is a
virtual cable (VB-CABLE): route the source into the cable, capture the cable's
loopback, and output to the real speaker. The UI enforces capture != output.
"""

from __future__ import annotations

import numpy as np

from ..config import CHANNELS, SAMPLE_RATE
from .base import BaseRingCapture


def _soundcard():
    """Import `soundcard` lazily (Windows-only dependency)."""
    try:
        import soundcard as sc
    except ImportError as exc:  # pragma: no cover - platform dependent
        raise RuntimeError(
            "The 'soundcard' package is required for Windows capture. "
            "Install it with: pip install soundcard"
        ) from exc
    return sc


def list_loopback_devices() -> list[str]:
    """Names of output devices whose loopback can be captured."""
    sc = _soundcard()
    return [s.name for s in sc.all_speakers()]


def default_loopback() -> str:
    """Name of the default output device (its loopback is the default capture)."""
    sc = _soundcard()
    return sc.default_speaker().name


class WasapiLoopbackCapture(BaseRingCapture):
    """Capture the loopback of a WASAPI output device via `soundcard`."""

    def __init__(
        self,
        device: str | None = None,
        samplerate: int = SAMPLE_RATE,
        channels: int = CHANNELS,
        block: int = 2048,
        **kwargs,
    ):
        super().__init__(samplerate=samplerate, channels=channels, **kwargs)
        self.device_name = device
        self._block = block
        self._mic = None
        self._recorder = None

    def _open(self) -> None:
        sc = _soundcard()
        speaker = (
            sc.default_speaker()
            if not self.device_name
            else sc.get_speaker(self.device_name)
        )
        if speaker is None:
            raise RuntimeError(f"Output device not found: {self.device_name!r}")
        # A loopback "microphone" bound to that speaker records what plays on it.
        self._mic = sc.get_microphone(id=str(speaker.name), include_loopback=True)
        self._recorder = self._mic.recorder(
            samplerate=self.samplerate, channels=self.channels, blocksize=self._block
        )
        self._recorder.__enter__()

    def _read_block(self) -> np.ndarray | None:
        if self._recorder is None:
            return None
        data = self._recorder.record(numframes=self._block)  # float32 [n, channels]
        return np.ascontiguousarray(data, dtype=np.float32)

    def _close(self) -> None:
        if self._recorder is not None:
            try:
                self._recorder.__exit__(None, None, None)
            except Exception:  # noqa: BLE001 - already tearing down
                pass
            self._recorder = None
        self._mic = None
