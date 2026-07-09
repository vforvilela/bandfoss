"""i18n mínimo, baseado em dicionário. Inglês por padrão; PT-BR disponível.

Troque o idioma com a variável de ambiente BANDFOSS_LANG=pt (ou en), ou chame
`set_language("pt")` em runtime antes de construir a janela.
"""

from __future__ import annotations

import os

DEFAULT_LANG = "en"

_STRINGS = {
    "en": {
        # janela / cabeçalho
        "window_title": "BandFOSS — Live Stem Mixer",
        "subtitle": "STEM MIXER",
        # captura ao vivo
        "app_label": "Source:",
        "app_placeholder": "e.g. Chrome, Spotify…",
        "capture_start": "● Capture live",
        "capture_stop": "■ Stop",
        "loading": "Loading…",
        "loading_model": "Loading live model…",
        "requires_linux": "requires Linux (PipeWire)",
        "linux_only_tip": "BandFOSS captures system audio via PipeWire — Linux only.",
        "status_live": "● live · {src} (latency ~{sec:.1f}s)",
        "src_only": "{app} only",
        "src_monitor": "monitor",
        "err_capture_title": "Live capture failed",
        "err_no_app": "Type the source app to capture (e.g. Chrome).",
        # avançado
        "advanced": "ADVANCED",
        "model_label": "Model:",
        "latency_label": "Latency:",
        "isolate": "Isolate by app (recommended)",
        "monitor_label": "Monitor (no isolation):",
        "model_tip": (
            "Fast (4 stems): drums/bass/vocals/other.\n"
            "Guitar (6 stems): adds guitar and piano — lets you mute the recorded\n"
            "guitar or keys specifically (a bit slower)."
        ),
        "latency_tip": (
            "Live audio delay = size of the Demucs window (not the processing time).\n"
            "Smaller = more responsive; larger = cleaner separation."
        ),
        "isolate_tip": (
            "On: only the chosen app is processed; your live instrument and other\n"
            "apps stay untouched. Off: captures the Monitor below (may echo)."
        ),
        # mixer
        "footer_prefix": "BandFOSS · free software · by ",
        # stems
        "stem_vocals": "Vocals", "stem_drums": "Drums", "stem_bass": "Bass",
        "stem_other": "Other", "stem_guitar": "Guitar", "stem_piano": "Piano",
        # modelos
        "model_fast4": "Fast · 4 stems",
        "model_guitar6": "Guitar · 6 stems",
        # latências
        "latency_low": "Low · ~1s",
        "latency_medium": "Medium · ~2s",
        "latency_high": "High · ~3s",
        "latency_max": "Max · ~6s (+quality)",
    },
    "pt": {
        "window_title": "BandFOSS — Mixer de Stems ao vivo",
        "subtitle": "STEM MIXER",
        "app_label": "Fonte:",
        "app_placeholder": "ex.: Chrome, Spotify…",
        "capture_start": "● Capturar ao vivo",
        "capture_stop": "■ Parar",
        "loading": "Carregando…",
        "loading_model": "Carregando modelo ao vivo…",
        "requires_linux": "requer Linux (PipeWire)",
        "linux_only_tip": "BandFOSS captura o áudio do sistema via PipeWire — só no Linux.",
        "status_live": "● ao vivo · {src} (latência ~{sec:.1f}s)",
        "src_only": "só {app}",
        "src_monitor": "monitor",
        "err_capture_title": "Falha na captura ao vivo",
        "err_no_app": "Informe o app a capturar (ex.: Chrome).",
        "advanced": "AVANÇADO",
        "model_label": "Modelo:",
        "latency_label": "Latência:",
        "isolate": "Isolar por app (recomendado)",
        "monitor_label": "Monitor (sem isolar):",
        "model_tip": (
            "Rápido (4 stems): bateria/baixo/vocal/outros.\n"
            "Guitarra (6 stems): adiciona guitarra e piano — permite mutar a guitarra\n"
            "ou o teclado gravados especificamente (um pouco mais lento)."
        ),
        "latency_tip": (
            "Atraso do áudio ao vivo = tamanho da janela do Demucs (não é o\n"
            "processamento). Menor = mais responsivo; maior = melhor separação."
        ),
        "isolate_tip": (
            "Ligado: processa só o app escolhido; seu instrumento ao vivo e os demais\n"
            "apps seguem intactos. Desligado: captura o Monitor abaixo (pode ter eco)."
        ),
        "footer_prefix": "BandFOSS · software livre · feito por ",
        "stem_vocals": "Vocal", "stem_drums": "Bateria", "stem_bass": "Baixo",
        "stem_other": "Outros", "stem_guitar": "Guitarra", "stem_piano": "Piano",
        "model_fast4": "Rápido · 4 stems",
        "model_guitar6": "Guitarra · 6 stems",
        "latency_low": "Baixa · ~1s",
        "latency_medium": "Média · ~2s",
        "latency_high": "Alta · ~3s",
        "latency_max": "Máxima · ~6s (+qualidade)",
    },
}

_lang = os.environ.get("BANDFOSS_LANG", DEFAULT_LANG)
if _lang not in _STRINGS:
    _lang = DEFAULT_LANG


def set_language(lang: str) -> None:
    global _lang
    _lang = lang if lang in _STRINGS else DEFAULT_LANG


def current_language() -> str:
    return _lang


def t(key: str, **kwargs) -> str:
    """Traduz `key` no idioma atual (fallback: inglês, depois a própria chave)."""
    s = _STRINGS.get(_lang, {}).get(key)
    if s is None:
        s = _STRINGS[DEFAULT_LANG].get(key, key)
    return s.format(**kwargs) if kwargs else s
