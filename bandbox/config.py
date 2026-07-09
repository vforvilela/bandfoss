"""Configuração central do BandBox."""

from __future__ import annotations

# Áudio ----------------------------------------------------------------------
SAMPLE_RATE = 44100          # Demucs opera nativamente em 44.1 kHz
CHANNELS = 2                 # estéreo
BLOCK_SIZE = 1024            # frames por callback do sounddevice (~23 ms)

# Modelos Demucs -------------------------------------------------------------
# htdemucs_ft -> 4 stems (drums, bass, other, vocals)  [melhor qualidade 4-stem]
# htdemucs_6s -> 6 stems (+ guitar, piano)             [espelha o BandBox]
MODEL_4STEM = "htdemucs_ft"
MODEL_6STEM = "htdemucs_6s"
DEFAULT_MODEL = MODEL_4STEM

# Modelo usado na captura AO VIVO: modelo único (não-ensemble) por velocidade.
LIVE_MODEL = "htdemucs"

# Janela deslizante da separação ao vivo.
# Latência ≈ LIVE_WINDOW_SEC; overlap de 50% (hop = janela/2) dá overlap-add
# perfeito com janela de Hann. Janela menor = menos latência, menos qualidade.
LIVE_WINDOW_SEC = 4.0
LIVE_HOP_SEC = 2.0

# Nomes dos stems por modelo (a ordem real vem do próprio modelo em runtime).
STEM_LABELS = {
    "drums": "Bateria",
    "bass": "Baixo",
    "other": "Outros",
    "vocals": "Vocal",
    "guitar": "Guitarra",
    "piano": "Piano",
}

# Presets estilo BandBox: stems a serem MUTADOS ao ativar o preset.
PRESETS = {
    "Original": [],
    "Karaokê (sem vocal)": ["vocals"],
    "Baterista (sem bateria)": ["drums"],
    "Baixista (sem baixo)": ["bass"],
    "Só vocal (a capella)": ["drums", "bass", "other", "guitar", "piano"],
    "Instrumental": ["vocals"],
}
