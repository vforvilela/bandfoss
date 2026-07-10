# BandFOSS (open source) — Architecture

Real-time stem separation on the Linux desktop, inspired by the **JBL BandBox
STEM AI**, built on open-source tools. It isolates/mutes vocals, drums, bass,
guitar, etc. from **whatever is playing on your computer** — to play along, do
karaoke, or practice.

> Feature reference: JBL BandBox Solo/Trio (`STEM AI`) and Moises.ai / RipX.
> Open-source equivalent of the core: **Demucs** (Meta).

## Goal

Reproduce the JBL BandBox STEM AI experience on the desktop, **live**:

- Tap the audio of any app playing on the system (Spotify, browser, a game…).
- Separate it into stems: **vocals / drums / bass / other** (4-stem) or
  **+ guitar / piano** (6-stem, `htdemucs_6s` model).
- Mixer with fader + mute/solo per stem, in real time, as it plays.

The shipped app is **live only**. An offline path (load a file/URL, separate,
play) still exists as a developer/test utility — see
[`scripts/smoke_test.py`](scripts/smoke_test.py) and the "offline helper"
modules below — but it is not exposed in the UI.

## Overview

```
┌─────────────┐   ┌──────────────┐   ┌───────────────┐   ┌──────────┐
│  SOURCE     │──▶│  CAPTURE     │──▶│  SEPARATION   │──▶│  MIXER   │──▶ output
│ live system │   │  PipeWire    │   │  Demucs (GPU) │   │ N gains  │   (speaker)
│ audio       │   │  (parec)     │   │  htdemucs     │   │ mute/solo│
└─────────────┘   └──────────────┘   └───────────────┘   └──────────┘
```

## Layers

### 1. Source capture

| Source | Mechanism | Status |
|---|---|---|
| Live system audio, Linux (Spotify, browser, …) | **PipeWire** monitor (`parec`) | **Shipped** |
| Per-app isolation, Linux | virtual sink + `pactl` routing | **Shipped** |
| Live system audio, Windows | **WASAPI loopback** (`soundcard`) | **Shipped** |
| Local file / URL (mp3/wav/… or YouTube) | `ffmpeg` / `yt-dlp` → PCM | Offline helper (test only) |
| Live system audio, macOS | virtual device (BlackHole) | Not implemented |

Backends live behind one interface (`capture/base.py`: `CaptureBackend` +
`BaseRingCapture`) and are picked per-OS by `capture.make_capture()`. `LiveEngine`
only depends on `read_exact(n)`, so a new OS is a new backend, nothing else.

**Per-app isolation is Linux-only.** PipeWire lets us route a single app to a
silent virtual sink and capture only that. Windows/macOS have no clean per-app
routing from Python, so there BandFOSS captures the whole system output.

**Avoiding self-capture (feedback).** Loopback/monitor capture records everything
going to a device, including our own output. On Linux the virtual-sink trick keeps
the source and our output separate. On Windows the rule is enforced in the UI:
capture device must differ from the output device (`capture.would_feedback`); a
virtual cable (VB-CABLE) gives the cleanest routing.

**Legal/ToS note:** capturing the already-decoded audio on its way to the sound
card is the most defensible route. `yt-dlp` is only used by the offline test
helper, never as a core dependency of the app.

### 2. Separation (core)

- Engine: **Demucs** (`htdemucs` fast for live 4-stem / `htdemucs_6s` for 6 stems).
- Runs on **CUDA** (NVIDIA) or **MPS** (Mac), falling back to CPU — a modern GPU
  separates a window in tens of milliseconds.
- Our own wrapper ([`engine/separator.py`](bandfoss/engine/separator.py)) exposes
  `separate(pcm) -> {stem: array}`.

### 3. Mixer + playback

- Playback via **sounddevice** (PortAudio) with a low-latency callback, or via
  `pacat` to an explicit sink when isolating an app (see routing below).
- The mix is a **weighted sum** of the stems by the fader gains — computed per
  block on output, so touching a fader/mute is reflected in the sound
  immediately.

### 4. UI

- **PySide6** (Qt) — all Python, one process for the window.
- Vertical faders + mute/solo per stem, live capture controls, advanced panel.
- Model loading and separation run off the UI thread (`QThread` / worker thread).

## Roadmap

- **Phase 1 — Offline MVP** ✅ (now a test utility)
  file/URL → Demucs → mixer with faders. Perfect sync, maximum quality.
