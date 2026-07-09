"""Demucs wrapper for stem separation (uses CUDA/MPS when available)."""

from __future__ import annotations

from collections.abc import Callable

import numpy as np

from ..config import DEFAULT_MODEL, SAMPLE_RATE

ProgressCb = Callable[[float], None] | None


class Separator:
    """Load a Demucs model and separate PCM into a dict of stems.

    The heavy dependencies (torch/demucs) are only imported when a `Separator`
    is instantiated, keeping UI startup light.
    """

    def __init__(self, model_name: str = DEFAULT_MODEL, device: str | None = None):
        import torch  # lazy import: only when we actually separate
        from demucs.pretrained import get_model

        self._torch = torch
        self.device = device or self._auto_device(torch)
        self.model = get_model(model_name).to(self.device)
        self.model.eval()
        self.model_name = model_name
        # Stem names in the exact order the model produces them.
        self.sources = list(self.model.sources)

    @staticmethod
    def _auto_device(torch) -> str:  # noqa: ANN001 — torch module, typed lazily
        """Best available accelerator: CUDA (NVIDIA) -> MPS (Mac) -> CPU."""
        if torch.cuda.is_available():
            return "cuda"
        mps = getattr(torch.backends, "mps", None)
        if mps is not None and mps.is_available():
            return "mps"
        return "cpu"

    @property
    def samplerate(self) -> int:
        return getattr(self.model, "samplerate", SAMPLE_RATE)

    def separate(
        self,
        pcm: np.ndarray,
        progress: ProgressCb = None,
        fast: bool = False,
        shifts: int | None = None,
    ) -> dict[str, np.ndarray]:
        """Separate PCM [samples, 2] float32 into {stem_name: [samples, 2] float32}.

        `progress` receives a float 0.0..1.0 (approximate) while processing.
        `fast=True` (used live): processes the whole window with no split/overlap,
        favoring latency over maximum quality.
        `shifts`: random-offset passes whose average reduces artifacts. If None,
        defaults to 0 in fast mode and 1 otherwise.
        """
        from demucs.apply import apply_model

        torch = self._torch
        if pcm.ndim != 2 or pcm.shape[1] != 2:
            raise ValueError("pcm must have shape [samples, 2] (stereo).")

        # demucs expects [batch, channels, samples]
        wav = torch.from_numpy(pcm.T).unsqueeze(0).to(self.device)

        # Per-mix normalization recommended by demucs.
        ref = wav.mean(dim=1, keepdim=True)
        mean = ref.mean()
        std = ref.std() + 1e-8
        wav = (wav - mean) / std

        if progress:
            progress(0.05)

        n_shifts = shifts if shifts is not None else (0 if fast else 1)
        with torch.no_grad():
            sources = apply_model(
                self.model,
                wav,
                device=self.device,
                shifts=n_shifts,
                split=not fast,
                overlap=0.0 if fast else 0.25,
                progress=False,
            )

        if progress:
            progress(0.95)

        sources = sources * std + mean
        sources = sources.squeeze(0).cpu().numpy()  # [n_sources, channels, samples]

        stems: dict[str, np.ndarray] = {}
        for name, arr in zip(self.sources, sources, strict=False):
            stems[name] = np.ascontiguousarray(arr.T, dtype=np.float32)  # [samples, 2]

        if progress:
            progress(1.0)
        return stems
