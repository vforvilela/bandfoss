"""Central configuration for BandFOSS."""

from __future__ import annotations

# Audio ----------------------------------------------------------------------
SAMPLE_RATE = 44100          # Demucs operates natively at 44.1 kHz
CHANNELS = 2                 # stereo
BLOCK_SIZE = 1024            # frames per sounddevice callback (~23 ms)

# Demucs models --------------------------------------------------------------
# htdemucs_ft -> 4 stems (drums, bass, other, vocals) [best 4-stem quality];
# used by the offline helper (scripts/smoke_test.py).
DEFAULT_MODEL = "htdemucs_ft"

# Models available in LIVE capture (id -> Demucs model name). The displayed
# label comes from i18n (model_<id>). "fast4" = 4 stems; "guitar6" = 6 stems.
LIVE_MODELS = {
    "fast4": "htdemucs",
    "guitar6": "htdemucs_6s",
}

# Sliding window for live separation.
# Latency ~= LIVE_WINDOW_SEC (NOT the processing time; it is inherent to the
# algorithm: the window must fill before the first separation). 50% overlap
# (hop = window/2) gives perfect overlap-add with a Hann window. Smaller window
# = less latency, lower quality.
LIVE_WINDOW_SEC = 2.0            # default (id "medium")

# Live latency options (id -> window in seconds). Label comes from i18n.
LIVE_WINDOWS = {
    "low": 1.0,
    "medium": 2.0,
    "high": 3.0,
    "max": 6.0,
}

# Demucs "shifts" in live mode: random-offset passes whose average reduces
# artifacts. More = better and slower; a modern GPU handles it comfortably.
LIVE_SHIFTS = 2

# Fader display order in the UI: vocals first, "other" last.
STEM_ORDER = ["vocals", "drums", "bass", "guitar", "piano", "other"]


def order_stems(names: list[str]) -> list[str]:
    """Reorder stems for display: vocals first, 'other' last."""
    known = [s for s in STEM_ORDER if s in names]
    rest = [s for s in names if s not in STEM_ORDER]
    return known + rest


# Per-channel color (mixer-style color code). Distinct hues, legible on dark.
STEM_COLORS = {
    "vocals": "#4CC2C4",   # teal — vocals
    "drums": "#E5484D",    # red — drums
    "bass": "#7C5CFF",     # violet — bass
    "other": "#F2A93B",    # amber — other
    "guitar": "#6FCF57",   # green — guitar
    "piano": "#C77DFF",    # lilac — piano
}
