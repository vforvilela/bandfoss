"""Headless pipeline test: load -> separate -> (optional) mix.

Usage:
    python scripts/smoke_test.py <file-or-url> [--model htdemucs_ft] [--play]

Without --play, it only separates and prints each stem's energy (RMS) — handy
to validate the pipeline with no sound card / display server.
"""

from __future__ import annotations

import sys

import numpy as np


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("source", help="local file or URL")
    ap.add_argument("--model", default="htdemucs_ft")
    ap.add_argument("--play", action="store_true", help="play 5s of the mix after separating")
    args = ap.parse_args()

    from bandfoss.capture.file_source import load_source
    from bandfoss.engine.separator import Separator

    print(f"[1/2] Loading source: {args.source}")
    pcm = load_source(args.source)
    print(f"      PCM: {pcm.shape[0]} samples, {pcm.shape[1]} channels "
          f"({pcm.shape[0] / 44100:.1f}s)")

    print(f"[2/2] Separating with '{args.model}' …")
    sep = Separator(args.model)
    print(f"      device = {sep.device}; stems = {sep.sources}")
    stems = sep.separate(pcm, progress=lambda p: print(f"      {p * 100:4.0f}%", end="\r"))
    print()

    for name, arr in stems.items():
        rms = float(np.sqrt(np.mean(arr ** 2)))
        print(f"      {name:8s}  RMS={rms:.4f}  shape={arr.shape}")

    if args.play:
        import time

        from bandfoss.engine.mixer import StemMixer

        mixer = StemMixer(stems, samplerate=sep.samplerate)
        mixer.play()
        print("      playing 5s…")
        time.sleep(5)
        mixer.close()

    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
