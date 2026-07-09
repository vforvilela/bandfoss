"""Teste headless do pipeline: captura -> separação -> (opcional) mixagem.

Uso:
    python scripts/smoke_test.py <arquivo-ou-url> [--model htdemucs_ft] [--play]

Sem --play, apenas separa e imprime a energia (RMS) de cada stem — útil para
validar o pipeline sem placa de som / servidor gráfico.
"""

from __future__ import annotations

import argparse
import sys

import numpy as np


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("source", help="arquivo local ou URL")
    ap.add_argument("--model", default="htdemucs_ft")
    ap.add_argument("--play", action="store_true", help="tocar 5s do mix após separar")
    args = ap.parse_args()

    from bandfoss.capture.file_source import load_source
    from bandfoss.engine.separator import Separator

    print(f"[1/2] Carregando fonte: {args.source}")
    pcm = load_source(args.source)
    print(f"      PCM: {pcm.shape[0]} amostras, {pcm.shape[1]} canais "
          f"({pcm.shape[0] / 44100:.1f}s)")

    print(f"[2/2] Separando com '{args.model}' …")
    sep = Separator(args.model)
    print(f"      device = {sep.device}; stems = {sep.sources}")
    stems = sep.separate(pcm, progress=lambda p: print(f"      {p * 100:4.0f}%", end="\r"))
    print()

    for name, arr in stems.items():
        rms = float(np.sqrt(np.mean(arr ** 2)))
        print(f"      {name:8s}  RMS={rms:.4f}  shape={arr.shape}")

    if args.play:
        from bandfoss.engine.mixer import StemMixer
        import time

        mixer = StemMixer(stems, samplerate=sep.samplerate)
        mixer.play()
        print("      tocando 5s…")
        time.sleep(5)
        mixer.close()

    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
