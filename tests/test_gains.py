"""Tests for per-stem gain/mute/solo state."""

import numpy as np

from bandfoss.engine.gains import StemGains

NAMES = ["vocals", "drums", "bass", "other"]


def test_defaults_are_unity():
    g = StemGains(NAMES)
    assert list(g.vector()) == [1.0, 1.0, 1.0, 1.0]


def test_set_gain_clamps_negative_to_zero():
    g = StemGains(NAMES)
    g.set_gain("drums", 1.5)
    g.set_gain("bass", -3.0)
    v = dict(zip(NAMES, g.vector(), strict=True))
    assert v["drums"] == 1.5
    assert v["bass"] == 0.0


def test_mute_zeros_only_that_stem():
    g = StemGains(NAMES)
    g.set_muted("vocals", True)
    v = dict(zip(NAMES, g.vector(), strict=True))
    assert v["vocals"] == 0.0
    assert v["drums"] == 1.0


def test_solo_silences_everything_else():
    g = StemGains(NAMES)
    g.set_gain("bass", 0.5)
    g.set_solo("bass")
    v = dict(zip(NAMES, g.vector(), strict=True))
    assert v["bass"] == 0.5           # soloed stem keeps its own gain
    assert v["vocals"] == 0.0
    assert v["drums"] == 0.0


def test_solo_overrides_mute_on_the_soloed_stem():
    g = StemGains(NAMES)
    g.set_muted("vocals", True)
    g.set_solo("vocals")
    v = dict(zip(NAMES, g.vector(), strict=True))
    assert v["vocals"] == 1.0         # solo wins over its own mute


def test_clear_solo_restores_mute_state():
    g = StemGains(NAMES)
    g.set_muted("drums", True)
    g.set_solo("bass")
    g.set_solo(None)
    v = dict(zip(NAMES, g.vector(), strict=True))
    assert v["drums"] == 0.0          # still muted
    assert v["vocals"] == 1.0


def test_mix_is_weighted_sum_over_stems():
    g = StemGains(["a", "b"])
    g.set_gain("a", 2.0)
    g.set_gain("b", 0.5)
    # stacked: [n_stems, frames, channels]
    stacked = np.array(
        [
            [[1.0, 1.0], [1.0, 1.0]],   # stem a
            [[4.0, 4.0], [4.0, 4.0]],   # stem b
        ],
        dtype=np.float32,
    )
    mix = g.mix(stacked)              # 2*1 + 0.5*4 = 4
    assert mix.shape == (2, 2)
    assert np.allclose(mix, 4.0)
