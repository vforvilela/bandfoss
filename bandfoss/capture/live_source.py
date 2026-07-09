"""Captura ao vivo do áudio do sistema via monitor do PipeWire (`parec`).

Grava o que estiver tocando no sink padrão (Spotify, navegador, etc.) e entrega
o PCM em blocos float32 estéreo, através de um `FloatRing`.
"""

from __future__ import annotations

import shutil
import subprocess
import threading
from typing import List, Optional

import numpy as np

from ..config import CHANNELS, SAMPLE_RATE
from ..engine.ring import FloatRing


def _require(tool: str) -> str:
    path = shutil.which(tool)
    if path is None:
        raise RuntimeError(f"'{tool}' não encontrado no PATH.")
    return path


def default_monitor() -> str:
    """Nome do monitor do sink padrão (o que captura o que está tocando)."""
    pactl = _require("pactl")
    sink = subprocess.check_output([pactl, "get-default-sink"], text=True).strip()
    if not sink:
        raise RuntimeError("Não foi possível obter o sink padrão (pactl).")
    return f"{sink}.monitor"


def list_monitors() -> List[str]:
    """Lista as fontes de monitor disponíveis (para o usuário escolher)."""
    pactl = _require("pactl")
    out = subprocess.check_output([pactl, "list", "sources", "short"], text=True)
    monitors = []
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2 and parts[1].endswith(".monitor"):
            monitors.append(parts[1])
    return monitors


class LiveCapture:
    """Sobe um `parec` no monitor escolhido e alimenta um FloatRing."""

    def __init__(
        self,
        device: Optional[str] = None,
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
        self._proc: Optional[subprocess.Popen] = None
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()

    def start(self) -> None:
        parec = _require("parec")
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

    def read_exact(self, n: int) -> Optional[np.ndarray]:
        """Bloqueia até obter `n` frames; retorna None se a captura encerrar."""
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
