"""Separação AO VIVO: janela deslizante + Demucs + overlap-add em tempo real.

Puxa áudio da captura em janelas de W frames com hop = W/2 (overlap de 50%),
separa cada janela, remixa pelos ganhos atuais, aplica janela de Hann e faz
overlap-add — reconstrução suave (COLA) que também suaviza os artefatos de borda
do Demucs. A saída vai para um FloatRing consumido pelo sounddevice.

Latência inerente ≈ tamanho da janela (precisamos de uma janela cheia antes da
primeira separação). Não há como zerar isso com o Demucs.
"""

from __future__ import annotations

import shutil
import subprocess
import threading
from typing import List, Optional, Protocol

import numpy as np
import sounddevice as sd

from ..config import BLOCK_SIZE, CHANNELS, SAMPLE_RATE
from .gains import StemGains
from .ring import FloatRing


class _CaptureLike(Protocol):
    def read_exact(self, n: int) -> Optional[np.ndarray]: ...


class _SeparatorLike(Protocol):
    sources: List[str]
    def separate(self, pcm: np.ndarray, fast: bool = ...) -> dict: ...


class LiveEngine:
    def __init__(
        self,
        separator: _SeparatorLike,
        capture: _CaptureLike,
        window_frames: int,
        samplerate: int = SAMPLE_RATE,
        gains: Optional[StemGains] = None,
        start_output: bool = True,
        output_sink: Optional[str] = None,
    ):
        # Garante W par e hop = W/2 (necessário para overlap-add Hann perfeito).
        self.W = int(window_frames) - (int(window_frames) % 2)
        self.H = self.W // 2
        self.names = list(separator.sources)
        self.samplerate = samplerate
        self.gains = gains or StemGains(self.names)

        self._sep = separator
        self._cap = capture
        self._start_output = start_output
        self._output_sink = output_sink   # se definido, toca via pacat neste sink real
        self._pacat: Optional[subprocess.Popen] = None
        self._pump_thread: Optional[threading.Thread] = None

        self._nstems = len(self.names)

        # Hann PERIÓDICO (não o np.hanning): garante overlap-add constante
        # (COLA = 1) no hop de 50%, sem ripple de amplitude entre janelas.
        w = 0.5 - 0.5 * np.cos(2 * np.pi * np.arange(self.W) / self.W)
        self._hann = w.astype(np.float32)[None, :, None]        # [1, W, 1]
        self._carry = np.zeros((self._nstems, self.H, CHANNELS), dtype=np.float32)
        self._window = np.zeros((self.W, CHANNELS), dtype=np.float32)

        # O ring guarda os stems SEPARADOS (overlap-added), não o mix. O ganho é
        # aplicado só na saída (a cada bloco) -> faders/mute respondem na hora.
        self.out_ring = FloatRing(int(4 * samplerate), self._nstems * CHANNELS)
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._stream: Optional[sd.OutputStream] = None
        self.underruns = 0

    # ---- delegação de ganhos (mesma API do StemMixer) ---------------------
    def set_gain(self, name: str, gain: float) -> None:
        self.gains.set_gain(name, gain)

    def set_muted(self, name: str, muted: bool) -> None:
        self.gains.set_muted(name, muted)

    def set_solo(self, name: Optional[str]) -> None:
        self.gains.set_solo(name)

    @property
    def latency_seconds(self) -> float:
        return self.W / self.samplerate

    # ---- núcleo DSP -------------------------------------------------------
    def prime(self) -> bool:
        """Enche a primeira janela. Retorna False se a captura acabar antes."""
        first = self._cap.read_exact(self.W)
        if first is None:
            return False
        self._window = first
        self._carry = np.zeros((self._nstems, self.H, CHANNELS), dtype=np.float32)
        return True

    def step(self) -> Optional[np.ndarray]:
        """Separa a janela, emite H frames por stem (empacotados) e desliza.

        NÃO aplica ganho aqui — o mix por fader é feito na saída, por bloco.
        Retorna [H, n_stems*2] ou None no fim.
        """
        stems = self._sep.separate(self._window, fast=True)
        stacked = np.stack([stems[n] for n in self.names])   # [S, W, 2]
        windowed = stacked * self._hann                       # [S, W, 2] (Hann)

        out = self._carry + windowed[:, : self.H, :]          # [S, H, 2] overlap-add
        self._carry = windowed[:, self.H:, :].copy()

        nxt = self._cap.read_exact(self.H)
        if nxt is None:
            return None
        self._window = np.concatenate([self._window[self.H:], nxt], axis=0)
        # empacota [S, H, 2] -> [H, S*2] para o ring
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
        except Exception as exc:  # noqa: BLE001
            print(f"[LiveEngine] erro no processamento: {exc}")
        finally:
            self.out_ring.close()

    # ---- saída de áudio ---------------------------------------------------
    def _mix_block(self, packed: np.ndarray) -> np.ndarray:
        """[n, n_stems*2] -> [n, 2] aplicando os ganhos ATUAIS (mute/solo)."""
        n = packed.shape[0]
        frames = packed.reshape(n, self._nstems, CHANNELS)   # [n, S, 2]
        g = self.gains.vector()                              # [S] (efetivo)
        mix = np.tensordot(frames, g, axes=(1, 0)).astype(np.float32)  # [n, 2]
        np.clip(mix, -1.0, 1.0, out=mix)
        return mix

    def _output_callback(self, outdata, frames, time_info, status):  # noqa: ANN001
        chunk, avail = self.out_ring.read(frames, block=False)
        if avail < frames:
            self.underruns += 1
        outdata[:] = self._mix_block(chunk)

    def _pump_to_pacat(self) -> None:
        """Lê o out_ring, mixa com os ganhos atuais e escreve no pacat."""
        try:
            while not self._stop.is_set():
                chunk, avail = self.out_ring.read(BLOCK_SIZE, block=True)
                if avail == 0:            # ring fechado e vazio -> fim
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
            # saída explícita no sink REAL via pacat (não segue o default,
            # que agora é o sink virtual) -> sem realimentação.
            pacat = shutil.which("pacat")
            if pacat is None:
                raise RuntimeError("'pacat' não encontrado no PATH.")
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
            # fallback (modo avançado, sem isolamento): sounddevice no default
            self._stream = sd.OutputStream(
                samplerate=self.samplerate,
                channels=CHANNELS,
                blocksize=BLOCK_SIZE,
                dtype="float32",
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
