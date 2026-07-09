"""Configuração central do BandFOSS."""

from __future__ import annotations

# Áudio ----------------------------------------------------------------------
SAMPLE_RATE = 44100          # Demucs opera nativamente em 44.1 kHz
CHANNELS = 2                 # estéreo
BLOCK_SIZE = 1024            # frames por callback do sounddevice (~23 ms)

# Modelos Demucs -------------------------------------------------------------
# htdemucs_ft -> 4 stems (drums, bass, other, vocals)  [melhor qualidade 4-stem]
# htdemucs_6s -> 6 stems (+ guitar, piano)             [espelha o JBL BandBox]
MODEL_4STEM = "htdemucs_ft"
MODEL_6STEM = "htdemucs_6s"
DEFAULT_MODEL = MODEL_4STEM

# Modelos disponíveis na captura AO VIVO (id -> nome do modelo Demucs).
# O rótulo exibido vem do i18n (model_<id>). "fast4" = 4 stems; "guitar6" = 6 stems.
LIVE_MODELS = {
    "fast4": "htdemucs",
    "guitar6": "htdemucs_6s",
}
LIVE_MODEL = "htdemucs"          # padrão

# Janela deslizante da separação ao vivo.
# Latência ≈ LIVE_WINDOW_SEC (NÃO é o tempo de processamento; é o algoritmo:
# a janela precisa encher antes da 1ª separação). Overlap de 50% (hop = janela/2)
# dá overlap-add perfeito com Hann. Janela menor = menos latência, menos qualidade.
LIVE_WINDOW_SEC = 2.0            # padrão (id "medium")
LIVE_HOP_SEC = 1.0

# Opções de latência ao vivo (id -> janela em segundos). Rótulo vem do i18n.
LIVE_WINDOWS = {
    "low": 1.0,
    "medium": 2.0,
    "high": 3.0,
    "max": 6.0,
}

# "shifts" do Demucs no modo ao vivo: passadas com deslocamento aleatório, cuja
# média reduz artefatos. Mais = melhor e mais lento. A RTX 4080 aguenta com folga.
LIVE_SHIFTS = 2

# Ordem de exibição dos faders na UI: voz primeiro, "outros" por último.
STEM_ORDER = ["vocals", "drums", "bass", "guitar", "piano", "other"]


def order_stems(names):
    """Reordena os stems para exibição: voz primeiro, 'outros' por último."""
    known = [s for s in STEM_ORDER if s in names]
    rest = [s for s in names if s not in STEM_ORDER]
    return known + rest


# Cor de cada canal (code de cor tipo mixer). Hues distintos, legíveis no escuro.
STEM_COLORS = {
    "vocals": "#4CC2C4",   # teal — voz
    "drums": "#E5484D",    # vermelho — bateria
    "bass": "#7C5CFF",     # violeta — baixo
    "other": "#F2A93B",    # âmbar — outros
    "guitar": "#6FCF57",   # verde — guitarra
    "piano": "#C77DFF",    # lilás — piano
}

