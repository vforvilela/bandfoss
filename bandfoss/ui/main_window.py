"""BandFOSS main window (PySide6) — LIVE capture and separation.

Flow: pick the app -> capture from PipeWire -> separate in real time ->
mixer with fader + mute/solo per stem.
"""

from __future__ import annotations

import platform
import re
from collections.abc import Callable

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFrame,
    QGraphicsOpacityEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from ..config import (
    LIVE_MODELS,
    LIVE_WINDOW_SEC,
    LIVE_WINDOWS,
    SAMPLE_RATE,
    STEM_COLORS,
    order_stems,
)
from ..i18n import t
from . import theme


class LiveModelWorker(QThread):
    """Loads the (slow) live Demucs model off the UI thread."""

    ready = Signal(object)   # Separator
    failed = Signal(str)

    def __init__(self, model_name: str):
        super().__init__()
        self.model_name = model_name

    def run(self) -> None:  # noqa: D401
        try:
            from ..engine.separator import Separator
            self.ready.emit(Separator(self.model_name))
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))


class AppComboBox(QComboBox):
    """App combo box that refreshes itself every time it is opened."""

    def __init__(self, populate: Callable[[], None]):
        super().__init__()
        self._populate = populate

    def showPopup(self):  # noqa: N802
        self._populate()
        super().showPopup()


