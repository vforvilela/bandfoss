"""Janela principal do BandBox (PySide6).

Fluxo: carregar fonte (arquivo/URL) -> separar em QThread -> montar mixer com
um fader + mute/solo por stem, transporte e presets.
"""

from __future__ import annotations

from typing import Dict, Optional

import numpy as np
from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFrame,
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

from ..config import DEFAULT_MODEL, PRESETS, STEM_LABELS
from ..engine.mixer import StemMixer


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


class StemStrip(QWidget):
    """Coluna de controle de um stem: fader vertical + mute + solo + nome."""

    def __init__(self, name: str, on_gain, on_mute, on_solo):
        super().__init__()
        self._name = name
        self._on_gain = on_gain
        self._on_mute = on_mute
        self._on_solo = on_solo

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignHCenter)

        self.fader = QSlider(Qt.Vertical)
        self.fader.setRange(0, 150)          # 0–150% de ganho
        self.fader.setValue(100)
        self.fader.setMinimumHeight(160)
        self.fader.valueChanged.connect(lambda v: self._on_gain(name, v / 100.0))

        self.value_label = QLabel("100%")
        self.value_label.setAlignment(Qt.AlignHCenter)
        self.fader.valueChanged.connect(lambda v: self.value_label.setText(f"{v}%"))

        self.mute_btn = QPushButton("M")
        self.mute_btn.setCheckable(True)
        self.mute_btn.setFixedWidth(40)
        self.mute_btn.toggled.connect(lambda on: self._on_mute(name, on))

        self.solo_btn = QPushButton("S")
        self.solo_btn.setCheckable(True)
        self.solo_btn.setFixedWidth(40)
        self.solo_btn.toggled.connect(lambda on: self._on_solo(name, on))

        btn_row = QHBoxLayout()
        btn_row.addWidget(self.mute_btn)
        btn_row.addWidget(self.solo_btn)

        title = QLabel(STEM_LABELS.get(name, name.capitalize()))
        title.setAlignment(Qt.AlignHCenter)
        title.setStyleSheet("font-weight: bold;")

        layout.addWidget(self.fader, alignment=Qt.AlignHCenter)
        layout.addWidget(self.value_label)
        layout.addLayout(btn_row)
        layout.addWidget(title)


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("BandBox — Separador de Stems")
        self.resize(680, 460)

        self.mixer: Optional[StemMixer] = None
        self.worker: Optional[SeparationWorker] = None
        self.strips: Dict[str, StemStrip] = {}

        root = QVBoxLayout(self)

        # --- barra de fonte ---
        src_row = QHBoxLayout()
        self.source_input = QLineEdit()
        self.source_input.setPlaceholderText(
            "Caminho do arquivo ou URL (YouTube Music/YouTube)…"
        )
        browse_btn = QPushButton("Abrir…")
        browse_btn.clicked.connect(self._browse)
        self.model_box = QComboBox()
        self.model_box.addItems([DEFAULT_MODEL, "htdemucs_6s"])
        self.separate_btn = QPushButton("Separar")
        self.separate_btn.clicked.connect(self._start_separation)
        src_row.addWidget(self.source_input, 1)
        src_row.addWidget(browse_btn)
        src_row.addWidget(self.model_box)
        src_row.addWidget(self.separate_btn)
        root.addLayout(src_row)

        # --- progresso ---
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setVisible(False)
        root.addWidget(self.progress)

        # --- área dos stems ---
        self.strip_row = QHBoxLayout()
        strip_frame = QFrame()
        strip_frame.setLayout(self.strip_row)
        strip_frame.setFrameShape(QFrame.StyledPanel)
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

        # --- transporte ---
        transport = QHBoxLayout()
        self.play_btn = QPushButton("▶ Play")
        self.play_btn.clicked.connect(self._toggle_play)
        self.play_btn.setEnabled(False)
        self.stop_btn = QPushButton("■ Stop")
        self.stop_btn.clicked.connect(self._stop)
        self.stop_btn.setEnabled(False)
        self.seek = QSlider(Qt.Horizontal)
        self.seek.setRange(0, 1000)
        self.seek.sliderMoved.connect(self._on_seek)
        self.time_label = QLabel("00:00 / 00:00")
        transport.addWidget(self.play_btn)
        transport.addWidget(self.stop_btn)
        transport.addWidget(self.seek, 1)
        transport.addWidget(self.time_label)
        root.addLayout(transport)

        # timer para atualizar posição/tempo
        self._timer = QTimer(self)
        self._timer.setInterval(200)
        self._timer.timeout.connect(self._tick)

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
            QMessageBox.warning(self, "BandBox", "Informe um arquivo ou URL.")
            return
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
        for name in self.mixer.names:
            strip = StemStrip(name, self._set_gain, self._set_mute, self._set_solo)
            self.strips[name] = strip
            self.strip_row.addWidget(strip)

        self.play_btn.setEnabled(True)
        self.stop_btn.setEnabled(True)
        self.preset_box.setEnabled(True)
        self.preset_box.setCurrentText("Original")
        self._timer.start()

    def _clear_strips(self) -> None:
        for strip in self.strips.values():
            strip.setParent(None)
        self.strips.clear()

    # ---- callbacks de stem ------------------------------------------------
    def _set_gain(self, name: str, gain: float) -> None:
        if self.mixer:
            self.mixer.set_gain(name, gain)

    def _set_mute(self, name: str, muted: bool) -> None:
        if self.mixer:
            self.mixer.set_muted(name, muted)

    def _set_solo(self, name: str, on: bool) -> None:
        if not self.mixer:
            return
        if on:
            for other, strip in self.strips.items():
                if other != name and strip.solo_btn.isChecked():
                    strip.solo_btn.setChecked(False)
            self.mixer.set_solo(name)
        else:
            self.mixer.set_solo(None)

    def _apply_preset(self, preset: str) -> None:
        if not self.mixer:
            return
        mute_set = set(PRESETS.get(preset, []))
        for name, strip in self.strips.items():
            should_mute = name in mute_set
            strip.mute_btn.setChecked(should_mute)

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
