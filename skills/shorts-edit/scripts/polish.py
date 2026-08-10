#!/usr/bin/env python3
"""Optional polish: punch-in zooms, film-burn flashes at scene changes, transition SFX.

Deliberately restrained. On a talking-head short, the job of these is to make the jump
cuts read as INTENTIONAL, not to be noticed themselves. Three rules:

  * Zoom alternates per segment (wide / punched-in). Consecutive cuts land on different
    framings, so a jump cut looks like a two-camera edit instead of a glitch. This is the
    single highest-value trick and it costs nothing.
  * Burns fire only at SCENE CHANGES — a cut where a big chunk of source was removed
    (>= MIN_GAP). A flash on every cut is nausea. Capped per clip.
  * SFX sit under the voice, synced to the burns. If you can hear them as "a sound
    effect", they are too loud.

The burn is composited into the SAME per-frame caption PNGs, so it needs no extra input
and no extra encode. The SFX are rendered to one bed WAV and amixed at weight 1 against
an untouched voice.
"""
import math

import numpy as np
from PIL import Image

from assets import SFX_DIR   # re-exported: qa.py imports it as polish.SFX_DIR

# --- zoom -------------------------------------------------------------------
ZOOM_A = 1.00
ZOOM_B = 1.06          # 6% punch-in. More than ~8% gets soft on a 360px source.
Y_BIAS = 0.35          # crop window sits above centre, so the head keeps its headroom
OVERSAMPLE = 3         # zoompan quantizes its pan to whole INPUT pixels. Feeding it a 3x
                       # frame turns a 1px step into 1/3 of an output pixel, which is the
                       # difference between a smooth drift and visible stair-stepping.

# "wide" BYPASSES the zoom filter completely — the frame reaches the encoder untouched.
#
# An earlier version ran every segment through zoompan for uniformity, including the ones
# at zoom 1.0. It cost real detail: SSIM against the source fell from 0.9983 to 0.9962 on
# segments that were not even being zoomed. The 360->1080->360 round trip is not free.
# The "sharpness pop" that uniformity was meant to prevent is unavoidable anyway — a
# genuinely zoomed segment IS softer, because zooming a 360px source means upscaling it.
# So: keep the un-zoomed frames pristine and accept that the punched-in ones are softer.
#   0: hold wide (untouched)   1: drift in   2: hold close   3: drift out
ZOOM_CYCLE = ("wide", "in", "close", "out")

# --- burn -------------------------------------------------------------------
BURN_FRAMES = 5        # ~165ms. Short.
BURN_MIN_GAP = 3.0     # only cuts that removed >= this much source count as a scene change
BURN_MAX = 3           # per clip
BURN_PEAK = 0.92       # FULL-FRAME flash. The trick is not the level, it is the ENVELOPE:
                       # one hot frame with a fast decay reads as light. The same level
                       # held across 6 frames reads as fog, which is what v1 got wrong.
BURN_ENV = (0.30, 1.00, 0.62, 0.30, 0.10)   # per-frame, hard attack, fast decay

# --- sfx --------------------------------------------------------------------
SFX_PEAK_DB = -20.0    # whoosh, under the voice (which peaks at -1.5)
CLICK_PEAK_DB = -17.0  # the snap on the cut. If you hear it AS a sound effect, too loud.
RISER_PEAK_DB = -19.0  # the hook riser
SR = 48000

# SFX_DIR (imported above) is an optional designed kit — whoosh/impact/riser as .mp3.
# Ours is ElevenLabs-designed and lives in our brand repo; point SHORTS_SFX_DIR at yours.
# The synthesised fallbacks below still work and measure clean, but a designed sound
# reads as produced rather than approximated.


