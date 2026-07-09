# BandFOSS

**Separe e remixe, em tempo real, o áudio que está tocando no seu computador.**
Isole ou silencie vocal, bateria, baixo, guitarra e mais — para cantar karaokê, tirar
músicas de ouvido ou **tocar junto** com a sua banda. Software livre, para desktop.

Inspirado no **JBL BandBox** (STEM AI), porém aberto e para computador.

Feito por [vforvilela](https://github.com/vforvilela).

---

## O que dá pra fazer

Toque uma música em **qualquer app** (Chrome, Spotify…) e o BandFOSS captura, separa
em faixas e deixa você mixar ao vivo:

- 🎤 **Karaokê** — tira o vocal.
- 🥁 **Tocar junto** — silencia a bateria (ou baixo, ou guitarra) e você toca por cima.
- 🎧 **Estudar de ouvido** — deixa só o instrumento que você quer escutar.

Só o app escolhido é processado — **sua guitarra ao vivo e todo o resto continuam
tocando normais** nas caixas.

> **Plataforma:** a captura ao vivo usa o **PipeWire**, então o BandFOSS roda no
> **Linux**. Precisa de uma **GPU NVIDIA** para separar em tempo real com folga
> (funciona em CPU, porém com mais atraso).

---

## Instalação (Linux)

```bash
# dependências do sistema (Debian/Ubuntu; use o gerenciador da sua distro)
sudo apt install python3-venv ffmpeg pipewire-pulse
sudo apt install libxcb-cursor0     # lib do Qt, se faltar

# o BandFOSS
git clone https://github.com/vforvilela/bandfoss.git
cd bandfoss
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
```

---

## Como usar

```bash
bandfoss
```

1. Comece a tocar a música no **Chrome** (ou outro app).
2. Em **App**, escolha/digite o programa (ex.: `Chrome`) e clique
   **● Capturar ao vivo**.
   - Pode clicar **antes** de dar play: quando o app começar a tocar, o BandFOSS
     pega o áudio sozinho.
3. Mexa nos **faders**, use **M** (mudo) / **S** (solo) ou um **Preset** (Karaokê,
   sem bateria…).

Ao parar, seu áudio volta ao normal.

### 🎸 Tocar guitarra junto

Abra **Avançado**, escolha o modelo **Guitarra · 6 stems**, capture o Chrome e aplique
o preset **Guitarrista (sem guitarra)**. A guitarra gravada some da música e a sua toca
por cima. Em **Avançado** também está a **Latência** (menor = mais responsivo).

---

## Dúvidas comuns

- **"Could not load the Qt platform plugin xcb":** instale `libxcb-cursor0`.
- **Tem uns segundos de atraso ao vivo:** é normal — a IA precisa de uma janela de
  áudio para separar. Reduza em **Avançado → Latência**.
- **Está lento:** você está na CPU. Uma GPU NVIDIA resolve; ou baixe a latência.
- **Não aparece o app na lista:** clique no campo **App** para reabrir a lista (ela se
  atualiza), ou digite o nome do app manualmente.

---

## Créditos & licença

Software livre, feito por **[vforvilela](https://github.com/vforvilela)**.

Motor de separação: [Demucs](https://github.com/facebookresearch/demucs) (Meta).
Inspirado no JBL BandBox — este projeto **não** é afiliado à JBL/Harman.
Respeite os termos de uso dos serviços de streaming.
