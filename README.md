# BandFOSS

**Separe e remixe qualquer música em tempo real.** Isole ou silencie vocal, bateria,
baixo, guitarra e mais — para cantar karaokê, tirar músicas de ouvido ou **tocar junto**
com a sua banda. 100% software livre, para desktop.

Inspirado no **JBL BandBox** (STEM AI), porém aberto e para computador.

![BandFOSS](https://img.shields.io/badge/licen%C3%A7a-livre-FF7A18) &nbsp; Feito por [vforvilela](https://github.com/vforvilela)

---

## O que dá pra fazer

- 🎤 **Karaokê** — tira o vocal de qualquer faixa.
- 🥁 **Tocar junto** — silencia a bateria (ou baixo, ou guitarra) e você toca por cima.
- 🎧 **Estudar de ouvido** — deixa só o instrumento que você quer escutar.
- ⏱️ **Ao vivo** — captura o que está tocando no Chrome/Spotify e separa em tempo real
  (Linux).

Você pode partir de:
- um **arquivo** (mp3, wav, flac, m4a…),
- uma **URL** do YouTube / YouTube Music,
- só o **nome da música** (ele busca sozinho),
- ou o **áudio ao vivo** de um app (Linux).

---

## Instalação

Você precisa de **Python 3.10+**, **ffmpeg** e (para URLs) **yt-dlp**.

### Linux

```bash
# dependências do sistema (Debian/Ubuntu; use o gerenciador da sua distro)
sudo apt install python3-venv ffmpeg
pip install --user yt-dlp        # ou: sudo apt install yt-dlp
# faltando a lib do Qt em algumas distros:
sudo apt install libxcb-cursor0

# o BandFOSS
git clone https://github.com/vforvilela/bandfoss.git
cd bandfoss
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
```

> **Placa de vídeo:** com GPU **NVIDIA** a separação é quase instantânea. Sem GPU
> funciona na CPU, só é mais lento.

### macOS

```bash
# Homebrew (https://brew.sh)
brew install python ffmpeg yt-dlp

git clone https://github.com/vforvilela/bandfoss.git
cd bandfoss
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
```

> **Apple Silicon (M1/M2/M3…):** usa a GPU do Mac (Metal/MPS) automaticamente; se der
> algum problema, cai para a CPU. **Modo offline (arquivo/URL) funciona no Mac.**
> **A captura ao vivo ainda é só no Linux** (depende do PipeWire) — veja abaixo.

---

## Como usar

Abra o app:

```bash
bandfoss
```

### 🎵 A partir de um arquivo, URL ou busca

1. Cole um **arquivo**, uma **URL** ou só digite o **nome da música**.
2. Clique **Separar** e aguarde (a primeira vez baixa o modelo de IA, ~80 MB).
3. Use os **faders** de cada faixa, os botões **M** (mudo) / **S** (solo) ou um
   **Preset** pronto (Karaokê, sem bateria…). Dê **Play**.

### 🔴 Ao vivo (Linux)

1. Em **App**, escolha (ou digite) o programa a capturar — ex.: `Chrome`.
2. Clique **● Capturar ao vivo**. Pode começar a captura **antes** de dar play: quando
   o app começar a tocar, o BandFOSS pega o áudio sozinho.
3. Mexa nos faders/presets em tempo real.

Só o app escolhido é processado — **sua guitarra ao vivo e todo o resto continuam
tocando normais** nas caixas. Ao parar, tudo volta ao normal.

### 🎸 Tocar guitarra junto (dica)

Abra **Avançado**, escolha o modelo **Guitarra · 6 stems**, capture o Chrome e aplique o
preset **Guitarrista (sem guitarra)**. A guitarra gravada some da música e a sua toca por
cima. (Em **Avançado** também ficam o modelo do modo arquivo e a **latência** do modo ao
vivo — quanto menor, mais responsivo.)

---

## Dúvidas comuns

- **"Could not load the Qt platform plugin xcb"** (Linux): instale `libxcb-cursor0`
  (veja acima).
- **A separação está lenta:** você está na CPU. Uma GPU NVIDIA resolve; ou baixe a
  qualidade/latência em **Avançado**.
- **O modo ao vivo tem uns segundos de atraso:** é normal — a IA precisa de uma janela
  de áudio para separar. Reduza em **Avançado → Latência**.
- **No Mac o botão "Capturar ao vivo" está desativado:** a captura ao vivo depende do
  PipeWire (Linux). O modo arquivo/URL funciona normalmente no Mac.

---

## Créditos & licença

Software livre, feito por **[vforvilela](https://github.com/vforvilela)**.

Motor de separação: [Demucs](https://github.com/facebookresearch/demucs) (Meta).
Inspirado no JBL BandBox — este projeto **não** é afiliado à JBL/Harman.
Respeite os termos de uso dos serviços de streaming.
