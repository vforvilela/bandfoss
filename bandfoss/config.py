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

# Modelos disponíveis na captura AO VIVO (rótulo -> nome do modelo Demucs).
# "Rápido" separa 4 stems; "Guitarra" separa 6 stems (inclui guitarra/piano),
# permitindo mutar especificamente a guitarra gravada da faixa.
LIVE_MODELS = {
    "Rápido · 4 stems": "htdemucs",
    "Guitarra · 6 stems": "htdemucs_6s",
}
LIVE_MODEL = "htdemucs"          # padrão

# Janela deslizante da separação ao vivo.
# Latência ≈ LIVE_WINDOW_SEC (NÃO é o tempo de processamento; é o algoritmo:
# a janela precisa encher antes da 1ª separação). Overlap de 50% (hop = janela/2)
# dá overlap-add perfeito com Hann. Janela menor = menos latência, menos qualidade.
LIVE_WINDOW_SEC = 2.0            # padrão (antes 4.0)
LIVE_HOP_SEC = 1.0

# Opções de latência ao vivo expostas na UI (rótulo -> janela em segundos).
# Janela maior = mais contexto = melhor separação (e mais atraso).
LIVE_WINDOW_OPTIONS = {
    "Baixa · ~1s": 1.0,
    "Média · ~2s": 2.0,
    "Alta · ~3s": 3.0,
    "Máxima · ~6s (+qualidade)": 6.0,
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

# Nomes dos stems por modelo (a ordem real vem do próprio modelo em runtime).
STEM_LABELS = {
    "drums": "Bateria",
    "bass": "Baixo",
    "other": "Outros",
    "vocals": "Vocal",
    "guitar": "Guitarra",
    "piano": "Piano",
}

# Presets: stems a serem MUTADOS ao ativar. Um por instrumento — toque/cante por cima.
# (guitar/piano só existem no modelo de 6 stems; nos outros modelos são ignorados.)
PRESETS = {
    "Original": [],
    "Karaokê (sem vocal)": ["vocals"],
    "Baterista (sem bateria)": ["drums"],
    "Baixista (sem baixo)": ["bass"],
    "Guitarrista (sem guitarra)": ["guitar"],
    "Tecladista (sem piano)": ["piano"],
    "Só vocal (a capella)": ["drums", "bass", "other", "guitar", "piano"],
    "Instrumental": ["vocals"],
}
