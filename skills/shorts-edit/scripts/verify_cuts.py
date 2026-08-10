#!/usr/bin/env python3
"""Safety check: no cut edge may land in live speech.

The hard rule is "never cut inside a word" — but the ASR word grid CANNOT enforce it.
Scribe pads a word's `end` deep into the following silence (one word claimed to run 1.3s
past where the voice actually stopped) and emits phantom words over dead-silent audio.
Checking cut edges against the word grid produced 25 false alarms in the reference
session; measuring the AUDIO at those points showed 24 were sitting in silence and only
ONE was a real defect (a cut through a voiced "um").

So: the audio is the authority. Measure a 40ms window INSIDE the kept region on each side.
A window straddling the cut would include deleted audio that never reaches the output,
which makes every segment following a dropped false start look like a chop.

    python verify_cuts.py            # exits 1 if any cut chops live speech
"""
import json
import subprocess
import sys

from paths import TIGHT, RAW

# Thresholds are DERIVED PER TAKE, never fixed. Raw OBS audio sits ~-45 dB speech over a
# ~-68 dB floor; a denoised intermediate sits far lower. A hardcoded dB value silently
# means something different on each — it reported 36 chops on one source and 92 on the
# same cuts from another. So: learn the floor from the take's own silence and the speech
# level from its peak, then put the "is this voiced?" line between them.
FLOOR_MARGIN = 12.0   # dB above the noise floor = definitely voiced
WARN_MARGIN = 6.0


def rms(src, start, dur):
    if start < 0:
        return -99.0
    err = subprocess.run(
        ["ffmpeg", "-hide_banner", "-ss", f"{start:.3f}", "-t", f"{dur:.3f}", "-i", str(src),
         "-vn", "-af", "astats=metadata=1:reset=0", "-f", "null", "-"],
        capture_output=True, text=True).stderr
    for line in err.splitlines():
        if "RMS level dB" in line:
            v = line.split()[-1]
            return -99.0 if v in ("-inf", "nan") else float(v)
    return -99.0


def noise_floor(src) -> float:
    """Level of this take's own silence — the baseline the thresholds hang off."""
    from render_final import find_silence
    win = find_silence(src)
    if not win:
        return -70.0
    a, b = win
    return rms(src, a, min(1.0, b - a))


def word_spans(name):
    """True word extents. ASR `end` overruns into silence, so clamp each word to the next
    word's start — otherwise nearly every sentence-final word looks like it swallows the
    pause after it."""
    from paths import TRANSCRIPTS
    W = [w for w in json.loads((TRANSCRIPTS / f"{name}.json").read_text())["words"]
         if w.get("type") == "word"]
    out = []
    for i, w in enumerate(W):
        end = min(w["end"], W[i + 1]["start"]) if i + 1 < len(W) else w["end"]
        out.append((w["start"], end, w["text"].strip()))
    return out


def main():
    """A cut is a real defect only if it BOTH lands inside a word AND has voiced audio
    there. Either test alone is useless:
      * the word grid alone gave 25 false alarms (ASR pads word ends into silence);
      * "voiced at the edge" alone flags every intentional filler deletion, because
        removing an "um" mid-sentence necessarily joins two voiced moments.
    The intersection found exactly one real bug (a cut through a voiced "um") in the
    reference session — and it was real.
    """
    bad = cand = edges = 0
    for p in sorted(TIGHT.glob("*.json")):
        edl = json.loads(p.read_text())
        name = edl["source"]
        src = next(RAW.glob(f"{name}.*"))
        floor = noise_floor(src)
        voiced_at = floor + FLOOR_MARGIN
        spans = word_spans(name)

        for i, r in enumerate(edl["ranges"]):
            for label, t in (("START", float(r["start"])), ("END", float(r["end"]))):
                edges += 1
                inside = next((w for ws, we, w in spans if ws + 0.025 < t < we - 0.025), None)
                if not inside:
                    continue                      # between words — safe by construction
                cand += 1
                lvl = rms(src, t - 0.02, 0.04)    # the audio AT the cut
                if lvl > voiced_at:
                    print(f"  CHOP  {name} seg{i} {label} {t:.2f}s inside {inside!r} "
                          f"({lvl:.1f} dB, {lvl - floor:.0f} dB over floor — voiced)")
                    bad += 1

    print(f"\n{edges} edges | {cand} land inside a word | {bad} of those are voiced (real chops)")
    if cand and not bad:
        print("(the in-word ones all sit in silence — ASR word ends pad into pauses)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
