"""macOS system-audio capture via a virtual input device (e.g. BlackHole).

macOS has no native loopback, so the user routes system audio into a virtual
audio device ([BlackHole](https://github.com/ExistentialAudio/BlackHole)) and
BandFOSS records that device as an ordinary input via `sounddevice` (PortAudio,
already a core dependency — no extra Python package).

Setup: set the system output (or a Multi-Output Device) to BlackHole, pick
BlackHole as **Capture** here, and set **Output** to your real speaker. Since
BandFOSS outputs to a different device than the one it captures, there's no
feedback and the original isn't doubled.
"""

from __future__ import annotations

import numpy as np

from ..config import CHANNELS, SAMPLE_RATE
from .base import BaseRingCapture

# Names that usually indicate a loopback/virtual device suitable for capture.
_VIRTUAL_HINTS = ("blackhole", "loopback", "soundflower", "aggregate", "vb-")


def _sounddevice():
    """Import `sounddevice` lazily (keeps UI startup light)."""
    import sounddevice as sd
    return sd


def list_input_devices() -> list[str]:
    """Names of devices that can be captured (have input channels)."""
    sd = _sounddevice()
    return [d["name"] for d in sd.query_devices() if d.get("max_input_channels", 0) > 0]


def list_output_devices() -> list[str]:
    """Names of devices that can play audio (have output channels)."""
    sd = _sounddevice()
    return [d["name"] for d in sd.query_devices() if d.get("max_output_channels", 0) > 0]


def default_input_device() -> str | None:
    """Best capture device: a virtual one (BlackHole) if present, else the default input."""
    sd = _sounddevice()
    for d in sd.query_devices():
        if d.get("max_input_channels", 0) > 0 and any(
            h in d["name"].lower() for h in _VIRTUAL_HINTS
        ):
            return d["name"]
    try:
        idx = sd.default.device[0]
        if idx is not None and idx >= 0:
            return sd.query_devices(idx)["name"]
    except Exception:  # noqa: BLE001 - no default input
        pass
    return None


class CoreAudioCapture(BaseRingCapture):
    """Capture a macOS input device (e.g. BlackHole) via `sounddevice`."""

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
        self._stream = None

    def _open(self) -> None:
        sd = _sounddevice()
        self._stream = sd.InputStream(
            samplerate=self.samplerate,
            channels=self.channels,
            dtype="float32",
            blocksize=self._block,
            device=self.device_name,       # None -> default input
        )
        self._stream.start()

    def _read_block(self) -> np.ndarray | None:
        if self._stream is None:
            return None
        data, _overflowed = self._stream.read(self._block)   # [block, channels]
        return np.ascontiguousarray(data, dtype=np.float32)

    def _close(self) -> None:
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:  # noqa: BLE001 - already tearing down
                pass
            self._stream = None