class StemStrip(QWidget):
    """Control column for one stem: vertical fader + mute + solo + name."""

    def __init__(
        self,
        name: str,
        on_gain: Callable[[str, float], None],
        on_mute: Callable[[str, bool], None],
        on_solo: Callable[[str, bool], None],
        color: str = theme.AMBER,
    ):
        super().__init__()
        self._name = name
        self._on_gain = on_gain
        self._on_mute = on_mute
        self._on_solo = on_solo

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignHCenter)

        dot = QLabel("●")
        dot.setAlignment(Qt.AlignHCenter)
        dot.setStyleSheet(f"color: {color}; font-size: 14px;")

        self.fader = QSlider(Qt.Vertical)
        self.fader.setRange(0, 150)          # 0–150% gain
        self.fader.setValue(100)
        self.fader.setMinimumHeight(160)
        self.fader.setStyleSheet(theme.fader_style(color))
        self.fader.valueChanged.connect(lambda v: self._on_gain(name, v / 100.0))

        self.value_label = QLabel("100%")
        self.value_label.setAlignment(Qt.AlignHCenter)
        self.value_label.setStyleSheet(f"color: {theme.MUTED};")
        self.fader.valueChanged.connect(lambda v: self.value_label.setText(f"{v}%"))

        self.mute_btn = QPushButton("M")
        self.mute_btn.setObjectName("muteBtn")
        self.mute_btn.setCheckable(True)
        self.mute_btn.setFixedWidth(38)
        self.mute_btn.toggled.connect(lambda on: self._on_mute(name, on))

        self.solo_btn = QPushButton("S")
        self.solo_btn.setObjectName("soloBtn")
        self.solo_btn.setCheckable(True)
        self.solo_btn.setFixedWidth(38)
        self.solo_btn.toggled.connect(lambda on: self._on_solo(name, on))

        btn_row = QHBoxLayout()
        btn_row.addWidget(self.mute_btn)
        btn_row.addWidget(self.solo_btn)

        title = QLabel(t(f"stem_{name}").upper())
        title.setAlignment(Qt.AlignHCenter)
        title.setStyleSheet(f"color: {color}; font-weight: 800; letter-spacing: 1px;")

        layout.addWidget(dot)
        layout.addWidget(self.fader, alignment=Qt.AlignHCenter)
        layout.addWidget(self.value_label)
        layout.addLayout(btn_row)
        layout.addWidget(title)

        # dim the whole column when the channel is not audible
        self._opacity = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._opacity)
        self._opacity.setOpacity(1.0)

    def set_active(self, active: bool) -> None:
        """Lit (audible) = opaque; off (muted or silenced by solo) = dimmed."""
        self._opacity.setOpacity(1.0 if active else 0.28)


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(t("window_title"))
        self.resize(720, 520)
        self.setStyleSheet(theme.STYLESHEET)

        self.engine = None                 # LiveEngine while live
        self.capture = None                # capture backend while live
        self.router = None                 # PipeWireRouter while isolating (Linux)
        self.live_worker: LiveModelWorker | None = None
        self._target = None                # active object for gains (the engine)
        self.strips: dict[str, StemStrip] = {}
        self._system = platform.system()   # "Linux" | "Windows" | "Darwin" | …

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 14, 18, 14)
        root.setSpacing(10)

        # --- header (focal point): BAND·FOSS wordmark ---
        header = QHBoxLayout()
        wordmark = QLabel(
            f"<span style='color:{theme.TEXT}'>BAND</span>"
            f"<span style='color:{theme.AMBER}'>FOSS</span>"
        )
        wordmark.setObjectName("wordmark")
        wf = QFont()
        wf.setPointSize(24)
        wf.setWeight(QFont.Black)
        wf.setLetterSpacing(QFont.PercentageSpacing, 118)
        wordmark.setFont(wf)
        subtitle = QLabel(t("subtitle"))
        subtitle.setObjectName("subtitle")
        sf = QFont()
        sf.setPointSize(9)
        sf.setWeight(QFont.DemiBold)
        sf.setLetterSpacing(QFont.PercentageSpacing, 130)
        subtitle.setFont(sf)
        header.addWidget(wordmark)
        header.addSpacing(10)
        header.addWidget(subtitle, 0, Qt.AlignVCenter)
        header.addStretch(1)
        root.addLayout(header)

        # --- live: source -> Capture ---
        live_row = QHBoxLayout()
        self.source_label = QLabel(t("app_label"))
        live_row.addWidget(self.source_label)
        # Linux: per-app selector. Windows: loopback-device selector (shown by
        # _apply_platform). Both live in this row; only one is visible.
        self.app_box = AppComboBox(self._populate_apps)
        self.app_box.setMinimumWidth(240)
        self.app_box.setEditable(True)          # lets you type an app not yet playing
        self.app_box.setInsertPolicy(QComboBox.NoInsert)
        self.app_box.lineEdit().setPlaceholderText(t("app_placeholder"))
        self._populate_apps()
        self.capture_box = QComboBox()          # Windows capture device
        self.capture_box.setMinimumWidth(240)
        self.capture_box.setVisible(False)
        self.live_btn = QPushButton(t("capture_start"))
        self.live_btn.setObjectName("recordBtn")
        self.live_btn.setCheckable(True)
        self.live_btn.toggled.connect(self._toggle_live)
        self.live_status = QLabel("")
        live_row.addWidget(self.app_box, 1)
        live_row.addWidget(self.capture_box, 1)
        live_row.addWidget(self.live_btn)
        live_row.addWidget(self.live_status)
        root.addLayout(live_row)

        # --- Advanced (collapsed): model, latency, monitor mode ---
        self.adv_btn = QPushButton("▸ " + t("advanced"))
        self.adv_btn.setObjectName("advBtn")
        self.adv_btn.setCheckable(True)
        self.adv_btn.toggled.connect(self._toggle_advanced)
        root.addWidget(self.adv_btn)
        root.addWidget(self._build_advanced_panel())

        # --- stem faders ---
        self.strip_row = QHBoxLayout()
        self.strip_row.setContentsMargins(14, 14, 14, 14)
        self.strip_row.setSpacing(16)
        strip_frame = QFrame()
        strip_frame.setObjectName("stemPanel")
        strip_frame.setLayout(self.strip_row)
        strip_frame.setMinimumHeight(280)
        root.addWidget(strip_frame, 1)

        # --- footer: credit + link ---
        footer = QLabel(
            f"<span style='color:{theme.MUTED}'>{t('footer_prefix')}</span>"
            f"<a href='https://github.com/vforvilela' "
            f"style='color:{theme.AMBER}; text-decoration:none'>vforvilela</a>"
        )
        footer.setObjectName("footer")
        footer.setOpenExternalLinks(True)
        footer.setAlignment(Qt.AlignRight)
        footer.setStyleSheet("font-size: 11px;")
        root.addWidget(footer)

        self._apply_platform()

    # ---- advanced panel ---------------------------------------------------
    def _build_advanced_panel(self) -> QWidget:
        self.adv_panel = QWidget()
        self.adv_panel.setObjectName("advPanel")
        grid = QGridLayout(self.adv_panel)
        grid.setContentsMargins(16, 2, 8, 6)

        self.live_model_box = QComboBox()
        for mid in LIVE_MODELS:
            self.live_model_box.addItem(t(f"model_{mid}"), userData=mid)
        self.live_model_box.setToolTip(t("model_tip"))
        grid.addWidget(QLabel(t("model_label")), 0, 0)
        grid.addWidget(self.live_model_box, 0, 1)

        self.latency_box = QComboBox()
        for i, (wid, sec) in enumerate(LIVE_WINDOWS.items()):
            self.latency_box.addItem(t(f"latency_{wid}"), userData=sec)
            if sec == LIVE_WINDOW_SEC:
                self.latency_box.setCurrentIndex(i)
        self.latency_box.setToolTip(t("latency_tip"))
        grid.addWidget(QLabel(t("latency_label")), 1, 0)
        grid.addWidget(self.latency_box, 1, 1)

        # ---- Linux-only: per-app isolation + monitor fallback ----
        self.isolate_chk = QCheckBox(t("isolate"))
        self.isolate_chk.setChecked(True)
        self.isolate_chk.setToolTip(t("isolate_tip"))
        self.isolate_chk.toggled.connect(self._on_isolate_toggled)
        grid.addWidget(self.isolate_chk, 2, 0, 1, 2)

        self.monitor_label = QLabel(t("monitor_label"))
        self.monitor_box = QComboBox()
        self._populate_monitors()
        grid.addWidget(self.monitor_label, 3, 0)
        grid.addWidget(self.monitor_box, 3, 1)

        # ---- Windows-only: output-device selector + hint ----
        self.output_label = QLabel(t("output_label"))
        self.output_box = QComboBox()
        grid.addWidget(self.output_label, 4, 0)
        grid.addWidget(self.output_box, 4, 1)
        self.win_hint = QLabel(t("win_hint"))
        self.win_hint.setWordWrap(True)
        self.win_hint.setStyleSheet(f"color: {theme.MUTED}; font-size: 11px;")
        grid.addWidget(self.win_hint, 5, 0, 1, 2)

        grid.setColumnStretch(1, 1)
        self.adv_panel.setVisible(False)
        self._on_isolate_toggled(True)
        return self.adv_panel

    def _toggle_advanced(self, on: bool) -> None:
        self.adv_panel.setVisible(on)
        self.adv_btn.setText(("▾ " if on else "▸ ") + t("advanced"))

    # ---- capture sources --------------------------------------------------
    def _populate_monitors(self) -> None:
        self.monitor_box.clear()
        try:
            from ..capture.live_source import default_monitor, list_monitors
            default = default_monitor()
            monitors = list_monitors()
            ordered = [default] + [m for m in monitors if m != default]
            for m in ordered:
                self.monitor_box.addItem(m)
        except Exception:  # noqa: BLE001 — no PipeWire/pactl
            self.monitor_box.addItem("(default monitor)")

    def _populate_apps(self) -> None:
        """List apps playing now; preserve what the user typed."""
        typed = self.app_box.currentText().strip() if self.app_box.isEditable() else ""
        self.app_box.clear()
        try:
            from ..capture.router import list_playback_apps
            apps = list_playback_apps()
        except Exception:  # noqa: BLE001
            apps = []
        browser_idx = 0
        for i, a in enumerate(apps):
            self.app_box.addItem(f"{a['label']} (#{a['id']})", userData=a["label"])
            if any(b in a["label"].lower() for b in ("chrom", "firefox", "brave", "edge")):
                browser_idx = i
        if typed:
            self.app_box.setCurrentText(typed)
        elif apps:
            self.app_box.setCurrentIndex(browser_idx)
        else:
            self.app_box.setCurrentText("")

    def _on_isolate_toggled(self, on: bool) -> None:
        # isolated -> use the App (main row); no isolation -> use the Monitor
        self.app_box.setEnabled(on)
        self.monitor_box.setEnabled(not on)

    # ---- platform wiring --------------------------------------------------
    def _apply_platform(self) -> None:
        """Show/hide controls and enable capture based on the OS."""
        win_only = (self.capture_box, self.output_label, self.output_box, self.win_hint)
        linux_only = (self.app_box, self.isolate_chk, self.monitor_label, self.monitor_box)
        if self._system == "Linux":
            for w in win_only:
                w.setVisible(False)
            self.source_label.setText(t("app_label"))
        elif self._system == "Windows":
            for w in linux_only:
                w.setVisible(False)
            for w in win_only:
                w.setVisible(True)
            self.source_label.setText(t("capture_label"))
            self._populate_windows_devices()
        else:  # macOS / others: no capture backend yet
            for w in win_only:
                w.setVisible(False)
            self.app_box.setEnabled(False)
            self.live_btn.setEnabled(False)
            self.live_btn.setToolTip(t("unsupported_os_tip"))
            self.live_status.setText(t("unsupported_os"))

    def _populate_windows_devices(self) -> None:
        from ..capture import default_capture_device, list_capture_devices
        devices = list_capture_devices("Windows")
        default = default_capture_device("Windows")
        self.capture_box.clear()
        self.output_box.clear()
        self.output_box.addItem(t("output_default"), userData=None)
        for d in devices:
            self.capture_box.addItem(d)
            self.output_box.addItem(d, userData=d)
        if default and default in devices:
            self.capture_box.setCurrentText(default)

    def _build_capture(self):
        """Create the capture backend + output config for the current OS.

        Returns (capture, output_sink, output_device, status_src). Raises with a
        localized message on misconfiguration (e.g. a feedback loop).
        """
        if self._system == "Windows":
            from ..capture import default_capture_device, make_capture, would_feedback
            cap_dev = self.capture_box.currentText() or None
            out_dev = self.output_box.currentData()          # None = system default
            effective_out = out_dev or default_capture_device("Windows")
            if would_feedback(cap_dev, effective_out):
                raise RuntimeError(t("err_feedback"))
            capture = make_capture(device=cap_dev, system="Windows", samplerate=SAMPLE_RATE)
            return capture, None, out_dev, t("src_system")

        # Linux (PipeWire): per-app isolation or plain monitor.
        from ..capture.live_source import LiveCapture
        from ..capture.router import PipeWireRouter
        if self.isolate_chk.isChecked():
            app_match = self.app_box.currentData()
            if not app_match:
                app_match = re.sub(r"\s*\(#\d+\)\s*$", "",
                                   self.app_box.currentText()).strip()
            if not app_match:
                raise RuntimeError(t("err_no_app"))
            self.router = PipeWireRouter()
            device, output_sink = self.router.setup(app_match)
            src = t("src_only", app=self.app_box.currentData() or self.app_box.currentText())
            return LiveCapture(device=device), output_sink, None, src

        device = self.monitor_box.currentText()
        if device.startswith("("):
            device = None
        return LiveCapture(device=device), None, None, t("src_monitor")

    # ---- live capture -----------------------------------------------------
    def _toggle_live(self, on: bool) -> None:
        if on:
            self._start_live()
        else:
            self._stop_live()

    def _start_live(self) -> None:
        self.live_btn.setText(t("loading"))
        self.live_btn.setEnabled(False)
        self.live_model_box.setEnabled(False)
        self.latency_box.setEnabled(False)
        self.live_status.setText(t("loading_model"))

        model_name = LIVE_MODELS[self.live_model_box.currentData()]
        self.live_worker = LiveModelWorker(model_name)
        self.live_worker.ready.connect(self._on_live_ready)
        self.live_worker.failed.connect(self._on_live_failed)
        self.live_worker.start()

    def _on_live_failed(self, msg: str) -> None:
        self.live_status.setText("")
        self.live_btn.setEnabled(True)
        self.live_btn.setText(t("capture_start"))
        self.live_btn.setChecked(False)
        self.live_model_box.setEnabled(True)
        self.latency_box.setEnabled(True)
        QMessageBox.critical(self, t("err_capture_title"), msg)

    def _on_live_ready(self, separator) -> None:  # noqa: ANN001
        from ..engine.live_engine import LiveEngine

        try:
            capture, output_sink, output_device, src = self._build_capture()
            self.capture = capture
            window_sec = self.latency_box.currentData()
            window_frames = int(window_sec * SAMPLE_RATE)
            self.engine = LiveEngine(
                separator, self.capture, window_frames=window_frames,
                samplerate=SAMPLE_RATE, output_sink=output_sink,
                output_device=output_device,
            )
            self._target = self.engine

            # build the faders (vocals first, "other" last)
            self._clear_strips()
            for name in order_stems(self.engine.names):
                strip = StemStrip(name, self._set_gain, self._set_mute, self._set_solo,
                                  color=STEM_COLORS.get(name, theme.AMBER))
                self.strips[name] = strip
                self.strip_row.addWidget(strip)
            self._update_strip_states()

            self.capture.start()
            self.engine.start()
        except Exception as exc:  # noqa: BLE001
            if self.router:
                self.router.teardown()
                self.router = None
            self._on_live_failed(str(exc))
            return

        self.live_btn.setEnabled(True)
        self.live_btn.setText(t("capture_stop"))
        self.live_status.setText(t("status_live", src=src, sec=self.engine.latency_seconds))

    def _stop_live(self) -> None:
        if self.engine:
            self.engine.stop()
        if self.capture:
            self.capture.stop()
        if self.router:
            self.router.teardown()          # restore the default sink, remove the virtual one
        self.engine = None
        self.capture = None
        self.router = None
        self._target = None
        self._clear_strips()
        self.live_btn.setText(t("capture_start"))
        self.live_btn.setChecked(False)
        self.live_model_box.setEnabled(True)
        self.latency_box.setEnabled(True)
        self.live_status.setText("")

    def _clear_strips(self) -> None:
        for strip in self.strips.values():
            strip.setParent(None)
        self.strips.clear()

    # ---- stem callbacks (routed to the active engine) ---------------------
    def _set_gain(self, name: str, gain: float) -> None:
        if self._target:
            self._target.set_gain(name, gain)

    def _set_mute(self, name: str, muted: bool) -> None:
        if self._target:
            self._target.set_muted(name, muted)
        self._update_strip_states()

    def _set_solo(self, name: str, on: bool) -> None:
        if not self._target:
            return
        if on:
            for other, strip in self.strips.items():
                if other != name and strip.solo_btn.isChecked():
                    strip.solo_btn.setChecked(False)
            self._target.set_solo(name)
        else:
            self._target.set_solo(None)
        self._update_strip_states()

    def _update_strip_states(self) -> None:
        """Dim the columns that are not audible (muted, or silenced by solo)."""
        soloed = next((n for n, s in self.strips.items() if s.solo_btn.isChecked()), None)
        for name, strip in self.strips.items():
            if soloed is not None:
                audible = name == soloed
            else:
                audible = not strip.mute_btn.isChecked()
            strip.set_active(audible)

    def closeEvent(self, event):  # noqa: ANN001, N802
        if self.engine:
            self.engine.stop()
        if self.capture:
            self.capture.stop()
        if self.router:
            self.router.teardown()
        super().closeEvent(event)


def run() -> int:
    app = QApplication.instance() or QApplication([])
    app.setStyle("Fusion")   # consistent base that draws the themed controls well
    window = MainWindow()
    window.show()
    return app.exec()
