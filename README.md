# BandBox Desktop

Separação de faixas (stems) no desktop Linux, inspirado no **JBL BandBox STEM AI**,
100% open source. Isola/muta vocais, bateria, baixo, guitarra etc. de uma música —
para tocar junto, karaokê ou praticar.

Veja [`ARCHITECTURE.md`](ARCHITECTURE.md) para o design completo.

## Requisitos

- Linux com PipeWire, Python ≥ 3.10
- `ffmpeg` e (opcional, para URLs) `yt-dlp` no PATH
- GPU NVIDIA com CUDA (recomendado; roda em CPU, porém lento)

## Instalação

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .            # núcleo (demucs, torch, PySide6, …)
# para baixar de URLs, se yt-dlp não estiver no sistema:
pip install -e ".[download]"
```

## Uso

### App gráfico

```bash
bandbox            # ou: python -m bandbox
```

1. Cole um caminho de arquivo **ou** uma URL do YouTube Music/YouTube.
2. Escolha o modelo (`htdemucs_ft` = 4 stems, `htdemucs_6s` = 6 stems).
3. Clique **Separar** e espere.
4. Ajuste os faders, use **M** (mute) / **S** (solo) ou um **preset** (Karaokê etc.)
   e dê **Play**.

### Teste headless (sem GUI)

```bash
python scripts/smoke_test.py caminho/da/musica.mp3
python scripts/smoke_test.py "https://music.youtube.com/watch?v=..." --model htdemucs_6s
```

## Status

- **Fase 1 (MVP):** arquivo/URL → Demucs → mixer com faders. ✅ em andamento
- **Fase 2:** captura ao vivo (PipeWire) + separação em tempo real.
- **Fase 3:** presets, export de stems, waveform, EQ por stem.
