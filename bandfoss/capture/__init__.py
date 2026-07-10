"""Capture layer: turns a source into stereo 44.1 kHz PCM.

`make_capture` returns the right backend for the OS (Linux -> PipeWire,
Windows -> WASAPI loopback). Device enumeration and the anti-feedback check are
here too so the UI stays platform-agnostic.
"""

from __future__ import annotations

import platform

from .base import CaptureBackend, FakeCapture  # re-exported


def make_capture(
    device: str | None = None,
    *,
    system: str | None = None,
    **kwargs,
) -> CaptureBackend:
    """Build a capture backend for this OS.

    `system` overrides `platform.system()` (used by tests). Raises on any OS
    without a live-capture backend yet (e.g. macOS).
    """
    system = system or platform.system()
    if system == "Windows":
        from .wasapi_source import WasapiLoopbackCapture
        return WasapiLoopbackCapture(device=device, **kwargs)
    if system == "Darwin":
        from .coreaudio_source import CoreAudioCapture
        return CoreAudioCapture(device=device, **kwargs)
    if system == "Linux":
        from .live_source import LiveCapture
        return LiveCapture(device=device, **kwargs)
    raise RuntimeError(f"Live capture is not supported on {system} yet.")


def list_capture_devices(system: str | None = None) -> list[str]:
    """Device names available for capture on this OS (best effort, [] on error)."""
    system = system or platform.system()
    try:
        if system == "Windows":
            from .wasapi_source import list_loopback_devices
            return list_loopback_devices()
        if system == "Darwin":
            from .coreaudio_source import list_input_devices
            return list_input_devices()
        if system == "Linux":
            from .live_source import list_monitors
            return list_monitors()
    except Exception:  # noqa: BLE001 - no backend / tools present
        return []
    return []


def list_output_devices(system: str | None = None) -> list[str]:
    """Playback device names for the Output selector (best effort, [] on error).

    On Windows the capturable devices are the outputs (loopback), so the same
    list serves both; on macOS outputs are distinct from inputs.
    """
    system = system or platform.system()
    try:
        if system == "Windows":
            from .wasapi_source import list_loopback_devices
            return list_loopback_devices()
        if system == "Darwin":
            from .coreaudio_source import list_output_devices as _outs
            return _outs()
    except Exception:  # noqa: BLE001
        return []
    return []


def default_capture_device(system: str | None = None) -> str | None:
    """Default capture device name for this OS, or None if unavailable."""
    system = system or platform.system()
    try:
        if system == "Windows":
            from .wasapi_source import default_loopback
            return default_loopback()
        if system == "Darwin":
            from .coreaudio_source import default_input_device
            return default_input_device()
        if system == "Linux":
            from .live_source import default_monitor
            return default_monitor()
    except Exception:  # noqa: BLE001
        return None
    return None


def would_feedback(capture_device: str | None, output_device: str | None) -> bool:
    """Report whether capture and output are the same device (a feedback loop)."""
    return bool(capture_device) and capture_device == output_device


__all__ = [
    "CaptureBackend",
    "FakeCapture",
    "make_capture",
    "list_capture_devices",
    "list_output_devices",
    "default_capture_device",
    "would_feedback",
]
