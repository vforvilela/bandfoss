"""Wrapper do Demucs para separação de stems (com CUDA quando disponível)."""

from __future__ import annotations

from typing import Callable, Dict, Optional

import numpy as np

from ..config import DEFAULT_MODEL, SAMPLE_RATE

ProgressCb = Optional[Callable[[float], None]]


class Separator:
    """Carrega um modelo Demucs e separa PCM em um dicionário de stems.

    O modelo pesado (torch/demucs) só é importado quando o `Separator` é
    instanciado — mantém a inicialização da UI leve.
    """

    def __init__(self, model_name: str = DEFAULT_MODEL, device: Optional[str] = None):
        import torch  # import tardio: só quando realmente separamos
        from demucs.pretrained import get_model

        self._torch = torch
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.model = get_model(model_name).to(self.device)
        self.model.eval()
        self.model_name = model_name
        # Nomes dos stems na ordem exata que o modelo produz.
        self.sources = list(self.model.sources)

    @property
    def samplerate(self) -> int:
        return getattr(self.model, "samplerate", SAMPLE_RATE)

    def separate(self, pcm: np.ndarray, progress: ProgressCb = None) -> Dict[str, np.ndarray]:
        """Separa PCM [amostras, 2] float32 em {nome_stem: [amostras, 2] float32}.

        `progress` recebe um float 0.0..1.0 (aproximado) durante o processamento.
        """
        from demucs.apply import apply_model

        torch = self._torch
        if pcm.ndim != 2 or pcm.shape[1] != 2:
            raise ValueError("pcm deve ter formato [amostras, 2] (estéreo).")

        # demucs espera [batch, canais, amostras]
        wav = torch.from_numpy(pcm.T).unsqueeze(0).to(self.device)

        # Normalização recomendada pelo demucs (por-mix).
        ref = wav.mean(dim=1, keepdim=True)
        mean = ref.mean()
        std = ref.std() + 1e-8
        wav = (wav - mean) / std

        if progress:
            progress(0.05)

        with torch.no_grad():
            sources = apply_model(
                self.model,
                wav,
                device=self.device,
                shifts=1,
                split=True,
                overlap=0.25,
                progress=False,
            )

        if progress:
            progress(0.95)

        sources = sources * std + mean
        sources = sources.squeeze(0).cpu().numpy()  # [n_sources, canais, amostras]

        stems: Dict[str, np.ndarray] = {}
        for name, arr in zip(self.sources, sources):
            stems[name] = np.ascontiguousarray(arr.T, dtype=np.float32)  # [amostras, 2]

        if progress:
            progress(1.0)
        return stems