def load_sfx(name, peak_db):
    """Load a brand SFX and normalise it to `peak_db`. Returns None if the kit is absent,
    so the synthesised path stays as a fallback."""
    f = SFX_DIR / f"{name}.mp3"
    if not f.exists():
        return None
    import subprocess, io, wave
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(f), "-ac", "1", "-ar", str(SR),
         "-f", "wav", "-"], capture_output=True).stdout
    w = wave.open(io.BytesIO(raw))
    x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float64) / 32768.
    if not len(x):
        return None
    x = x / (np.abs(x).max() + 1e-9) * (10 ** (peak_db / 20))
    n = min(240, len(x) // 4)                       # 5ms in/out — never a click of its own
    x[:n] *= np.linspace(0, 1, n)
    x[-n:] *= np.linspace(1, 0, n)
    return x


def zooms_for(ranges):
    """One move per segment, cycling hold-wide / drift-in / hold-close / drift-out."""
    return [ZOOM_CYCLE[i % len(ZOOM_CYCLE)] for i in range(len(ranges))]


def zoom_filter(mode, n_frames, w=360, h=640, fps=30):
    """Smooth Ken-Burns move via zoompan on an oversampled frame.

    `mode` is one of wide / in / close / out. `n_frames` is this segment's length, so the
    drift always completes exactly across the segment rather than running at a fixed rate.
    """
    if mode == "wide":
        return ""          # untouched — no resample, no loss. See ZOOM_CYCLE note.

    n = max(int(n_frames), 2)
    if mode == "in":
        z = f"{ZOOM_A}+{ZOOM_B - ZOOM_A:.4f}*min(on/{n - 1},1)"
    elif mode == "out":
        z = f"{ZOOM_B}-{ZOOM_B - ZOOM_A:.4f}*min(on/{n - 1},1)"
    else:                  # close
        z = f"{ZOOM_B}"

    # Oversampling exists to defeat zoompan's whole-input-pixel pan quantization. At a
    # 1080p target the quantum is already 1/1080 — sub-visible — and 3x would mean an
    # 18-megapixel intermediate per frame for nothing.
    os_ = OVERSAMPLE if w <= 540 else 1
    ow, oh = w * os_, h * os_
    return (f"scale={ow}:{oh}:flags=lanczos,"
            f"zoompan=z='{z}':x='(iw-iw/zoom)/2':y='(ih-ih/zoom)*{Y_BIAS}':"
            f"d=1:s={w}x{h}:fps={fps}")


def scene_changes(ranges, fps=30):
    """Output frame indices of cuts that removed a big chunk of source."""
    out, off = [], 0.0
    for i in range(len(ranges) - 1):
        s, e = float(ranges[i]["start"]), float(ranges[i]["end"])
        off += e - s
        gap = float(ranges[i + 1]["start"]) - e
        if gap >= BURN_MIN_GAP:
            out.append((round(off * fps), gap))
    out.sort(key=lambda x: -x[1])           # biggest jumps first
    return sorted(f for f, _ in out[:BURN_MAX])


def burn_layer(i: int, w=None, h=None, seed=0) -> Image.Image:
    """One frame of a FULL-SCREEN film burn. `i` is the frame index within the burn.

    Covers the whole frame. What stops it reading as fog is the envelope: one hot frame,
    then a fast decay. The hot spot drifts and the grain reseeds each frame so it moves
    like light rather than sitting there like a filter.
    """
    from paths import OUT_W, OUT_H
    w, h = w or OUT_W, h or OUT_H
    env = BURN_ENV[min(i, len(BURN_ENV) - 1)]
    t = i / max(len(BURN_ENV) - 1, 1)
    rng = np.random.default_rng(seed)

    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    # broad hot core, drifting — modulates the wash, never gates it
    cx, cy = w * (0.30 + 0.40 * t), h * (0.40 + 0.10 * t)
    r = np.sqrt(((xx - cx) / (w * 1.15)) ** 2 + ((yy - cy) / (h * 0.95)) ** 2)
    core = np.clip(1.0 - r, 0, 1) ** 1.3

    grain = rng.normal(0, 0.05, (h, w)).astype(np.float32)
    wash = np.clip(0.62 + 0.38 * core + grain, 0, 1)     # >0 everywhere: full screen
    a = np.clip(wash * env * BURN_PEAK, 0, 1)

    img = np.zeros((h, w, 4), dtype=np.float32)
    # white-hot centre bleeding to deep orange at the edges
    img[..., 0] = 255 * 1.00
    img[..., 1] = 255 * (0.58 + 0.36 * core)
    img[..., 2] = 255 * (0.20 + 0.55 * core ** 2)
    img[..., 3] = 255 * a
    return Image.fromarray(img.astype(np.uint8), "RGBA")


def apply_burns(frames_dir, burn_frames, w=None, h=None):
    """Composite burns into the existing per-frame caption PNGs (hardlinked -> must break
    the link before writing, or every frame sharing that PNG changes)."""
    import os
    for k, f0 in enumerate(burn_frames):
        for i in range(BURN_FRAMES):
            fi = f0 + i - 1               # one frame of pre-flash, then the cut, then decay
            p = frames_dir / f"f_{fi:06d}.png"
            if not p.exists():
                continue
            base = Image.open(p).convert("RGBA")
            base.alpha_composite(burn_layer(i, w, h, seed=k * 17 + i))
            os.unlink(p)                       # break the hardlink first
            base.save(p)


def whoosh(dur=0.42, seed=0) -> np.ndarray:
    """Short airy transition. Filtered noise, swept, with a soft tail. Not a 'swoosh'
    stock sample — just air moving."""
    rng = np.random.default_rng(seed)
    n = int(dur * SR)
    t = np.arange(n) / SR
    x = rng.normal(0, 1, n)

    # sweep a one-pole lowpass upward then down: gives the 'passing air' shape
    env_f = 900 + 4200 * np.sin(np.pi * t / dur) ** 1.5
    y = np.zeros(n)
    prev = 0.0
    for i in range(n):
        a = np.exp(-2 * np.pi * env_f[i] / SR)
        prev = a * prev + (1 - a) * x[i]
        y[i] = prev

    amp = np.sin(np.pi * t / dur) ** 2.2       # soft in, soft out — no click
    y *= amp
    y /= (np.abs(y).max() + 1e-9)
    return y * (10 ** (SFX_PEAK_DB / 20))


def click(seed=0) -> np.ndarray:
    """A short mechanical snap on the cut — shutter-ish, not a pop.

    A raw impulse IS a click, but it also reads as a defect. Give it a tiny body (a
    bandpassed noise burst with a fast exponential decay) and it reads as a deliberate
    sound instead of a glitch.
    """
    rng = np.random.default_rng(100 + seed)
    n = int(0.018 * SR)                       # 18ms
    t = np.arange(n) / SR
    x = rng.normal(0, 1, n)

    # crude bandpass 1.5-5kHz: difference of two one-pole lowpasses
    def lp(sig, f):
        a = np.exp(-2 * np.pi * f / SR)
        y = np.zeros_like(sig)
        prev = 0.0
        for i in range(len(sig)):
            prev = a * prev + (1 - a) * sig[i]
            y[i] = prev
        return y

    body = lp(x, 5000) - lp(x, 1500)
    body *= np.exp(-t * 320)                  # fast decay -> snap, not a thud
    body[:8] *= np.linspace(0, 1, 8)          # 0.2ms fade-in: no DC step, no true "pop"
    body /= (np.abs(body).max() + 1e-9)
    return body * (10 ** (CLICK_PEAK_DB / 20))


def _mix(bed, x, at_s):
    if x is None:
        return
    s = max(0, int(at_s * SR))
    e = min(len(bed), s + len(x))
    if e > s:
        bed[s:e] += x[: e - s]


def sfx_bed(total_s: float, burn_frames, fps=30, hook_at=None) -> np.ndarray:
    """Brand SFX where available, synthesised fallbacks otherwise.

    whoosh leads INTO the cut; impact lands ON it. A riser under the hook resolves into
    the board reveal — that resolution is what makes an opener feel designed rather than
    merely loud.
    """
    bed = np.zeros(int(total_s * SR) + SR, dtype=np.float64)

    W = load_sfx("whoosh", SFX_PEAK_DB)
    I = load_sfx("impact", CLICK_PEAK_DB)
    R = load_sfx("riser", RISER_PEAK_DB)

    if hook_at is not None and R is not None:
        _mix(bed, R, max(0.0, hook_at - len(R) / SR + 0.10))   # riser LANDS on the reveal
        _mix(bed, I, hook_at)

    for k, f0 in enumerate(burn_frames):
        cut = f0 / fps
        w = W if W is not None else whoosh(seed=k)
        _mix(bed, w, max(0.0, cut - len(w) / SR + 0.06))       # arrives at the cut
        _mix(bed, I if I is not None else click(seed=k), cut)

    return np.clip(bed, -1, 1)


# --------------------------------------------------------------- pattern interrupts

MAX_HOLD = 4.8     # the 2026 "5-second rule": no block may go >5s with nothing changing.
                   # Beats here run 11-17s, so the cuts alone leave 91% of the clip dead.


def plan_chunks(ranges, max_hold=MAX_HOLD, fps=30):
    """Split long beats into render chunks with ALTERNATING framing.

    The audio is untouched and continuous — this is not a cut. It is a snap change of
    framing partway through a long beat, which reads as a second camera and resets the
    viewer's attention. That is the cheapest pattern interrupt there is.

    Chunk = (start, end, zoom_mode, fade_in, fade_out). Only REAL cuts get the 30ms audio
    fades; a zoom split must NOT fade, or you get an audible dip mid-sentence.
    """
    chunks = []
    for r in ranges:
        s, e = float(r["start"]), float(r["end"])
        d = e - s
        # ceil, not floor+fudge: floor leaves a remainder that can still exceed the hold
        # (an 11.4s beat split in 2 gives 5.7s chunks, which is still a >5s dead block).
        n = max(1, math.ceil(d / max_hold))
        step = d / n
        for k in range(n):
            cs = s + k * step
            ce = s + (k + 1) * step if k < n - 1 else e
            chunks.append({
                "start": cs, "end": ce,
                "zoom": ZOOM_CYCLE[len(chunks) % len(ZOOM_CYCLE)],
                "fade_in": k == 0,          # only the real cut edges fade
                "fade_out": k == n - 1,
            })
    return chunks


def leak_report(chunks, graphics_t, total, fps=30):
    """How much of the clip still has nothing changing for >5s?"""
    ev = [0.0]
    off = 0.0
    for c in chunks:
        off += c["end"] - c["start"]
        ev.append(off)
    ev += list(graphics_t)
    ev = sorted(set(round(t, 2) for t in ev if t <= total))
    leaks, prev = [], 0.0
    for t in ev:
        if t - prev > 5.0:
            leaks.append((prev, t))
        prev = t
    if total - prev > 5.0:
        leaks.append((prev, total))
    return leaks, sum(b - a for a, b in leaks)
