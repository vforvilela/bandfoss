# BandFOSS

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
bandfoss            # ou: python -m bandfoss
```

**Modo offline (arquivo/URL):**
1. Cole um caminho de arquivo, uma URL do YouTube Music/YouTube, **ou** só digite o
   nome da música (busca automática).
2. Escolha o modelo (`htdemucs_ft` = 4 stems, `htdemucs_6s` = 6 stems).
3. Clique **Separar** e espere.
4. Ajuste os faders, use **M** (mute) / **S** (solo) ou um **preset** (Karaokê etc.)
   e dê **Play**.

**Modo ao vivo (Fase 2):**
1. Toque algo em qualquer app (Spotify, Chrome…).
2. Em **App:** escolha o app (a lista se atualiza ao abrir) e clique
   **🔴 Capturar ao vivo**. Só aquele app é processado — sua guitarra ao vivo e o
   resto seguem tocando normalmente. Ao parar, tudo é restaurado.
3. Mexa nos faders/presets em tempo real.

**Avançado** (recolhido por padrão) expõe:
- **Modelo (ao vivo):** *Rápido · 4 stems* ou *Guitarra · 6 stems* (`htdemucs_6s`,
  adiciona guitarra/piano — permite mutar a guitarra gravada da faixa).
- **Latência:** Baixa ~1s / Média ~2s / Alta ~3s (tamanho da janela do Demucs).
- **Modelo (arquivo)** e o modo **Monitor** (captura sem isolar por app).

> **Tocar guitarra junto:** em Avançado escolha *Guitarra · 6 stems*; capture o
> Chrome e aplique o preset *Guitarrista (sem guitarra)* — a guitarra gravada some
> da música e sua guitarra ao vivo (não capturada) toca por cima.

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
