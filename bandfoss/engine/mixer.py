"""Real-time mixer: plays N gain-summed stems, with mute/solo/seek.

Stems are pre-separated (in-memory arrays). The sounddevice callback mixes
per block, reading the current gains — so moving a fader is heard immediately.

Note: this is the offline path, used by scripts/smoke_test.py. The shipped app
runs live only (see live_engine.LiveEngine).
"""

from __future__ import annotations

import threading

import numpy as np
import sounddevice as sd

from ..config import BLOCK_SIZE, CHANNELS, SAMPLE_RATE
from .gains import StemGains


class StemMixer:
    def __init__(self, stems: dict[str, np.ndarray], samplerate: int = SAMPLE_RATE):
        if not stems:
            raise ValueError("No stems provided to the mixer.")

        self.names: list[str] = list(stems.keys())
        # Stack stems into a [n_stems, samples, 2] array for a vectorized mix.
        length = max(s.shape[0] for s in stems.values())
        self._buffers = np.zeros((len(self.names), length, CHANNELS), dtype=np.float32)
        for i, name in enumerate(self.names):
            s = stems[name]
            self._buffers[i, : s.shape[0], : s.shape[1]] = s

        self.samplerate = samplerate
        self.total_frames = length

        self.gains = StemGains(self.names)

        self._pos = 0
        self._playing = False
        self._lock = threading.Lock()
        self._stream: sd.OutputStream | None = None

    # ---- stem control (delegated to StemGains) ----------------------------
    def set_gain(self, name: str, gain: float) -> None:
        self.gains.set_gain(name, gain)

    def set_muted(self, name: str, muted: bool) -> None:
        self.gains.set_muted(name, muted)

    def set_solo(self, name: str | None) -> None:
        self.gains.set_solo(name)

    # ---- transport --------------------------------------------------------
    def _callback(self, outdata, frames, time_info, status):  # noqa: ANN001
        with self._lock:
            if not self._playing:
                outdata.fill(0)
                return
            start = self._pos
            end = min(start + frames, self.total_frames)
            n = end - start
            self._pos = end
            reached_end = end >= self.total_frames

        outdata.fill(0)
        if n > 0:
            # [n_stems, n, 2] -> weighted sum over stems -> [n, 2]
            mix = self.gains.mix(self._buffers[:, start:end, :])
            np.clip(mix, -1.0, 1.0, out=mix)
            outdata[:n] = mix

        if reached_end:
            with self._lock:
                self._playing = False

    def start(self) -> None:
        """Open the output stream (idempotent)."""
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

    # ---- state ------------------------------------------------------------
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
