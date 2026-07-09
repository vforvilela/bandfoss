"""Janela principal do BandFOSS (PySide6).

Fluxo: carregar fonte (arquivo/URL) -> separar em QThread -> montar mixer com
um fader + mute/solo por stem, transporte e presets.
"""

from __future__ import annotations

from typing import Dict, Optional

import numpy as np
from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from ..config import (
    DEFAULT_MODEL,
    LIVE_MODELS,
    LIVE_WINDOW_OPTIONS,
    LIVE_WINDOW_SEC,
    PRESETS,
    SAMPLE_RATE,
    STEM_COLORS,
    STEM_LABELS,
    order_stems,
)
from ..engine.mixer import StemMixer
from . import theme


class SeparationWorker(QThread):
    """Roda captura + separação fora da thread da UI."""

    progress = Signal(float)
    status = Signal(str)
    finished_ok = Signal(dict, int)   # {stem: array}, samplerate
    failed = Signal(str)

    def __init__(self, source: str, model_name: str):
        super().__init__()
        self.source = source
        self.model_name = model_name

    def run(self) -> None:  # noqa: D401
        try:
            from ..capture.file_source import load_source
            from ..engine.separator import Separator

            self.status.emit("Preparando…")
            pcm = load_source(self.source, status=self.status.emit)
            self.status.emit("Carregando modelo…")
            separator = Separator(self.model_name)
            self.status.emit("Separando stems…")
            stems = separator.separate(pcm, progress=self.progress.emit)
            self.finished_ok.emit(stems, separator.samplerate)
        except Exception as exc:  # noqa: BLE001 — reportamos à UI
            self.failed.emit(str(exc))


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

        # ponto colorido do canal (topo)
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

        title = QLabel(STEM_LABELS.get(name, name.capitalize()).upper())
        title.setAlignment(Qt.AlignHCenter)
        title.setStyleSheet(f"color: {color}; font-weight: 800; letter-spacing: 1px;")

        layout.addWidget(dot)
        layout.addWidget(self.fader, alignment=Qt.AlignHCenter)
        layout.addWidget(self.value_label)
        layout.addLayout(btn_row)
        layout.addWidget(title)


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("BandFOSS — Separador de Stems")
        self.resize(720, 560)
        self.setStyleSheet(theme.STYLESHEET)

        self.mixer: Optional[StemMixer] = None
        self.engine = None                 # LiveEngine quando ao vivo
        self.capture = None                # LiveCapture quando ao vivo
        self.router = None                 # PipeWireRouter quando isolando
        self.live_worker: Optional[LiveModelWorker] = None
        self.worker: Optional[SeparationWorker] = None
        self._target = None                # objeto ativo p/ ganhos (mixer ou engine)
        self.strips: Dict[str, StemStrip] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 14, 18, 14)
        root.setSpacing(10)

        # --- cabeçalho (ponto focal): wordmark BAND·BOX ---
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
        subtitle = QLabel("STEM MIXER")
        subtitle.setObjectName("subtitle")
        sf = QFont()
        sf.setPointSize(9)
        sf.setWeight(QFont.DemiBold)
        sf.setLetterSpacing(QFont.PercentageSpacing, 260)
        subtitle.setFont(sf)
        header.addWidget(wordmark)
        header.addSpacing(10)
        header.addWidget(subtitle, 0, Qt.AlignVCenter)
        header.addStretch(1)
        root.addLayout(header)

        # --- fonte: arquivo/URL -> Separar ---
        src_row = QHBoxLayout()
        self.source_input = QLineEdit()
        self.source_input.setPlaceholderText("Arquivo, URL ou nome da música…")
        browse_btn = QPushButton("Abrir…")
        browse_btn.clicked.connect(self._browse)
        self.separate_btn = QPushButton("Separar")
        self.separate_btn.setObjectName("primaryBtn")
        self.separate_btn.clicked.connect(self._start_separation)
        src_row.addWidget(self.source_input, 1)
        src_row.addWidget(browse_btn)
        src_row.addWidget(self.separate_btn)
        root.addLayout(src_row)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setVisible(False)
        root.addWidget(self.progress)

        # --- ao vivo: App -> Capturar ---
        live_row = QHBoxLayout()
        live_row.addWidget(QLabel("App:"))
        self.app_box = AppComboBox(self._populate_apps)
        self.app_box.setMinimumWidth(220)
        self._populate_apps()
        self.live_btn = QPushButton("● Capturar ao vivo")
        self.live_btn.setObjectName("recordBtn")
        self.live_btn.setCheckable(True)
        self.live_btn.toggled.connect(self._toggle_live)
        self.live_status = QLabel("")
        live_row.addWidget(self.app_box, 1)
        live_row.addWidget(self.live_btn)
        live_row.addWidget(self.live_status)
        root.addLayout(live_row)

        # --- Avançado (recolhido): modelos, latência, modo monitor ---
        self.adv_btn = QPushButton("▸ AVANÇADO")
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

        # --- presets ---
        preset_row = QHBoxLayout()
        preset_row.addWidget(QLabel("Preset:"))
        self.preset_box = QComboBox()
        self.preset_box.addItems(PRESETS.keys())
        self.preset_box.currentTextChanged.connect(self._apply_preset)
        self.preset_box.setEnabled(False)
        preset_row.addWidget(self.preset_box)
        preset_row.addStretch(1)
        root.addLayout(preset_row)

        # --- transporte (só no modo arquivo; some ao vivo) ---
        self.transport_widget = QWidget()
        transport = QHBoxLayout(self.transport_widget)
        transport.setContentsMargins(0, 0, 0, 0)
        self.play_btn = QPushButton("▶ Play")
        self.play_btn.clicked.connect(self._toggle_play)
        self.stop_btn = QPushButton("■ Stop")
        self.stop_btn.clicked.connect(self._stop)
        self.seek = QSlider(Qt.Horizontal)
        self.seek.setRange(0, 1000)
        self.seek.sliderMoved.connect(self._on_seek)
        self.time_label = QLabel("00:00 / 00:00")
        transport.addWidget(self.play_btn)
        transport.addWidget(self.stop_btn)
        transport.addWidget(self.seek, 1)
        transport.addWidget(self.time_label)
        self.transport_widget.setVisible(False)   # aparece após separar um arquivo
        root.addWidget(self.transport_widget)

        # timer para atualizar posição/tempo
        self._timer = QTimer(self)
        self._timer.setInterval(200)
        self._timer.timeout.connect(self._tick)

    # ---- painel avançado --------------------------------------------------
    def _build_advanced_panel(self) -> QWidget:
        self.adv_panel = QWidget()
        self.adv_panel.setObjectName("advPanel")
        grid = QGridLayout(self.adv_panel)
        grid.setContentsMargins(16, 2, 8, 6)

        self.model_box = QComboBox()
        self.model_box.addItems([DEFAULT_MODEL, "htdemucs_6s"])
        grid.addWidget(QLabel("Modelo (arquivo):"), 0, 0)
        grid.addWidget(self.model_box, 0, 1)

        self.live_model_box = QComboBox()
        self.live_model_box.addItems(LIVE_MODELS.keys())
        self.live_model_box.setToolTip(
            "Rápido (4 stems): bateria/baixo/vocal/outros.\n"
            "Guitarra (6 stems): adiciona guitarra e piano — permite mutar\n"
            "especificamente a guitarra gravada da faixa (um pouco mais lento)."
        )
        grid.addWidget(QLabel("Modelo (ao vivo):"), 1, 0)
        grid.addWidget(self.live_model_box, 1, 1)

        self.latency_box = QComboBox()
        self.latency_box.addItems(LIVE_WINDOW_OPTIONS.keys())
        self.latency_box.setToolTip(
            "Atraso do áudio ao vivo = tamanho da janela do Demucs (não é o\n"
            "processamento). Menor = mais responsivo; maior = melhor separação."
        )
        for i, (lbl, sec) in enumerate(LIVE_WINDOW_OPTIONS.items()):
            if sec == LIVE_WINDOW_SEC:
                self.latency_box.setCurrentIndex(i)
        grid.addWidget(QLabel("Latência (ao vivo):"), 2, 0)
        grid.addWidget(self.latency_box, 2, 1)

        self.isolate_chk = QCheckBox("Isolar por app (recomendado)")
        self.isolate_chk.setChecked(True)
        self.isolate_chk.setToolTip(
            "Ligado: processa só o App escolhido; guitarra ao vivo e demais apps\n"
            "seguem intactos. Desligado: captura o Monitor abaixo (pode ter eco)."
        )
        self.isolate_chk.toggled.connect(self._on_isolate_toggled)
        grid.addWidget(self.isolate_chk, 3, 0, 1, 2)

        self.monitor_box = QComboBox()
        self._populate_monitors()
        grid.addWidget(QLabel("Monitor (sem isolar):"), 4, 0)
        grid.addWidget(self.monitor_box, 4, 1)

        grid.setColumnStretch(1, 1)
        self.adv_panel.setVisible(False)
        self._on_isolate_toggled(True)   # monitor desabilitado por padrão
        return self.adv_panel

    # ---- fonte ------------------------------------------------------------
    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Escolher áudio", "",
            "Áudio (*.mp3 *.wav *.flac *.m4a *.ogg *.opus);;Todos (*)",
        )
        if path:
            self.source_input.setText(path)

    def _start_separation(self) -> None:
        source = self.source_input.text().strip()
        if not source:
            QMessageBox.warning(self, "BandFOSS", "Informe um arquivo ou URL.")
            return
        if self.engine:                       # sai do modo ao vivo primeiro
            self.live_btn.setChecked(False)
        self.separate_btn.setEnabled(False)
        self.progress.setVisible(True)
        # começa indeterminada (download/modelo não têm % confiável)
        self.progress.setRange(0, 0)
        self.progress.setFormat("Preparando…")

        self.worker = SeparationWorker(source, self.model_box.currentText())
        self.worker.status.connect(self._on_status)
        self.worker.progress.connect(self._on_progress)
        self.worker.finished_ok.connect(self._on_separated)
        self.worker.failed.connect(self._on_failed)
        self.worker.start()

    def _on_status(self, msg: str) -> None:
        # fases sem percentual: mantém a barra em modo "ocupada"
        self.progress.setRange(0, 0)
        self.progress.setFormat(msg)

    def _on_progress(self, p: float) -> None:
        # fase de separação: percentual real
        if self.progress.maximum() == 0:
            self.progress.setRange(0, 100)
        self.progress.setValue(int(p * 100))
        self.progress.setFormat(f"Separando… %p%")

    def _on_failed(self, msg: str) -> None:
        self.progress.setVisible(False)
        self.separate_btn.setEnabled(True)
        QMessageBox.critical(self, "Falha na separação", msg)

    def _on_separated(self, stems: Dict[str, np.ndarray], samplerate: int) -> None:
        self.progress.setVisible(False)
        self.separate_btn.setEnabled(True)

        # Fecha mixer anterior, se houver.
        if self.mixer is not None:
            self.mixer.close()
        self._clear_strips()

        self.mixer = StemMixer(stems, samplerate=samplerate)
        self._target = self.mixer
        for name in order_stems(self.mixer.names):
            strip = StemStrip(name, self._set_gain, self._set_mute, self._set_solo,
                              color=STEM_COLORS.get(name, theme.AMBER))
            self.strips[name] = strip
            self.strip_row.addWidget(strip)

        self.play_btn.setEnabled(True)
        self.stop_btn.setEnabled(True)
        self.transport_widget.setVisible(True)     # transporte só no modo arquivo
        self.preset_box.setEnabled(True)
        self.preset_box.setCurrentText("Original")
        self._timer.start()

    def _clear_strips(self) -> None:
        for strip in self.strips.values():
            strip.setParent(None)
        self.strips.clear()

    # ---- callbacks de stem (roteados para o alvo ativo: mixer ou engine) --
    def _set_gain(self, name: str, gain: float) -> None:
        if self._target:
            self._target.set_gain(name, gain)

    def _set_mute(self, name: str, muted: bool) -> None:
        if self._target:
            self._target.set_muted(name, muted)

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

    def _apply_preset(self, preset: str) -> None:
        if not self._target:
            return
        mute_set = set(PRESETS.get(preset, []))
        for name, strip in self.strips.items():
            should_mute = name in mute_set
            strip.mute_btn.setChecked(should_mute)

    # ---- captura ao vivo --------------------------------------------------
    def _populate_monitors(self) -> None:
        self.monitor_box.clear()
        try:
            from ..capture.live_source import default_monitor, list_monitors
            default = default_monitor()
            monitors = list_monitors()
            # coloca o monitor padrão em primeiro
            ordered = [default] + [m for m in monitors if m != default]
            for m in ordered:
                self.monitor_box.addItem(m)
        except Exception:  # noqa: BLE001 — sem PipeWire/pactl
            self.monitor_box.addItem("(monitor padrão)")

    def _populate_apps(self) -> None:
        """Lista os apps tocando agora; pré-seleciona um navegador se houver."""
        self.app_box.clear()
        try:
            from ..capture.router import list_playback_apps
            apps = list_playback_apps()
        except Exception:  # noqa: BLE001
            apps = []
        if not apps:
            self.app_box.addItem("(nenhum app tocando)", userData=None)
            return
        browser_idx = 0
        for i, a in enumerate(apps):
            self.app_box.addItem(f"{a['label']} (#{a['id']})", userData=a["label"])
            if any(b in a["label"].lower() for b in ("chrom", "firefox", "brave", "edge")):
                browser_idx = i
        self.app_box.setCurrentIndex(browser_idx)

    def _on_isolate_toggled(self, on: bool) -> None:
        # isolado -> usa o App (linha principal); sem isolar -> usa o Monitor
        self.app_box.setEnabled(on)
        self.monitor_box.setEnabled(not on)

    def _toggle_advanced(self, on: bool) -> None:
        self.adv_panel.setVisible(on)
        self.adv_btn.setText(("▾ " if on else "▸ ") + "AVANÇADO")

    def _toggle_live(self, on: bool) -> None:
        if on:
            self._start_live()
        else:
            self._stop_live()

    def _start_live(self) -> None:
        # não misturar com o playback offline
        if self.mixer:
            self.mixer.stop()
        self.separate_btn.setEnabled(False)
        self.transport_widget.setVisible(False)    # sem transporte ao vivo
        self.live_btn.setText("Carregando…")
        self.live_btn.setEnabled(False)
        self.live_model_box.setEnabled(False)
        self.latency_box.setEnabled(False)
        self.live_status.setText("Carregando modelo ao vivo…")

        model_name = LIVE_MODELS[self.live_model_box.currentText()]
        self.live_worker = LiveModelWorker(model_name)
        self.live_worker.ready.connect(self._on_live_ready)
        self.live_worker.failed.connect(self._on_live_failed)
        self.live_worker.start()

    def _on_live_failed(self, msg: str) -> None:
        self.live_status.setText("")
        self.live_btn.setEnabled(True)
        self.live_btn.setText("● Capturar ao vivo")
        self.live_btn.setChecked(False)
        self.live_model_box.setEnabled(True)
        self.latency_box.setEnabled(True)
        self.separate_btn.setEnabled(True)
        QMessageBox.critical(self, "Falha na captura ao vivo", msg)

    def _on_live_ready(self, separator) -> None:  # noqa: ANN001
        from ..capture.live_source import LiveCapture
        from ..capture.router import PipeWireRouter
        from ..engine.live_engine import LiveEngine

        try:
            output_sink = None
            if self.isolate_chk.isChecked():
                # sink virtual: move só o app escolhido, toca no alto-falante real
                app_match = self.app_box.currentData()
                if not app_match:
                    raise RuntimeError(
                        "Nenhum app selecionado. Comece a tocar no Chrome e clique ↻."
                    )
                self.router = PipeWireRouter()
                device, output_sink = self.router.setup(app_match)
            else:
                # modo avançado: captura o monitor escolhido (pode ter eco)
                device = self.monitor_box.currentText()
                if device.startswith("("):
                    device = None

            self.capture = LiveCapture(device=device)
            window_sec = LIVE_WINDOW_OPTIONS[self.latency_box.currentText()]
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
            self.preset_box.setEnabled(True)
            self.preset_box.setCurrentText("Original")

            self.capture.start()
            self.engine.start()
        except Exception as exc:  # noqa: BLE001
            if self.router:
                self.router.teardown()
                self.router = None
            self._on_live_failed(str(exc))
            return

        self.live_btn.setEnabled(True)
        self.live_btn.setText("■ Parar ao vivo")
        if self.isolate_chk.isChecked():
            src = f"só {self.app_box.currentData()}"
        else:
            src = "monitor"
        self.live_status.setText(
            f"● ao vivo · {src} (latência ~{self.engine.latency_seconds:.1f}s)"
        )

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
        if self._target is not self.mixer:
            self._target = None
        self._clear_strips()
        self.preset_box.setEnabled(False)
        self.live_btn.setText("● Capturar ao vivo")
        self.live_btn.setChecked(False)
        self.live_model_box.setEnabled(True)
        self.latency_box.setEnabled(True)
        self.live_status.setText("")
        self.separate_btn.setEnabled(True)
        self.transport_widget.setVisible(bool(self.mixer))   # volta se há arquivo

    # ---- transporte -------------------------------------------------------
    def _toggle_play(self) -> None:
        if not self.mixer:
            return
        playing = self.mixer.toggle()
        self.play_btn.setText("⏸ Pause" if playing else "▶ Play")

    def _stop(self) -> None:
        if self.mixer:
            self.mixer.stop()
            self.play_btn.setText("▶ Play")

    def _on_seek(self, value: int) -> None:
        if self.mixer:
            self.mixer.seek_seconds(value / 1000.0 * self.mixer.duration_seconds)

    def _tick(self) -> None:
        if not self.mixer:
            return
        pos = self.mixer.position_seconds
        dur = self.mixer.duration_seconds
        if dur > 0 and not self.seek.isSliderDown():
            self.seek.setValue(int(pos / dur * 1000))
        self.time_label.setText(f"{_fmt(pos)} / {_fmt(dur)}")
        if not self.mixer.is_playing:
            self.play_btn.setText("▶ Play")

    def closeEvent(self, event):  # noqa: ANN001, N802
        if self.engine:
            self.engine.stop()
        if self.capture:
            self.capture.stop()
        if self.router:
            self.router.teardown()
        if self.mixer:
            self.mixer.close()
        super().closeEvent(event)


def _fmt(seconds: float) -> str:
    seconds = int(seconds)
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def run() -> int:
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.show()
    return app.exec()
