"""Drive the whole live DSP pipeline with a fake capture — no audio hardware.

FakeCapture feeds a known signal; a fake separator splits it into two stems;
LiveEngine runs prime/step/overlap-add and writes the mixed stems to its ring.
This exercises the platform-independent core end to end on any OS.
"""

import numpy as np

from bandfoss.capture import FakeCapture
from bandfoss.engine.live_engine import LiveEngine


class FakeSeparator:
    """Splits the input into two stems that sum back to it (identity check)."""

    sources = ["vocals", "other"]

    def separate(self, pcm, fast=False, shifts=None):
        half = (pcm * 0.5).astype(np.float32)
        return {"vocals": half, "other": half.copy()}


def _sine(seconds, sr=44100, freq=220.0):
    n = int(seconds * sr)
    t = np.arange(n, dtype=np.float32) / sr
    mono = 0.2 * np.sin(2 * np.pi * freq * t).astype(np.float32)
    return np.stack([mono, mono], axis=1)   # [n, 2]


def test_pipeline_produces_finite_output():
    sr = 44100
    signal = _sine(1.0, sr=sr)              # 1s of audio -> several windows
    cap = FakeCapture(signal, block=2048, samplerate=sr)
    window_frames = int(0.5 * sr)           # small window for a fast test

    eng = LiveEngine(
        FakeSeparator(), cap, window_frames=window_frames,
        samplerate=sr, start_output=False,  # no sounddevice stream in tests
    )
    cap.start()
    eng.start()

    # collect whatever the engine emits until its processing thread finishes
    collected = []
    while eng._thread.is_alive() or eng.out_ring.available > 0:
        chunk, avail = eng.out_ring.read(window_frames, block=False)
        if avail:
            collected.append(chunk[:avail])
        else:
            eng._thread.join(timeout=0.2)
    eng.stop()
    cap.stop()

    out = np.concatenate(collected) if collected else np.zeros((0,))
    assert out.size > 0                     # something came out
    assert np.all(np.isfinite(out))         # no NaNs/inf from the DSP
    # packed layout is [frames, n_stems * channels] = [frames, 4]
    assert out.shape[1] == len(FakeSeparator.sources) * 2


def test_latency_seconds_matches_window():
    sr = 44100
    cap = FakeCapture(_sine(0.2, sr=sr), samplerate=sr)
    eng = LiveEngine(FakeSeparator(), cap, window_frames=sr, samplerate=sr,
                     start_output=False)
    assert abs(eng.latency_seconds - 1.0) < 1e-6   # window == 1s
