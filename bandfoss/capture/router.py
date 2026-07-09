"""Roteamento seletivo no PipeWire para captura ao vivo por aplicativo.

Cria um *sink virtual* (null sink) e move para ele **apenas o app escolhido**
(ex.: Chrome). O BandFOSS captura o monitor desse sink e toca o resultado
processado no alto-falante real. Todo o resto — inclusive uma guitarra ao vivo —
continua tocando normalmente nos alto-falantes, sem captura nem processamento.

  Chrome ─► [sink virtual] ─► monitor ─► BandFOSS ─► pacat ─► [sink real] ─► 🔊
  Guitarra ──────────────────────────────────────────────► [sink real] ─► 🔊
"""

from __future__ import annotations

import re
import shutil
import subprocess
import threading
from typing import Dict, List, Optional, Tuple


def _require(tool: str) -> str:
    path = shutil.which(tool)
    if path is None:
        raise RuntimeError(f"'{tool}' não encontrado no PATH.")
    return path


def _run(args: List[str]) -> str:
    return subprocess.check_output(args, text=True).strip()


def list_playback_apps() -> List[Dict[str, str]]:
    """Lista os streams tocando agora: {id, app, binary, media, label}."""
    pactl = _require("pactl")
    out = subprocess.check_output([pactl, "list", "sink-inputs"], text=True)
    apps: List[Dict[str, str]] = []
    cur: Optional[Dict[str, str]] = None
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
    """Move o app escolhido para um sink virtual; devolve tudo no teardown."""

    def __init__(self, sink_name: str = "bandfoss_capture"):
        self.sink_name = sink_name
        self._pactl = _require("pactl")
        self.module_id: Optional[str] = None
        self.real_sink: Optional[str] = None
        self._moved_ids: List[str] = []
        self._needle: str = ""
        self._watch_proc: Optional[subprocess.Popen] = None
        self._watch_thread: Optional[threading.Thread] = None

    def _modules_for_our_sink(self) -> List[str]:
        """IDs de módulos null-sink já criados com o nosso sink_name (sobras)."""
        out = subprocess.check_output([self._pactl, "list", "modules"], text=True)
        ids: List[str] = []
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
        """Sink de saída real (hardware), ignorando o virtual e monitores."""
        default = _run([self._pactl, "get-default-sink"])
        if default and default != self.sink_name and not default.endswith(".monitor"):
            return default
        out = subprocess.check_output([self._pactl, "list", "sinks", "short"], text=True)
        for line in out.splitlines():
            parts = line.split("\t")
            if len(parts) >= 2 and parts[1].startswith("alsa_output."):
                return parts[1]
        raise RuntimeError("Nenhum sink de saída de hardware encontrado.")

    def _virtual_sink_index(self) -> Optional[str]:
        out = subprocess.check_output([self._pactl, "list", "sinks", "short"], text=True)
        for line in out.splitlines():
            parts = line.split("\t")
            if len(parts) >= 2 and parts[1] == self.sink_name:
                return parts[0]
        return None

    def _inputs_on_virtual(self) -> List[str]:
        idx = self._virtual_sink_index()
        if idx is None:
            return []
        out = subprocess.check_output(
            [self._pactl, "list", "sink-inputs", "short"], text=True
        )
        return [
            l.split("\t")[0]
            for l in out.splitlines()
            if "\t" in l and l.split("\t")[1] == str(idx)
        ]

    def _input_sink_map(self) -> Dict[str, str]:
        """{id_do_stream: índice_do_sink} para todos os sink-inputs."""
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
        """Move para o sink virtual os streams do app que ainda não estão nele."""
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

    def setup(self, app_match: str) -> Tuple[str, str]:
        """Cria o sink virtual e passa a capturar SÓ o app `app_match`.

        Move o que já está tocando E vigia novos streams do app (via
        `pactl subscribe`), então você pode iniciar a captura ANTES de dar play —
        quando o app começar a tocar, o stream é movido automaticamente.
        `app_match`: substring case-insensitive do nome/binário do app.
        Retorna (monitor_para_capturar, sink_real_para_a_saida). NÃO mexe no sink
        padrão — guitarra e demais apps seguem intactos.
        """
        self._needle = app_match.lower()
        self._cleanup_existing()                 # remove sinks bandfoss sobrando
        self.real_sink = self._pick_real_sink()  # alto-falante real (não o virtual)
        self.module_id = _run([
            self._pactl, "load-module", "module-null-sink",
            f"sink_name={self.sink_name}",
            "sink_properties=device.description=BandFOSS_Capture",
        ])
        self._move_matching()                    # move o que já está tocando (se houver)
        self._start_watcher()                    # vigia novos streams do app
        return f"{self.sink_name}.monitor", self.real_sink

    def _start_watcher(self) -> None:
        self._watch_proc = subprocess.Popen(
            [self._pactl, "subscribe"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
        )
        self._watch_thread = threading.Thread(target=self._watch_loop, daemon=True)
        self._watch_thread.start()

    def _watch_loop(self) -> None:
        """A cada evento de sink-input novo/alterado, tenta mover o app escolhido."""
        try:
            for line in self._watch_proc.stdout:
                if "sink-input" in line and ("'new'" in line or "'change'" in line):
                    try:
                        self._move_matching()
                    except Exception:  # noqa: BLE001 — captura pode estar encerrando
                        pass
        except Exception:  # noqa: BLE001
            pass

    def teardown(self) -> None:
        """Para o vigia, devolve os streams ao sink real e remove o sink virtual."""
        if self._watch_proc is not None:
            self._watch_proc.terminate()
            self._watch_proc = None
        if self.real_sink:
            for sid in self._inputs_on_virtual():
                subprocess.run(
                    [self._pactl, "move-sink-input", sid, self.real_sink], check=False
                )
        self._moved_ids.clear()
        if self.module_id:
            subprocess.run([self._pactl, "unload-module", self.module_id], check=False)
            self.module_id = None
