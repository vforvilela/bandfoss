"""Tests for stem ordering in config."""

from bandfoss.config import order_stems


def test_known_stems_follow_canonical_order():
    # Demucs emits drums, bass, other, vocals — UI wants vocals first, other last.
    got = order_stems(["drums", "bass", "other", "vocals"])
    assert got == ["vocals", "drums", "bass", "other"]


def test_six_stems_place_other_last():
    got = order_stems(["drums", "bass", "other", "vocals", "guitar", "piano"])
    assert got == ["vocals", "drums", "bass", "guitar", "piano", "other"]


def test_unknown_stems_are_appended_after_known():
    got = order_stems(["vocals", "mystery", "drums"])
    assert got == ["vocals", "drums", "mystery"]


def test_empty_input():
    assert order_stems([]) == []
