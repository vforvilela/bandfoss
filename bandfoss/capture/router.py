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

    def setup(self, app_match: str) -> Tuple[str, str]:
        """Cria o sink virtual e move só os streams do app `app_match` para ele.

        `app_match` é comparado (case-insensitive, substring) contra o nome/binário
        do aplicativo. Retorna (monitor_para_capturar, sink_real_para_a_saida).
        NÃO altera o sink padrão — guitarra e demais apps seguem intactos.
        """
        self._cleanup_existing()                 # remove sinks bandfoss sobrando
        self.real_sink = self._pick_real_sink()  # alto-falante real (não o virtual)
        self.module_id = _run([
            self._pactl, "load-module", "module-null-sink",
            f"sink_name={self.sink_name}",
            "sink_properties=device.description=BandFOSS_Capture",
        ])

        needle = app_match.lower()
        moved = 0
        for a in list_playback_apps():
            hay = f"{a['app']} {a['binary']} {a['media']}".lower()
            if needle in hay:
                r = subprocess.run(
                    [self._pactl, "move-sink-input", a["id"], self.sink_name],
                    check=False,
                )
                if r.returncode == 0:
                    self._moved_ids.append(a["id"])
                    moved += 1
        if moved == 0:
            # nada casou -> desfaz para não deixar um sink virtual órfão
            self.teardown()
            raise RuntimeError(
                f"Nenhum stream de '{app_match}' tocando agora. "
                "Comece a tocar a música no app e tente de novo."
            )
        return f"{self.sink_name}.monitor", self.real_sink

    def teardown(self) -> None:
        """Devolve os streams ao sink real e remove o sink virtual."""
        if self.real_sink:
            for sid in self._inputs_on_virtual():
                subprocess.run(
                    [self._pactl, "move-sink-input", sid, self.real_sink], check=False
                )
        self._moved_ids.clear()
        if self.module_id:
            subprocess.run([self._pactl, "unload-module", self.module_id], check=False)
            self.module_id = None