- **Phase 2 — Real time** ✅ (the shipped app)
  PipeWire monitor capture (`parec`) → sliding window (W=2s default, hop=W/2) →
  Demucs `htdemucs` (fast) → overlap-add with a periodic Hann window (exact COLA)
  → output. The same faders control the live mix. Latency ≈ window size.

  **Audio isolation (avoids mixing and feedback):** a *virtual sink*
  (`module-null-sink`) receives the app's audio (silent on the speakers); we
  capture ITS monitor and play the processed result **on the real speaker** via
  `pacat` (explicit device, does not follow the default). This way the original
  never leaks to the speakers and the output is not recaptured. On shutdown the
  streams are moved back and the virtual sink is removed.

  ```
  app (Spotify) ─► [virtual sink bandfoss_capture] ─► monitor ─► capture
                        (no speaker)                                │
                                                                    ▼
                                              Demucs + mix + overlap-add
                                                                    │
                                          pacat ─► [REAL sink] ─► speaker
  ```
- **Phase 3 — Polish** — named presets, stem export, waveform, per-stem EQ,
  live track-change detection, more window/latency options in the UI.

### Live overlap-add detail

```
window k (W frames) ──► Demucs (fast) ──► stems ──► gain mix ──► × Hann(W)
                                                                     │
        A = mixed[:W/2]   B = mixed[W/2:]                            │
        out(k) = carry + A     (H final frames)  ◄── carry = B(k-1) ─┘
        carry ← B ; window slides H frames
```

A periodic Hann window (`0.5 - 0.5·cos(2πn/W)`) sums to a constant (COLA = 1) at
the 50% hop, so the reconstruction is exact and free of amplitude *pumping*
between windows — the window also attenuates Demucs' edge artifacts.

**Latency vs. control responsiveness (two distinct delays):**

- *Audio latency* ≈ window size `W` (the window must fill before the 1st
  separation). It is NOT the GPU time (~hundreds of ms). That is why it is
  adjustable in the UI: a smaller window = less delay, slightly worse
  separation. The GPU has plenty of headroom.
- *Control responsiveness* — the separated stems go to the ring **without gain**;
  the fader/mute/solo mix is applied **at output, per block (~23 ms)**. So moving
  a fader affects the next block immediately, regardless of window/hop. (If gain
  were applied at separation time, controls would lag by up to one hop.)

Fader order in the UI: **vocals first, "other" last** (`order_stems`).

## Project structure

```
bandbox/
├── pyproject.toml
├── LICENSE                      # MIT
├── ARCHITECTURE.md              # this file
├── README.md
├── bandfoss/
│   ├── config.py                # sample rate, models, stem names/colors/order
│   ├── i18n.py                  # minimal EN/PT-BR strings
│   ├── util.py                  # shared helpers (require_tool)
│   ├── capture/
│   │   ├── base.py              # CaptureBackend + BaseRingCapture + FakeCapture
│   │   ├── __init__.py          # make_capture() factory + feedback guard
│   │   ├── live_source.py       # PipeWire monitor → PCM         [live, Linux]
│   │   ├── router.py            # per-app virtual-sink routing   [live, Linux]
│   │   ├── wasapi_source.py     # WASAPI loopback → PCM          [live, Windows]
│   │   └── file_source.py       # local file / URL → PCM        [offline helper]
│   ├── engine/
│   │   ├── separator.py         # Demucs wrapper (GPU/CPU)
│   │   ├── live_engine.py       # sliding window + overlap-add         [live]
│   │   ├── mixer.py             # offline weighted-sum player   [offline helper]
│   │   ├── gains.py             # per-stem gain/mute/solo state (shared)
│   │   └── ring.py              # thread-safe float ring buffer
│   ├── ui/
│   │   ├── main_window.py       # PySide6: faders, live controls
│   │   └── theme.py             # "Tube Amp" stylesheet
│   └── app.py                   # entry point
├── scripts/
│   └── smoke_test.py            # headless offline pipeline check
├── tests/                       # unit tests (pytest)
└── docs/reference/              # JBL manuals & notes (reference only)
```

## Risks / recorded decisions

1. **Legal/ToS:** capture via the PipeWire monitor is the primary route; the
   downloader is an optional test-only helper.
2. **Real-time latency** is inherent to Demucs (it needs future context). The
   sliding window is the realistic ceiling — we do not promise "zero latency".
3. **Live capture has no metadata** (track name, song change) — detection is
   left for Phase 3.

## Target environment

- **Linux** (PipeWire) or **Windows** (WASAPI), Python 3.10+, NVIDIA GPU (CUDA)
  recommended — also runs on CPU. macOS separation works (MPS) but live capture
  isn't wired yet. `ffmpeg` + `yt-dlp` on PATH only for the offline helper.
