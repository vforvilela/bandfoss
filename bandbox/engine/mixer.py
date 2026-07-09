"""Mixer em tempo real: toca N stems somados por ganho, com mute/solo/seek.

Os stems são pré-separados (arrays em memória). O callback do sounddevice mixa
por bloco, lendo os ganhos atuais — mexer num fader reflete imediatamente no som.
"""

from __future__ import annotations

import threading
from typing import Dict, List, Optional

import numpy as np
import sounddevice as sd

from ..config import BLOCK_SIZE, CHANNELS, SAMPLE_RATE


class StemMixer:
    def __init__(self, stems: Dict[str, np.ndarray], samplerate: int = SAMPLE_RATE):
        if not stems:
            raise ValueError("Nenhum stem fornecido ao mixer.")

        self.names: List[str] = list(stems.keys())
        # Empilha stems em um array [n_stems, amostras, 2] para mix vetorizada.
        length = max(s.shape[0] for s in stems.values())
        self._buffers = np.zeros((len(self.names), length, CHANNELS), dtype=np.float32)
        for i, name in enumerate(self.names):
            s = stems[name]
            self._buffers[i, : s.shape[0], : s.shape[1]] = s

        self.samplerate = samplerate
        self.total_frames = length

        self._gains = {name: 1.0 for name in self.names}
        self._muted = {name: False for name in self.names}
        self._solo: Optional[str] = None

        self._pos = 0
        self._playing = False
        self._lock = threading.Lock()
        self._stream: Optional[sd.OutputStream] = None

    # ---- controle de stems ------------------------------------------------
    def set_gain(self, name: str, gain: float) -> None:
        with self._lock:
            self._gains[name] = max(0.0, float(gain))

    def set_muted(self, name: str, muted: bool) -> None:
        with self._lock:
            self._muted[name] = bool(muted)

    def set_solo(self, name: Optional[str]) -> None:
        with self._lock:
            self._solo = name

    def _effective_gain(self, name: str) -> float:
        if self._solo is not None:
            return self._gains[name] if name == self._solo else 0.0
        if self._muted[name]:
            return 0.0
        return self._gains[name]

    # ---- transporte -------------------------------------------------------
    def _callback(self, outdata, frames, time_info, status):  # noqa: ANN001
        with self._lock:
            if not self._playing:
                outdata.fill(0)
                return
            start = self._pos
            end = min(start + frames, self.total_frames)
            n = end - start
            gains = np.array(
                [self._effective_gain(name) for name in self.names], dtype=np.float32
            )
            self._pos = end
            reached_end = end >= self.total_frames

        outdata.fill(0)
        if n > 0:
            # [n_stems, n, 2] * [n_stems, 1, 1] -> soma sobre stems -> [n, 2]
            chunk = self._buffers[:, start:end, :]
            mix = np.tensordot(gains, chunk, axes=(0, 0))
            np.clip(mix, -1.0, 1.0, out=mix)
            outdata[:n] = mix

        if reached_end:
            with self._lock:
                self._playing = False

    def start(self) -> None:
        """Abre o stream de saída (idempotente)."""
        if self._stream is None:
            self._stream = sd.OutputStream(
                samplerate=self.samplerate,
                channels=CHANNELS,
                blocksize=BLOCK_SIZE,
                dtype="float32",
                callback=self._callback,
            )
            self._stream.start()

    def play(self) -> None:
        self.start()
        with self._lock:
            if self._pos >= self.total_frames:
                self._pos = 0
            self._playing = True

    def pause(self) -> None:
        with self._lock:
            self._playing = False

    def toggle(self) -> bool:
        with self._lock:
            playing = self._playing
        if playing:
            self.pause()
        else:
            self.play()
        return not playing

    def stop(self) -> None:
        with self._lock:
            self._playing = False
            self._pos = 0

    def seek(self, frame: int) -> None:
        with self._lock:
            self._pos = int(np.clip(frame, 0, self.total_frames))

    def seek_seconds(self, seconds: float) -> None:
        self.seek(int(seconds * self.samplerate))

    # ---- estado -----------------------------------------------------------
    @property
    def is_playing(self) -> bool:
        with self._lock:
            return self._playing

    @property
    def position_frames(self) -> int:
        with self._lock:
            return self._pos

    @property
    def position_seconds(self) -> float:
        return self.position_frames / self.samplerate

    @property
    def duration_seconds(self) -> float:
        return self.total_frames / self.samplerate

    def close(self) -> None:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
