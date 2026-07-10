# Contributing to BandFOSS

Thanks for your interest! BandFOSS is a small, focused project — contributions
that improve clarity, correctness, and the live-audio experience are very
welcome.

## Development setup

BandFOSS runs on **Linux** (PipeWire), **Windows** (WASAPI loopback), and
**macOS** (BlackHole), on **Python 3.10+**. The examples below use Linux; on
Windows/macOS use a `python -m venv` env and `pip install -e .` (the `soundcard`
Windows capture dep installs automatically; macOS uses `sounddevice`, already a
core dep, plus a one-time BlackHole install — see the README).

```bash
git clone https://github.com/vforvilela/bandfoss.git
cd bandfoss
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"        # app + pytest + ruff
```

System tools used at runtime (install via your package manager):

- `pipewire-pulse` (provides `pactl`, `parec`, `pacat`) — required for live capture
- `ffmpeg`, `yt-dlp` — only for the offline helper (`scripts/smoke_test.py`)

## Running

```bash
bandfoss                       # launch the app
BANDFOSS_LANG=pt bandfoss       # Portuguese UI

# Headless pipeline check (needs a file/URL; separates and prints stem RMS):
python scripts/smoke_test.py path/to/song.mp3
```

## Linting and tests

```bash
ruff check .                   # lint
ruff format .                  # format
pytest                         # unit tests
```

Please run `ruff check` and `pytest` before opening a pull request. The unit
tests cover the pure-logic core (ring buffer, gain/mute/solo state, stem
ordering, URL parsing) and do **not** require a GPU, sound card, or PipeWire.

## Code conventions

- **Language:** code, comments, docstrings, and commit messages are in
  **English**. User-facing UI strings live in [`bandfoss/i18n.py`](bandfoss/i18n.py)
  (English + PT-BR) — add new strings there rather than hard-coding text.
- **Style:** follow the existing style; `ruff` (config in `pyproject.toml`) is
  the source of truth. Docstrings use the Google convention.
- **External tools:** resolve binaries through `bandfoss.util.require_tool` so a
  missing dependency fails with a clear message.
- **Audio threads:** anything touching the audio callback or shared gain state
  must stay thread-safe (see `engine/ring.py` and `engine/gains.py`).

## Architecture

Read [`ARCHITECTURE.md`](ARCHITECTURE.md) for the layered design (capture →
separation → mixer → UI) and the live overlap-add / latency details.

## Reporting issues

Include your OS/distro, Python version, GPU (or CPU), and the exact steps.
For live-capture problems, mention the app you were capturing and whether
"Isolate by app" was on.

## License

By contributing you agree that your contributions are licensed under the
project's [MIT License](LICENSE).
