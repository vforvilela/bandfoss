"""Selective PipeWire routing for per-application live capture.

Creates a *virtual sink* (null sink) and moves **only the chosen app** to it
(e.g. Chrome). BandFOSS captures that sink's monitor and plays the processed
result back on the real speaker. Everything else — including a live guitar —
keeps playing normally through the speakers, uncaptured and unprocessed.

  Chrome ─► [virtual sink] ─► monitor ─► BandFOSS ─► pacat ─► [real sink] ─► 🔊
  Guitar ──────────────────────────────────────────────────► [real sink] ─► 🔊
"""

from __future__ import annotations

import re
import subprocess
import threading

from ..util import require_tool


def _run(args: list[str]) -> str:
    return subprocess.check_output(args, text=True).strip()


def list_playback_apps() -> list[dict[str, str]]:
    """List streams playing right now: {id, app, binary, media, label}."""
    pactl = require_tool("pactl")
    out = subprocess.check_output([pactl, "list", "sink-inputs"], text=True)
    apps: list[dict[str, str]] = []
    cur: dict[str, str] | None = None
    for line in out.splitlines():
        if line.startswith("Sink Input #"):
            if cur:
                apps.append(cur)
            cur = {"id": line.split("#", 1)[1].strip(), "app": "", "binary": "", "media": ""}
        elif cur is not None:
            s = line.strip()
            for key, prop in (("app", "application.name"),
                              ("binary", "application.process.binary"),
                              ("media", "media.name")):
                if s.startswith(prop + " = "):
                    cur[key] = s.split("=", 1)[1].strip().strip('"')
    if cur:
        apps.append(cur)
    for a in apps:
        a["label"] = a["app"] or a["binary"] or a["media"] or f"stream {a['id']}"
    return apps


class PipeWireRouter:
    """Move the chosen app to a virtual sink; put everything back on teardown."""

    def __init__(self, sink_name: str = "bandfoss_capture"):
        self.sink_name = sink_name
        self._pactl = require_tool("pactl")
        self.module_id: str | None = None
        self.real_sink: str | None = None
        self._needle: str = ""
        self._watch_proc: subprocess.Popen | None = None
        self._watch_thread: threading.Thread | None = None

    def _modules_for_our_sink(self) -> list[str]:
        """IDs of null-sink modules already created with our sink_name (leftovers)."""
        out = subprocess.check_output([self._pactl, "list", "modules"], text=True)
        ids: list[str] = []
        cur = name = arg = None
        for line in out.splitlines():
            m = re.match(r"Module #(\d+)", line)
            if m:
                if cur and name == "module-null-sink" and arg and \
                        f"sink_name={self.sink_name}" in arg:
                    ids.append(cur)
                cur, name, arg = m.group(1), None, None
            elif line.strip().startswith("Name:"):
                name = line.split(":", 1)[1].strip()
            elif line.strip().startswith("Argument:"):
                arg = line.split(":", 1)[1].strip()
        if cur and name == "module-null-sink" and arg and \
                f"sink_name={self.sink_name}" in arg:
            ids.append(cur)
        return ids

    def _cleanup_existing(self) -> None:
        for mid in self._modules_for_our_sink():
            subprocess.run([self._pactl, "unload-module", mid], check=False)

    def _pick_real_sink(self) -> str:
        """Real (hardware) output sink, ignoring the virtual sink and monitors."""
        default = _run([self._pactl, "get-default-sink"])
        if default and default != self.sink_name and not default.endswith(".monitor"):
            return default
        out = subprocess.check_output([self._pactl, "list", "sinks", "short"], text=True)
        for line in out.splitlines():
            parts = line.split("\t")
            if len(parts) >= 2 and parts[1].startswith("alsa_output."):
                return parts[1]
        raise RuntimeError("No hardware output sink found.")

    def _virtual_sink_index(self) -> str | None:
        out = subprocess.check_output([self._pactl, "list", "sinks", "short"], text=True)
        for line in out.splitlines():
            parts = line.split("\t")
            if len(parts) >= 2 and parts[1] == self.sink_name:
                return parts[0]
        return None

    def _inputs_on_virtual(self) -> list[str]:
        idx = self._virtual_sink_index()
        if idx is None:
            return []
        out = subprocess.check_output(
            [self._pactl, "list", "sink-inputs", "short"], text=True
        )
        return [
            line.split("\t")[0]
            for line in out.splitlines()
            if "\t" in line and line.split("\t")[1] == str(idx)
        ]

    def _input_sink_map(self) -> dict[str, str]:
        """{stream_id: sink_index} for every sink-input."""
        out = subprocess.check_output(
            [self._pactl, "list", "sink-inputs", "short"], text=True
        )
        m = {}
        for line in out.splitlines():
            parts = line.split("\t")
            if len(parts) >= 2:
                m[parts[0]] = parts[1]
        return m

    def _move_matching(self) -> int:
        """Move the app's streams that are not yet on the virtual sink."""
        vidx = self._virtual_sink_index()
        if vidx is None:
            return 0
        sinks = self._input_sink_map()
        moved = 0
        for a in list_playback_apps():
            hay = f"{a['app']} {a['binary']} {a['media']}".lower()
            if self._needle in hay and sinks.get(a["id"]) != vidx:
                r = subprocess.run(
                    [self._pactl, "move-sink-input", a["id"], self.sink_name],
                    check=False,
                )
                if r.returncode == 0:
                    moved += 1
        return moved

    def setup(self, app_match: str) -> tuple[str, str]:
        """Create the virtual sink and start capturing ONLY app `app_match`.

        Moves what is already playing AND watches for new streams of the app
        (via `pactl subscribe`), so you can start capturing BEFORE hitting play —
        when the app starts, its stream is moved automatically.
        `app_match`: case-insensitive substring of the app name/binary.
        Returns (monitor_to_capture, real_sink_for_output). Does NOT touch the
        default sink — a guitar and other apps stay intact.
        """
        self._needle = app_match.lower()
        self._cleanup_existing()                 # remove leftover bandfoss sinks
        self.real_sink = self._pick_real_sink()  # real speaker (not the virtual)
        self.module_id = _run([
            self._pactl, "load-module", "module-null-sink",
            f"sink_name={self.sink_name}",
            "sink_properties=device.description=BandFOSS_Capture",
        ])
        self._move_matching()                    # move what is already playing (if any)
        self._start_watcher()                    # watch for new streams of the app
        return f"{self.sink_name}.monitor", self.real_sink

    def _start_watcher(self) -> None:
        self._watch_proc = subprocess.Popen(
            [self._pactl, "subscribe"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
        )
        self._watch_thread = threading.Thread(target=self._watch_loop, daemon=True)
        self._watch_thread.start()

    def _watch_loop(self) -> None:
        """On each new/changed sink-input event, try to move the chosen app."""
        try:
            for line in self._watch_proc.stdout:
                if "sink-input" in line and ("'new'" in line or "'change'" in line):
                    try:
                        self._move_matching()
                    except Exception:  # noqa: BLE001 — capture may be shutting down
                        pass
        except Exception:  # noqa: BLE001
            pass

    def teardown(self) -> None:
        """Stop the watcher, return streams to the real sink, remove the virtual sink."""
        if self._watch_proc is not None:
            self._watch_proc.terminate()
            self._watch_proc = None
        if self.real_sink:
            for sid in self._inputs_on_virtual():
                subprocess.run(
                    [self._pactl, "move-sink-input", sid, self.real_sink], check=False
                )
        if self.module_id:
            subprocess.run([self._pactl, "unload-module", self.module_id], check=False)
            self.module_id = None
