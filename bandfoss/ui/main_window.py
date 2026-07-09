"""Janela principal do BandFOSS (PySide6) — captura e separação AO VIVO.

Fluxo: escolher o app -> capturar do PipeWire -> separar em tempo real ->
mixer com fader + mute/solo por stem.
"""

from __future__ import annotations

import platform
import re
from typing import Dict, Optional

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
    """Carrega o modelo Demucs ao vivo (lento) fora da thread da UI."""

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
    """Combo de apps que se reatualiza sozinho toda vez que é aberto."""

    def __init__(self, populate):
        super().__init__()
        self._populate = populate

    def showPopup(self):  # noqa: N802
        self._populate()
        super().showPopup()


class StemStrip(QWidget):
    """Coluna de controle de um stem: fader vertical + mute + solo + nome."""

    def __init__(self, name: str, on_gain, on_mute, on_solo, color: str = theme.AMBER):
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
        self.fader.setRange(0, 150)          # 0–150% de ganho
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

        # esmaece a coluna inteira quando o canal não está audível
        self._opacity = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._opacity)
        self._opacity.setOpacity(1.0)

    def set_active(self, active: bool) -> None:
        """Aceso (audível) = opaco; apagado (mudo ou silenciado por solo) = esmaecido."""
        self._opacity.setOpacity(1.0 if active else 0.28)


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(t("window_title"))
        self.resize(720, 520)
        self.setStyleSheet(theme.STYLESHEET)

        self.engine = None                 # LiveEngine quando ao vivo
        self.capture = None                # LiveCapture quando ao vivo
        self.router = None                 # PipeWireRouter quando isolando
        self.live_worker: Optional[LiveModelWorker] = None
        self._target = None                # objeto ativo p/ ganhos (o engine)
        self.strips: Dict[str, StemStrip] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 14, 18, 14)
        root.setSpacing(10)

        # --- cabeçalho (ponto focal): wordmark BAND·FOSS ---
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

        # --- ao vivo: App -> Capturar ---
        live_row = QHBoxLayout()
        live_row.addWidget(QLabel(t("app_label")))
        self.app_box = AppComboBox(self._populate_apps)
        self.app_box.setMinimumWidth(240)
        self.app_box.setEditable(True)          # dá para digitar um app que ainda não toca
        self.app_box.setInsertPolicy(QComboBox.NoInsert)
        self.app_box.lineEdit().setPlaceholderText(t("app_placeholder"))
        self._populate_apps()
        self.live_btn = QPushButton(t("capture_start"))
        self.live_btn.setObjectName("recordBtn")
        self.live_btn.setCheckable(True)
        self.live_btn.toggled.connect(self._toggle_live)
        self.live_status = QLabel("")
        live_row.addWidget(self.app_box, 1)
        live_row.addWidget(self.live_btn)
        live_row.addWidget(self.live_status)
        root.addLayout(live_row)

        # --- Avançado (recolhido): modelo, latência, modo monitor ---
        self.adv_btn = QPushButton("▸ " + t("advanced"))
        self.adv_btn.setObjectName("advBtn")
        self.adv_btn.setCheckable(True)
        self.adv_btn.toggled.connect(self._toggle_advanced)
        root.addWidget(self.adv_btn)
        root.addWidget(self._build_advanced_panel())

        # --- faders dos stems ---
        self.strip_row = QHBoxLayout()
        self.strip_row.setContentsMargins(14, 14, 14, 14)
        self.strip_row.setSpacing(16)
        strip_frame = QFrame()
        strip_frame.setObjectName("stemPanel")
        strip_frame.setLayout(self.strip_row)
        strip_frame.setMinimumHeight(280)
        root.addWidget(strip_frame, 1)

        # --- footer: crédito + link ---
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

        # captura ao vivo depende do PipeWire (Linux).
        if platform.system() != "Linux":
            self.app_box.setEnabled(False)
            self.live_btn.setEnabled(False)
            self.live_btn.setToolTip(t("linux_only_tip"))
            self.live_status.setText(t("requires_linux"))

    # ---- painel avançado --------------------------------------------------
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

        self.isolate_chk = QCheckBox(t("isolate"))
        self.isolate_chk.setChecked(True)
        self.isolate_chk.setToolTip(t("isolate_tip"))
        self.isolate_chk.toggled.connect(self._on_isolate_toggled)
        grid.addWidget(self.isolate_chk, 2, 0, 1, 2)

        self.monitor_box = QComboBox()
        self._populate_monitors()
        grid.addWidget(QLabel(t("monitor_label")), 3, 0)
        grid.addWidget(self.monitor_box, 3, 1)

        grid.setColumnStretch(1, 1)
        self.adv_panel.setVisible(False)
        self._on_isolate_toggled(True)
        return self.adv_panel

    def _toggle_advanced(self, on: bool) -> None:
        self.adv_panel.setVisible(on)
        self.adv_btn.setText(("▾ " if on else "▸ ") + t("advanced"))

    # ---- fontes de captura ------------------------------------------------
    def _populate_monitors(self) -> None:
        self.monitor_box.clear()
        try:
            from ..capture.live_source import default_monitor, list_monitors
            default = default_monitor()
            monitors = list_monitors()
            ordered = [default] + [m for m in monitors if m != default]
            for m in ordered:
                self.monitor_box.addItem(m)
        except Exception:  # noqa: BLE001 — sem PipeWire/pactl
            self.monitor_box.addItem("(monitor padrão)")

    def _populate_apps(self) -> None:
        """Lista os apps tocando agora; preserva o que o usuário digitou."""
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
        # isolado -> usa o App (linha principal); sem isolar -> usa o Monitor
        self.app_box.setEnabled(on)
        self.monitor_box.setEnabled(not on)

    # ---- captura ao vivo --------------------------------------------------
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
        from ..capture.live_source import LiveCapture
        from ..capture.router import PipeWireRouter
        from ..engine.live_engine import LiveEngine

        try:
            output_sink = None
            if self.isolate_chk.isChecked():
                app_match = self.app_box.currentData()
                if not app_match:
                    app_match = re.sub(r"\s*\(#\d+\)\s*$", "",
                                       self.app_box.currentText()).strip()
                if not app_match:
                    raise RuntimeError(t("err_no_app"))
                self.router = PipeWireRouter()
                device, output_sink = self.router.setup(app_match)
            else:
                device = self.monitor_box.currentText()
                if device.startswith("("):
                    device = None

            self.capture = LiveCapture(device=device)
            window_sec = self.latency_box.currentData()
            window_frames = int(window_sec * SAMPLE_RATE)
            self.engine = LiveEngine(
                separator, self.capture, window_frames=window_frames,
                samplerate=SAMPLE_RATE, output_sink=output_sink,
            )
            self._target = self.engine

            # monta os faders (voz primeiro, "outros" por último)
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
        if self.isolate_chk.isChecked():
            app = self.app_box.currentData() or self.app_box.currentText()
            src = t("src_only", app=app)
        else:
            src = t("src_monitor")
        self.live_status.setText(t("status_live", src=src, sec=self.engine.latency_seconds))

    def _stop_live(self) -> None:
        if self.engine:
            self.engine.stop()
        if self.capture:
            self.capture.stop()
        if self.router:
            self.router.teardown()          # restaura o sink padrão e remove o virtual
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

    # ---- callbacks de stem (roteados para o engine ativo) -----------------
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
        """Esmaece as colunas que não estão audíveis (mute, ou silenciadas por solo)."""
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
    app.setStyle("Fusion")   # base consistente que desenha bem os controles do tema
    window = MainWindow()
    window.show()
    return app.exec()
