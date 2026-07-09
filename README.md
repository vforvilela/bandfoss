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

**Modo offline (arquivo/URL):**
1. Cole um caminho de arquivo, uma URL do YouTube Music/YouTube, **ou** só digite o
   nome da música (busca automática).
2. Escolha o modelo (`htdemucs_ft` = 4 stems, `htdemucs_6s` = 6 stems).
3. Clique **Separar** e espere.
4. Ajuste os faders, use **M** (mute) / **S** (solo) ou um **preset** (Karaokê etc.)
   e dê **Play**.

**Modo ao vivo (Fase 2):**
1. Toque algo em qualquer app (Spotify, navegador…).
2. Deixe **Isolar áudio** marcado (recomendado) e clique **🔴 Capturar ao vivo**.
   - Isso cria um sink virtual: o app original fica mudo nos alto-falantes e só o
     áudio **processado** toca. Evita ouvir os dois ao mesmo tempo e o loop de
     realimentação. Ao parar, tudo é restaurado automaticamente.
   - Sem isolar (modo avançado): captura o monitor escolhido e toca no default —
     pode haver eco/mistura.
3. Mexa nos faders/presets em tempo real. Latência ≈ 4 s (tamanho da janela do
   Demucs; ajustável em `config.py`).

### Teste headless (sem GUI)

```bash
python scripts/smoke_test.py caminho/da/musica.mp3
python scripts/smoke_test.py "https://music.youtube.com/watch?v=..." --model htdemucs_6s
```

## Status

- **Fase 1 (MVP):** arquivo/URL → Demucs → mixer com faders. ✅
- **Fase 2:** captura ao vivo (monitor PipeWire) + separação em tempo real
  (janela deslizante + overlap-add). ✅ — 24,5× de folga de tempo real na RTX 4080 SUPER.
- **Fase 3:** export de stems, waveform, EQ por stem, latência ajustável na UI.
