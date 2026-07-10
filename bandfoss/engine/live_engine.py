"""LIVE separation: sliding window + Demucs + real-time overlap-add.

Pulls audio from the capture in windows of W frames with hop = W/2 (50% overlap),
separates each window, remixes by the current gains, applies a Hann window and
overlap-adds — a smooth reconstruction (COLA) that also softens Demucs' edge
artifacts. The output goes to a FloatRing consumed by sounddevice.

Inherent latency ~= window size (we need a full window before the first
separation). This cannot be driven to zero with Demucs.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import threading
from typing import Protocol

import numpy as np
import sounddevice as sd

from ..config import BLOCK_SIZE, CHANNELS, LIVE_SHIFTS, SAMPLE_RATE
from .gains import StemGains
from .ring import FloatRing

log = logging.getLogger(__name__)


class _CaptureLike(Protocol):
    def read_exact(self, n: int) -> np.ndarray | None: ...


class _SeparatorLike(Protocol):
    sources: list[str]
    def separate(self, pcm: np.ndarray, fast: bool = ...) -> dict: ...


class LiveEngine:
    def __init__(
        self,
        separator: _SeparatorLike,
        capture: _CaptureLike,
        window_frames: int,
        samplerate: int = SAMPLE_RATE,
        gains: StemGains | None = None,
        start_output: bool = True,
        output_sink: str | None = None,
        output_device: str | int | None = None,
    ):
        # Force W even and hop = W/2 (required for perfect Hann overlap-add).
        self.W = int(window_frames) - (int(window_frames) % 2)
        self.H = self.W // 2
        self.names = list(separator.sources)
        self.samplerate = samplerate
        self.gains = gains or StemGains(self.names)

        self._sep = separator
        self._cap = capture
        self._start_output = start_output
        self._output_sink = output_sink   # if set, play via pacat to this real sink
        self._output_device = output_device  # sounddevice output device (name/index)
        self._pacat: subprocess.Popen | None = None
        self._pump_thread: threading.Thread | None = None

        self._nstems = len(self.names)

        # PERIODIC Hann (not np.hanning): guarantees constant overlap-add
        # (COLA = 1) at 50% hop, with no amplitude ripple between windows.
        w = 0.5 - 0.5 * np.cos(2 * np.pi * np.arange(self.W) / self.W)
        self._hann = w.astype(np.float32)[None, :, None]        # [1, W, 1]
        self._carry = np.zeros((self._nstems, self.H, CHANNELS), dtype=np.float32)
        self._window = np.zeros((self.W, CHANNELS), dtype=np.float32)

        # The ring holds the SEPARATED (overlap-added) stems, not the mix. Gain
        # is applied only at output (per block) -> faders/mute respond instantly.
        self.out_ring = FloatRing(int(4 * samplerate), self._nstems * CHANNELS)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._stream: sd.OutputStream | None = None
        self.underruns = 0

    # ---- gain delegation (same API as StemMixer) --------------------------
    def set_gain(self, name: str, gain: float) -> None:
        self.gains.set_gain(name, gain)

    def set_muted(self, name: str, muted: bool) -> None:
        self.gains.set_muted(name, muted)

    def set_solo(self, name: str | None) -> None:
        self.gains.set_solo(name)

    @property
    def latency_seconds(self) -> float:
        return self.W / self.samplerate

    # ---- DSP core ---------------------------------------------------------
    def prime(self) -> bool:
        """Fill the first window. Returns False if the capture ends first."""
        first = self._cap.read_exact(self.W)
        if first is None:
            return False
        self._window = first
        self._carry = np.zeros((self._nstems, self.H, CHANNELS), dtype=np.float32)
        return True

    def step(self) -> np.ndarray | None:
        """Separate the window, emit H frames per stem (packed), and slide.

        Does NOT apply gain here — the fader mix happens at output, per block.
        Returns [H, n_stems*2] or None at the end.
        """
        stems = self._sep.separate(self._window, fast=True, shifts=LIVE_SHIFTS)
        stacked = np.stack([stems[n] for n in self.names])   # [S, W, 2]
        windowed = stacked * self._hann                       # [S, W, 2] (Hann)

        out = self._carry + windowed[:, : self.H, :]          # [S, H, 2] overlap-add
        self._carry = windowed[:, self.H:, :].copy()

        nxt = self._cap.read_exact(self.H)
        if nxt is None:
            return None
        self._window = np.concatenate([self._window[self.H:], nxt], axis=0)
        # pack [S, H, 2] -> [H, S*2] for the ring
        return np.transpose(out, (1, 0, 2)).reshape(self.H, self._nstems * CHANNELS)

    def _loop(self) -> None:
        try:
            if not self.prime():
                return
            while not self._stop.is_set():
                out = self.step()
                if out is None:
                    break
                self.out_ring.write(out)
        except Exception:  # noqa: BLE001
            log.exception("processing error")
        finally:
            self.out_ring.close()

    # ---- audio output -----------------------------------------------------
    def _mix_block(self, packed: np.ndarray) -> np.ndarray:
        """[n, n_stems*2] -> [n, 2] applying the CURRENT gains (mute/solo)."""
        n = packed.shape[0]
        frames = packed.reshape(n, self._nstems, CHANNELS)   # [n, S, 2]
        g = self.gains.vector()                              # [S] (effective)
        mix = np.tensordot(frames, g, axes=(1, 0)).astype(np.float32)  # [n, 2]
        np.clip(mix, -1.0, 1.0, out=mix)
        return mix

    def _output_callback(self, outdata, frames, time_info, status):  # noqa: ANN001
        chunk, avail = self.out_ring.read(frames, block=False)
        if avail < frames:
            self.underruns += 1
        outdata[:] = self._mix_block(chunk)

    def _pump_to_pacat(self) -> None:
        """Read out_ring, mix with the current gains, and write to pacat."""
        try:
            while not self._stop.is_set():
                chunk, avail = self.out_ring.read(BLOCK_SIZE, block=True)
                if avail == 0:            # ring closed and empty -> end
                    break
                try:
                    self._pacat.stdin.write(self._mix_block(chunk).tobytes())
                except (BrokenPipeError, ValueError):
                    break
        finally:
            if self._pacat and self._pacat.stdin:
                try:
                    self._pacat.stdin.close()
                except Exception:  # noqa: BLE001
                    pass

    def start(self) -> None:
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

        if self._output_sink:
            # explicit output to the REAL sink via pacat (does not follow the
            # default, which is now the virtual sink) -> no feedback loop.
            pacat = shutil.which("pacat")
            if pacat is None:
                raise RuntimeError("'pacat' not found on PATH.")
            self._pacat = subprocess.Popen(
                [
                    pacat, "--playback",
                    f"--device={self._output_sink}",
                    "--format=float32le",
                    f"--rate={self.samplerate}",
                    f"--channels={CHANNELS}",
                    "--latency-msec=80",
                ],
                stdin=subprocess.PIPE,
            )
            self._pump_thread = threading.Thread(target=self._pump_to_pacat, daemon=True)
            self._pump_thread.start()
        elif self._start_output:
            # sounddevice output (Windows/macOS, or Linux advanced without
            # isolation). output_device=None uses the system default.
            self._stream = sd.OutputStream(
                samplerate=self.samplerate,
                channels=CHANNELS,
                blocksize=BLOCK_SIZE,
                dtype="float32",
                device=self._output_device,
                callback=self._output_callback,
            )
            self._stream.start()

    def stop(self) -> None:
        self._stop.set()
        self.out_ring.close()
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        if self._pacat is not None:
            self._pacat.terminate()
            try:
                self._pacat.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                self._pacat.kill()
            self._pacat = None
