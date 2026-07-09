# BandBox Desktop (open source) — Arquitetura

Separação de faixas (stems) no desktop Linux, inspirado no **JBL BandBox STEM AI**,
usando ferramentas open source. Isola/muta vocais, bateria, baixo, guitarra, etc. de
uma música — para tocar junto, fazer karaokê ou praticar.

> Referência de features: JBL BandBox Solo/Trio (`STEM AI`) e Moises.ai / RipX.
> Equivalente open source do núcleo: **Demucs** (Meta).

## Objetivo

Reproduzir a experiência do STEM AL do BandBox no desktop:

- Pega uma música (arquivo local, URL do YouTube Music, ou o áudio do sistema ao vivo).
- Separa em stems: **vocals / drums / bass / other** (4-stem) ou
  **+ guitar / piano** (6-stem, modelo `htdemucs_6s`).
- Mixer com fader + mute/solo por stem, em tempo real, enquanto toca.
- Presets estilo BandBox: *Karaokê* (muta vocal), *Baterista* (muta drums), etc.

## Visão geral

```
┌─────────────┐   ┌──────────────┐   ┌───────────────┐   ┌──────────┐
│  FONTE      │──▶│  CAPTURA     │──▶│  SEPARAÇÃO    │──▶│  MIXER   │──▶ saída
│ arquivo /   │   │  yt-dlp /    │   │  Demucs (CUDA)│   │ N ganhos │   (alto-falante)
│ URL / live  │   │  PipeWire    │   │  htdemucs     │   │ mute/solo│
└─────────────┘   └──────────────┘   └───────────────┘   └──────────┘
```

## Camadas

### 1. Captura da fonte

| Fonte | Mecanismo | Status |
|---|---|---|
| Arquivo local (mp3/wav/flac/…) | `ffmpeg` normaliza → PCM 44.1k estéreo | **Fase 1 (MVP)** |
| YouTube Music / YouTube | `yt-dlp` baixa bestaudio → `ffmpeg` → wav | **Fase 1 (MVP)** |
| Áudio do sistema ao vivo (Spotify, navegador) | monitor do **PipeWire** (`pw-record`) | Fase 2 |
| Spotify direto | `librespot` (Spotify Connect, requer Premium) | Opcional/futuro |

**Nota legal/ToS:** a captura via monitor do PipeWire (o áudio já decodificado saindo
para a placa de som) é a rota mais defensável. `yt-dlp`/`librespot` ficam como plugins
opcionais, nunca como dependência central.

### 2. Separação (núcleo)

- Motor: **Demucs** (`htdemucs_ft` para 4 stems / `htdemucs_6s` para 6 stems).
- Roda em **CUDA** (RTX 4080 SUPER, 16 GB) — separação de uma faixa em segundos.
- Wrapper próprio (`engine/separator.py`) expõe `separate(pcm) -> {stem: array}`.
- Qualidade > Spleeter (Deezer), que fica como fallback rápido se necessário.

### 3. Mixer + playback

- Reprodução via **sounddevice** (PortAudio) com callback de baixa latência.
- O mix é uma **soma ponderada** dos stems pelos ganhos dos faders — calculada por
  amostra no callback, então mexer no fader/mute reflete imediatamente no som.
- Transport: play / pause / stop / seek / barra de progresso.

### 4. UI

- **PySide6** (Qt) — tudo em Python, um processo para a janela.
- Faders verticais + mute/solo por stem, controles de transporte, presets.
- A separação roda numa `QThread` para não travar a interface.

## Modos (espelhando o BandBox)

| Modo BandBox | Aqui | Latência |
|---|---|---|
| Multi-stem separation (~2 s) | Fase 2 — janela deslizante ao vivo | ~1–3 s |
| Karaoke (~500 ms) | Fase 2 — modelo mais leve / hop menor | alvo <1 s |
| Export remixes | Fase 3 — salvar stems em disco | — |

## Estrutura do projeto

```
bandbox/
├── pyproject.toml
├── ARCHITECTURE.md              # este arquivo
├── bandbox/
│   ├── config.py                # sample rate, modelo, nomes dos stems, presets
│   ├── capture/
│   │   ├── file_source.py       # arquivo local / URL (yt-dlp) → PCM  [Fase 1]
│   │   └── live_source.py       # monitor PipeWire → PCM               [Fase 2]
│   ├── engine/
│   │   ├── separator.py         # wrapper Demucs (CUDA)                [Fase 1]
│   │   └── mixer.py             # soma ponderada + saída sounddevice   [Fase 1]
│   ├── ui/
│   │   └── main_window.py       # PySide6: faders, transporte          [Fase 1]
│   └── app.py                   # entry point / fiação
└── models/                      # cache dos pesos do Demucs
```

## Roadmap

- **Fase 1 — MVP offline** *(em andamento)*
  arquivo/URL → Demucs → mixer com faders. Sincronia perfeita, qualidade máxima.
- **Fase 2 — Tempo real** — captura PipeWire + separação em janela deslizante com
  overlap-add; presets Karaokê/Multi-stem; latência ~1–3 s.
- **Fase 3 — Polimento** — presets nomeados, export de stems, waveform, EQ por stem,
  detecção de troca de faixa na captura ao vivo.

## Riscos / decisões registradas

1. **Legal/ToS:** captura via monitor PipeWire é a rota principal; downloaders são
   plugins opcionais.
2. **Latência do tempo real** é inerente ao Demucs (precisa de contexto futuro).
   Janela deslizante é o teto realista — não prometemos "zero latência".
3. **Captura ao vivo não tem metadados** (nome da faixa, troca de música) — detecção
   fica para a Fase 3.

## Ambiente alvo

- Linux, PipeWire, Python 3.12, GPU NVIDIA (CUDA). ffmpeg + yt-dlp no PATH.
