# Family Jam Setup — JBL BandBox Trio + Imenso X74

## The Family

- **Guitar** player
- **Keyboard** player
- **Electronic drums** player
- Plus vocals (anyone, via Imenso wireless mics)

## Gear We Have

| Device | Role |
|---|---|
| **JBL BandBox Trio** | Brain — 4-channel mixer, instrument inputs, STEM AI for the streamed song, guitar effects |
| **Imenso X74** | Final PA — 200 W speaker + 2 wireless microphones for vocals |

## Signal Flow

```
Guitar     ─► Trio CH3 (Hi-Z 1/4")
Keyboard   ─► Trio CH2 (1/4" combo, slider → line)
E-drums    ─► Trio CH1 (1/4" combo, line)
Phone/song ─► Trio CH4 via Bluetooth ─► STEM AI

         Trio PASSTHRU (1/4") ──► Imenso X74 (line / AUX in)

Wireless Mic 1 ─► Imenso (built-in receiver)
Wireless Mic 2 ─► Imenso (built-in receiver)
                      │
                      ▼
                Imenso X74 — final speaker (200 W)
```

## Channel Assignments

| Source | Connector / Channel | Notes |
|---|---|---|
| **Guitar** | Trio **CH3** (dedicated Hi-Z) | Keeps the editable 8-module guitar effect chain available |
| **Keyboard** | Trio **CH2** (combo, slider → line) | Line-level (370 mV rms input sensitivity) |
| **Electronic drums** | Trio **CH1** (combo, line) | L/Mono out from drum module, summed to mono |
| **Streamed song** | Trio **CH4 / Bluetooth** | Free for Stem AI — no other CH4 source competing |
| **Vocal mic 1** | **Imenso wireless** | Frees Trio channels, no cable |
| **Vocal mic 2** | **Imenso wireless** | Second singer / duets |
| **Master mix to PA** | **Trio PASSTHRU → Imenso line in** | Imenso is the loud speaker |

## Why Each Choice

- **Keyboard on CH2, not CH4 AUX:** CH4 is a 3-in-1 channel (Bluetooth → AUX → USB-C, single-source priority). Putting the keyboard on AUX would block the streamed song. CH2's combo jack is purpose-built for line-level instruments.
- **Drums on CH1, not CH4:** Same reason — CH4 must stay free for the song so STEM AI has something to separate.
- **Guitar on CH3:** Dedicated Hi-Z input, plus access to amp/cab/effect modules without occupying CH1/CH2.
- **Song on CH4 Bluetooth:** Highest priority of CH4's three sub-inputs; cleanest path to STEM AI.
- **Vocals on Imenso wireless mics:** Trio has no built-in mic and only 4 channels; Imenso's 2 wireless mics keep singers cable-free and don't consume Trio channels.
- **Trio → Imenso via PASSTHRU:** Imenso is louder (200 W vs 135 W) and adds the vocal mic mix on top.

## STEM AI Plan

The Trio runs real-time on-device AI separation on the streamed song (CH4):

1. Press **STEM AI** on the Trio.
2. Configure Track Settings (in JBL One app) to expose **Drum**, **Vocal**, **Guitar**, **Others** stems.
3. **Mute the Drum stem** → e-drum player provides the drums live.
4. **Mute the Guitar stem** → guitar player covers the guitar part.
5. Keep **Vocal** audible if no one is singing yet, mute it if a singer takes lead.
6. **Others** stem (keys, bass, strings, etc.) stays audible — keyboard player layers over the original keys, or mute Others too if the keyboard wants to be the sole keys voice.

Modes:
- **Multi-stem separation:** ~2 s latency — best for free-form practice.
- **Karaoke mode:** ~500 ms latency — best for synchronized sing-along.

## Step-by-Step Setup

1. **Power up the Trio** on AC. Power up the **Imenso X74** on its battery or AC.
2. **Plug instruments into the Trio**:
   - Guitar → CH3
   - Keyboard L/Mono out → CH2 (slider on line)
   - E-drum module L/Mono out → CH1 (slider on line)
3. **Pair the phone to the Trio** over Bluetooth → CH4. Start the song.
4. **Press STEM AI** on the Trio. Mute Drum + Guitar stems (and others as desired).
5. **Connect Trio PASSTHRU → Imenso line/AUX input** with a 1/4" TRS cable (use a 1/4" → 3.5 mm adapter if Imenso's input is 3.5 mm).
6. **Turn on the Imenso wireless mics**, hand them to the singer(s).
7. **Balance levels**:
   - On the **Trio mixer screen**: set CH1, CH2, CH3, CH4 individually. Keep the clipping LED green.
   - On the **Imenso master**: set overall room volume + vocal mic level.
8. **Play.**

## What Plays Through What

| What you hear | Comes from |
|---|---|
| Guitar (with amp/cab modeling) | Trio → PASSTHRU → Imenso |
| Keyboard | Trio → PASSTHRU → Imenso |
| Electronic drums | Trio → PASSTHRU → Imenso |
| Streamed song (with stems muted) | Trio → STEM AI → PASSTHRU → Imenso |
| Vocals | Imenso wireless mics → Imenso (direct) |

## Tips & Gotchas

- **Single source on CH4 at a time** — Bluetooth has priority over AUX/USB-C. Disable Bluetooth on the phone if you ever want to use AUX/USB-C instead.
- **STEM AI needs CH4 in music mode**, not "Inst" — only relevant if using AUX with a wired source.
- **Feedback control**: keep wireless mics in front of the Imenso speaker, not behind. Roll off mic gain first if it howls.
- **Double song output**: don't also stream the song to the Imenso over Bluetooth — only the Trio should hold the song so STEM AI works and you avoid an echo.
- **Trio internal speaker**: keep it at low volume since the Imenso is now the room PA. The Trio's speaker can serve as a close-range monitor for the instrument players if needed.
- **Bass guitar option**: if anyone wants to play bass instead of/alongside guitar, the Trio supports it on CH3 with bass amp/cab models (Bass Amp, Studio Bass, M Bass 2×10, A Bass 8×10).
- **Cable not included** for PASSTHRU → Imenso. Need a 1/4" TRS-to-TRS (or 1/4" TRS → 3.5 mm) cable.

## Maximum Simultaneous Sources

- Trio: up to **4 channels live** (CH1 + CH2 + CH3 + one CH4 sub-source)
- Imenso: + **2 wireless vocal mics**
- **Total live performers supported: up to 6 inputs** mixed into one room PA.

## Quick Reference Card

```
TRIO:
  CH1 = E-drums (line)
  CH2 = Keyboard (line)
  CH3 = Guitar (Hi-Z)
  CH4 = Phone via Bluetooth → STEM AI

  STEM AI: mute Drum, mute Guitar, keep Vocal/Others as preferred

  PASSTHRU OUT → IMENSO LINE IN

IMENSO:
  Mic 1 = Singer A
  Mic 2 = Singer B
  Master volume = room level
```
