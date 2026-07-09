"""Tests for the thread-safe FloatRing buffer."""

import numpy as np

from bandfoss.engine.ring import FloatRing


def _ramp(n, ch=2, start=0.0):
    """Build a [n, ch] block whose first column counts up from `start`."""
    col = np.arange(start, start + n, dtype=np.float32)
    return np.repeat(col[:, None], ch, axis=1)


def test_write_then_read_roundtrip():
    ring = FloatRing(16, channels=2)
    ring.write(_ramp(4))
    out, avail = ring.read(4)
    assert avail == 4
    assert np.array_equal(out, _ramp(4))
    assert ring.available == 0


def test_read_more_than_available_zero_fills():
    ring = FloatRing(16, channels=2)
    ring.write(_ramp(2))
    out, avail = ring.read(5)
    assert avail == 2
    assert out.shape == (5, 2)
    assert np.array_equal(out[:2], _ramp(2))
    assert np.all(out[2:] == 0.0)


def test_wrap_around_preserves_order():
    ring = FloatRing(4, channels=1)
    ring.write(_ramp(3, ch=1, start=0))   # [0,1,2]
    out, _ = ring.read(2)                  # consume [0,1]
    ring.write(_ramp(3, ch=1, start=3))   # [3,4,5] wraps past the end
    out, avail = ring.read(4)
    assert avail == 4
    assert list(out[:, 0]) == [2.0, 3.0, 4.0, 5.0]


def test_overflow_drops_oldest():
    ring = FloatRing(4, channels=1)
    ring.write(_ramp(6, ch=1, start=0))   # only the last 4 survive
    out, avail = ring.read(4)
    assert avail == 4
    assert list(out[:, 0]) == [2.0, 3.0, 4.0, 5.0]


def test_write_larger_than_capacity_keeps_tail():
    ring = FloatRing(3, channels=1)
    ring.write(_ramp(10, ch=1, start=0))
    out, avail = ring.read(3)
    assert avail == 3
    assert list(out[:, 0]) == [7.0, 8.0, 9.0]


def test_read_block_returns_after_close():
    ring = FloatRing(8, channels=2)
    ring.close()
    out, avail = ring.read(4, block=True)   # must not hang once closed
    assert avail == 0
    assert out.shape == (4, 2)
