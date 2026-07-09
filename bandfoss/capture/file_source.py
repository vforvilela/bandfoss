"""Fonte de áudio: arquivo local, URL (YouTube Music/YouTube) ou busca por texto.

Entrega sempre um `numpy.ndarray` float32 em [amostras, 2] a 44.1 kHz, pronto
para o separador. `ffmpeg` normaliza qualquer formato; `yt-dlp` baixa de URLs e
resolve buscas por texto (pega o primeiro resultado).
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import parse_qs, urlparse

import numpy as np
import soundfile as sf

from ..config import CHANNELS, SAMPLE_RATE

StatusCb = Optional[Callable[[str], None]]


def _require(tool: str) -> str:
    path = shutil.which(tool)
    if path is None:
        raise RuntimeError(
            f"'{tool}' não encontrado no PATH. Instale-o para continuar."
        )
    return path


def is_url(source: str) -> bool:
    return source.startswith(("http://", "https://"))


def resolve_target(source: str) -> str:
    """Converte a entrada do usuário no alvo que o yt-dlp entende.

    - URL de faixa (watch?v=…) -> a própria URL
    - URL de busca (…/search?q=algo) -> `ytsearch1:algo`
    - texto livre ("we are the champions") -> `ytsearch1:we are the champions`
    """
    if is_url(source):
        parsed = urlparse(source)
        if "/search" in parsed.path or parsed.path.endswith("/results"):
            q = parse_qs(parsed.query).get("q") or parse_qs(parsed.query).get("search_query")
            if q:
                return f"ytsearch1:{q[0]}"
        return source
    # não é URL nem arquivo local -> trata como busca
    return f"ytsearch1:{source}"


def _download(target: str, dest_dir: Path, status: StatusCb = None) -> Path:
    """Baixa o melhor áudio de `target` (URL ou `ytsearch1:…`) com yt-dlp."""
    ytdlp = _require("yt-dlp")
    if status:
        status("Baixando áudio…")
    out_template = str(dest_dir / "download.%(ext)s")
    proc = subprocess.run(
        [
            ytdlp,
            "--no-playlist",
            "-f", "bestaudio/best",
            "-x", "--audio-format", "wav",
            "-o", out_template,
            target,
        ],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-3:]
        raise RuntimeError("Falha no yt-dlp:\n" + "\n".join(tail))
    files = list(dest_dir.glob("download.*"))
    if not files:
        raise RuntimeError("yt-dlp não produziu nenhum arquivo de áudio.")
    return files[0]


def _to_wav(src: Path, dest: Path, status: StatusCb = None) -> None:
    """Normaliza para WAV PCM 16-bit, 44.1 kHz, estéreo via ffmpeg."""
    ffmpeg = _require("ffmpeg")
    if status:
        status("Convertendo…")
    subprocess.run(
        [
            ffmpeg, "-y",
            "-i", str(src),
            "-ac", str(CHANNELS),
            "-ar", str(SAMPLE_RATE),
            "-c:a", "pcm_s16le",
            str(dest),
        ],
        check=True,
        capture_output=True,
        text=True,
    )


def load_source(source: str, status: StatusCb = None) -> np.ndarray:
    """Resolve `source` para PCM float32 [amostras, 2].

    `source` pode ser: caminho local, URL (faixa ou busca), ou texto de busca.
    `status` recebe mensagens curtas de progresso ("Baixando…", "Convertendo…").
    """
    source = source.strip()
    with tempfile.TemporaryDirectory(prefix="bandfoss_") as tmp:
        tmp_dir = Path(tmp)

        local = Path(source).expanduser()
        if not is_url(source) and local.exists():
            raw = local
        else:
            raw = _download(resolve_target(source), tmp_dir, status)

        wav = tmp_dir / "normalized.wav"
        _to_wav(raw, wav, status)

        audio, sr = sf.read(str(wav), dtype="float32", always_2d=True)

    if sr != SAMPLE_RATE:  # ffmpeg já reamostra, mas garantimos a invariante
        raise RuntimeError(f"Sample rate inesperado: {sr} != {SAMPLE_RATE}")

    if audio.shape[1] == 1:  # mono -> estéreo
        audio = np.repeat(audio, 2, axis=1)
    elif audio.shape[1] > 2:
        audio = audio[:, :2]

    return np.ascontiguousarray(audio, dtype=np.float32)
