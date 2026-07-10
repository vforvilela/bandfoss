"""Tests for the platform capture factory and the feedback guard."""

import pytest

from bandfoss.capture import (
    make_capture,
    would_feedback,
)


def test_make_capture_windows_returns_wasapi_without_soundcard():
    # soundcard is imported lazily inside the backend, so construction works
    # even on a box without it installed.
    cap = make_capture(device="Speakers", system="Windows")
    assert type(cap).__name__ == "WasapiLoopbackCapture"
    assert cap.device_name == "Speakers"


def test_make_capture_macos_returns_coreaudio():
    cap = make_capture(device="BlackHole 2ch", system="Darwin")
    assert type(cap).__name__ == "CoreAudioCapture"
    assert cap.device_name == "BlackHole 2ch"


def test_make_capture_linux_returns_pipewire():
    cap = make_capture(device="foo.monitor", system="Linux")
    assert type(cap).__name__ == "LiveCapture"


def test_make_capture_unsupported_os_raises():
    with pytest.raises(RuntimeError):
        make_capture(system="Plan9")


def test_would_feedback():
    assert would_feedback("Speakers", "Speakers") is True
    assert would_feedback("VB-Cable", "Speakers") is False
    assert would_feedback(None, None) is False
    assert would_feedback("Speakers", None) is False
