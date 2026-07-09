"""Audio source: local file, URL (YouTube Music/YouTube) or free-text search.

Always returns a float32 `numpy.ndarray` of shape [samples, 2] at 44.1 kHz,
ready for the separator. `ffmpeg` normalizes any format; `yt-dlp` downloads from
URLs and resolves text searches (takes the first result).

This is the offline path, used by scripts/smoke_test.py. The shipped app runs
live only (see capture/live_source.py).
"""

from __future__ import annotations

import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import numpy as np
import soundfile as sf

from ..config import CHANNELS, SAMPLE_RATE
from ..util import require_tool

StatusCb = Callable[[str], None] | None


def is_url(source: str) -> bool:
    return source.startswith(("http://", "https://"))


def resolve_target(source: str) -> str:
    """Turn user input into the target yt-dlp understands.

    - Track URL (watch?v=…) -> the URL itself
    - Search URL (…/search?q=something) -> `ytsearch1:something`
    - Free text ("we are the champions") -> `ytsearch1:we are the champions`
    """
    if is_url(source):
        parsed = urlparse(source)
        if "/search" in parsed.path or parsed.path.endswith("/results"):
            q = parse_qs(parsed.query).get("q") or parse_qs(parsed.query).get("search_query")
            if q:
                return f"ytsearch1:{q[0]}"
        return source
    # neither a URL nor a local file -> treat as a search
    return f"ytsearch1:{source}"


def _download(target: str, dest_dir: Path, status: StatusCb = None) -> Path:
    """Download the best audio for `target` (URL or `ytsearch1:…`) with yt-dlp."""
    ytdlp = require_tool("yt-dlp")
    if status:
        status("Downloading audio…")
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
        raise RuntimeError("yt-dlp failed:\n" + "\n".join(tail))
    files = list(dest_dir.glob("download.*"))
    if not files:
        raise RuntimeError("yt-dlp produced no audio file.")
    return files[0]


def _to_wav(src: Path, dest: Path, status: StatusCb = None) -> None:
    """Normalize to WAV PCM 16-bit, 44.1 kHz, stereo via ffmpeg."""
    ffmpeg = require_tool("ffmpeg")
    if status:
        status("Converting…")
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
    """Resolve `source` to float32 PCM [samples, 2].

    `source` can be: a local path, a URL (track or search), or search text.
    `status` receives short progress messages ("Downloading…", "Converting…").
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

    if sr != SAMPLE_RATE:  # ffmpeg already resamples, but we enforce the invariant
        raise RuntimeError(f"Unexpected sample rate: {sr} != {SAMPLE_RATE}")

    if audio.shape[1] == 1:  # mono -> stereo
        audio = np.repeat(audio, 2, axis=1)
    elif audio.shape[1] > 2:
        audio = audio[:, :2]

    return np.ascontiguousarray(audio, dtype=np.float32)
