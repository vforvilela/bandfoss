"""Live capture of system audio via the PipeWire monitor (`parec`).

Records whatever is playing on the default sink (Spotify, browser, etc.) and
delivers PCM in stereo float32 blocks through a `FloatRing`.
"""

from __future__ import annotations

import subprocess
import threading

import numpy as np

from ..config import CHANNELS, SAMPLE_RATE
from ..engine.ring import FloatRing
from ..util import require_tool


def default_monitor() -> str:
    """Monitor name of the default sink (captures what is currently playing)."""
    pactl = require_tool("pactl")
    sink = subprocess.check_output([pactl, "get-default-sink"], text=True).strip()
    if not sink:
        raise RuntimeError("Could not determine the default sink (pactl).")
    return f"{sink}.monitor"


def list_monitors() -> list[str]:
    """List available monitor sources (for the user to choose from)."""
    pactl = require_tool("pactl")
    out = subprocess.check_output([pactl, "list", "sources", "short"], text=True)
    monitors = []
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2 and parts[1].endswith(".monitor"):
            monitors.append(parts[1])
    return monitors


class LiveCapture:
    """Spawns a `parec` on the chosen monitor and feeds a FloatRing."""

    def __init__(
        self,
        device: str | None = None,
        samplerate: int = SAMPLE_RATE,
        channels: int = CHANNELS,
        ring_seconds: float = 8.0,
        read_frames: int = 2048,
    ):
        self.device = device or default_monitor()
        self.samplerate = samplerate
        self.channels = channels
        self._read_frames = read_frames
        self._ring = FloatRing(int(ring_seconds * samplerate), channels)
        self._proc: subprocess.Popen | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    def start(self) -> None:
        parec = require_tool("parec")
        cmd = [
            parec,
            "--format=float32le",
            f"--rate={self.samplerate}",
            f"--channels={self.channels}",
            f"--device={self.device}",
            "--latency-msec=50",
        ]
        self._proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        self._thread = threading.Thread(target=self._reader, daemon=True)
        self._thread.start()

    def _reader(self) -> None:
        bytes_per_frame = 4 * self.channels  # float32
        want = bytes_per_frame * self._read_frames
        stdout = self._proc.stdout
        while not self._stop.is_set():
            data = stdout.read(want)
            if not data:
                break
            arr = np.frombuffer(data, dtype=np.float32)
            n = (len(arr) // self.channels) * self.channels
            if n == 0:
                continue
            self._ring.write(arr[:n].reshape(-1, self.channels))
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
        if self._proc is not None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                self._proc.kill()
            self._proc = None
