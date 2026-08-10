---
name: shorts-audio
description: Clean the audio on a talking-head recording without making it sound processed — constant-gain loudness, rumble removal, and when (not) to denoise. Use when recording audio sounds weird, artificial, pumping, quiet, or noisy, or when asked to denoise or normalize a video's audio.
---

# shorts-audio

Stage 2 of shorts-edit. **Two traps, both silent, both cost hours.**

Quiet recordings cause both. The reference takes sat at **−43 LUFS** and needed **+26 dB**.

---

## TRAP A: `loudnorm` silently pumps

`loudnorm` with `linear=true` promises a single constant gain.

**It abandons that promise without warning** whenever the required gain would push the true
peak past the ceiling — which +26 dB always does. It falls back to *dynamic* mode: per-frame
gain riding. Pumping, breathing, a squashed unnatural tone.

**This — not the denoiser — was the actual cause of "the audio sounds artificial".**
Removing the denoiser alone did not fix it, which is exactly why it cost so much time.

**Fix: never use `loudnorm` for gain.** Measure the true peak, apply ONE constant
`volume=XdB` that lands it at −1.5 dBTP, and accept whatever LUFS falls out.

Verified pure: **correlation 0.999975** with the source waveform, residual 43 dB down (just
AAC noise), no limiter ever engaged. Mathematically, the output is the input times a number.

---

## TRAP B: every denoiser reconstructs the voice, and you can hear it

`afftdn` with `tn=1` (blind tracking) *guesses* the noise spectrum moment to moment.
Guessing wrong is precisely what makes musical burbling.

Learning the profile from real silence in the take is **far** better — `asendcmd … sn
start/stop` around the longest silence:

| chain | noise reduction | speech level |
|---|---|---|
| highpass 60Hz only | 11.2 dB | −0.1 dB |
| RNNoise (arnndn) | 17.6 dB | −0.1 dB |
| **learned print, nr=12** | **23.0 dB** | **−0.1 dB** |

**And it still didn't ship.** On headphones, every spectral denoiser — blind, learned, even
a 50/50 wet/dry blend — was audible as an unnatural tone, because they all *reconstruct* the
signal rather than merely attenuating it. The user listened to all of them and chose the
honest one.

> **SHIPPED: no denoiser. `highpass=f=60` + a constant gain. Nothing else.**

If a genuinely noisy take needs help, `print12@50` (a 50% blend) was the best compromise.

---

## Two ordering rules that silently defeat the filters

1. **The denoiser must run BEFORE the trims.** Its `asendcmd` timestamps point at silence
   in the ORIGINAL take, and the edit throws that silence away. Applied after the cut, the
   sample window falls outside the clip, the command never fires, and afftdn **quietly
   reverts to blind mode** — the exact thing that sounded fake. The floor betrays it:
   −54 dB (blind) vs −64.8 dB (learned).

2. **Gain must precede ANY denoiser.** RNNoise is trained on speech at normal levels. Fed
   −68 dBFS audio it sees silence and does **literally nothing** (measured: 0 dB of extra
   reduction). Gain it first and the same filter removes 23 dB.

---

## What did NOT work

- **A noise gate.** Intuitive — mute the gaps — and useless: after the edit the cut is
  **96% speech**. There are no gaps left to gate. The audible noise is *under* the voice.
- **Notch filters.** The noise looked like 60Hz mains harmonics at coarse FFT resolution.
  At fine resolution it isn't: **69% of the voice-band noise is broadband** room tone.
  Notching mangled the voice (correlation 0.77) to buy 3 dB.

## The mono-SFX clipping trap

`amix` negotiates a common channel layout. A **mono** SFX bed makes it pick mono, which
silently downmixes the stereo voice — and that downmix pushed the peak from −1.62 dB to
**+0.83 dB (clipping)**. Pin `aformat=channel_layouts=stereo` on **both** sides of the mix.

## Known tradeoff: the clips are quiet (−18 to −23 LUFS)

Peak-normalizing with **no limiting and no compression** lands below the −14/−16 social
norm. That is the honest ceiling for zero dynamics processing; getting louder means
compressing, which is what was rejected. Platforms normalize on playback.

The real fix is at the source: **raise the input gain when recording.**
