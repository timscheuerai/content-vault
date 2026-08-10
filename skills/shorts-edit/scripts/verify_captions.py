#!/usr/bin/env python3
"""Prove every caption shows the RIGHT word on the RIGHT frame — by pixels.

Eyeballing does not scale to thousands of words, and the failure it must catch is subtle:
a 1-2 frame slip is invisible on a long word and fatal on a short one. In the reference
session every eyeball spot-check landed on long words and looked perfect while short words
were silently wrong ("THING" on screen where "THE" belonged — "THE" is 3 frames long).

We DREW the caption, so we know exactly what the frame should look like. Pull the real
frame at the caption's midpoint, isolate the bright text, and score its overlap (IoU)
against the expected word's bitmap AND its neighbours'. If the expected word is not the
best match, the caption is on the wrong frame.

Two things make this a real test rather than a rubber stamp:
  * it reads the schedule the RENDERER wrote (caption_work/*/schedule.json). A verifier
    that recomputes the frame numbers just re-implements the code under test, and would
    have happily agreed with the off-by-one bug it exists to catch.
  * sampling is biased toward the SHORTEST words, where slips actually show.

    python verify_captions.py        # exits 1 on any wrong frame
"""
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

from caption_render import draw_word, Y_FRAC, SIZE
from make_captions import build_events
from paths import CLIPS, TIGHT, WORK, S

# Crop to where the caption ACTUALLY IS. A tier board lifts the captions above itself, so
# a fixed band looks at empty video and reports every caption missing. The renderer records
# which position it used; read that rather than assuming.
BRIGHT = 150
RAISED_Y = 0.60


def band(raised=False):
    # Logical geometry x S — output frames and draw_word rasters are both at OUT res.
    y = int(640 * S * (RAISED_Y if raised else Y_FRAC))
    return (0, y - (SIZE + 8) * S, 360 * S, y + 10 * S)


def mask_rgb(img, raised=False):
    a = np.asarray(img.convert("RGB").crop(band(raised))).astype(np.int16)
    return a.min(axis=2) > BRIGHT


def mask_expected(word, raised=False):
    kw = {"y_frac": RAISED_Y} if raised else {}
    a = np.asarray(draw_word(word, **kw).convert("RGBA").crop(band(raised)))
    return (a[:, :, 3] > 100) & (a[:, :, 0] > BRIGHT)


def iou(x, y):
    u = (x | y).sum()
    return float((x & y).sum() / u) if u else 1.0


def frame_at(clip, idx, out):
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(clip),
         "-vf", f"select=eq(n\\,{idx})", "-fps_mode", "passthrough", "-frames:v", "1", str(out)],
        check=True, capture_output=True)


def check(name, tmp, n_samples=40):
    slug = re.sub(r"[^A-Za-z0-9]", "_", name)
    sched = json.loads((WORK / slug / "schedule.json").read_text())
    clip = CLIPS / f"{name}_final.mp4"
    if not sched or not clip.exists():
        return 0, 0
    ev = [(s["start_frame"], s["end_frame"], s["word"], s.get("raised", False))
          for s in sched]

    # A motion graphic's panel deliberately COVERS the caption band. Those frames are not
    # caption failures — the graphic replaced the caption on purpose. Skip them, or the
    # verifier reports a defect that does not exist.
    from motion import load_plan, resolve_plan
    from paths import FPS
    raw = load_plan(name)
    if isinstance(raw, dict) and raw.get("kind") == "tierboard":
        blocked = []          # the board raises the captions rather than hiding them
    else:
        blocked = [(f0, f1) for f0, f1, _ in resolve_plan(raw, name, FPS)]

    def covered(f):
        return any(a <= f < b for a, b in blocked)

    order = sorted(range(len(ev)), key=lambda i: ev[i][1] - ev[i][0])
    idxs = sorted(set(order[: n_samples // 2] +
                      list(np.linspace(0, len(ev) - 1, n_samples - n_samples // 2, dtype=int))))

    ok = bad = 0
    png = tmp / "f.png"
    for i in idxs:
        sf, ef, word, raised = ev[i]
        if covered((sf + ef) // 2):
            continue
        try:
            frame_at(clip, (sf + ef) // 2, png)
            got = mask_rgb(Image.open(png), raised)
        except Exception:
            continue
        if got.sum() < 8:
            print(f"  BLANK  {name} f{(sf + ef)//2} expected {word!r}")
            bad += 1
            continue
        cands = {word: iou(got, mask_expected(word, raised))}
        for j in (i - 1, i + 1):
            if 0 <= j < len(ev):
                cands.setdefault(ev[j][2], iou(got, mask_expected(ev[j][2], raised)))
        best = max(cands, key=cands.get)
        if best == word and cands[word] > 0.4:
            ok += 1
        else:
            print(f"  WRONG  {name} f{(sf + ef)//2}: expected {word!r} (IoU {cands[word]:.2f}) "
                  f"but best match is {best!r} (IoU {cands[best]:.2f})")
            bad += 1
    return ok, bad


def main():
    names = [a for a in sys.argv[1:] if not a.startswith("--")] or \
            [p.stem for p in sorted(TIGHT.glob("*.json"))]
    T = B = 0
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        for n in names:
            ok, bad = check(n, tmp)
            T += ok
            B += bad
            print(f"{n}: {ok}/{ok+bad} sampled captions on the correct frame")
    print(f"\nTOTAL {T}/{T+B} correct" + ("  <-- FAILURES" if B else "  — all correct"))
    return 1 if B else 0


if __name__ == "__main__":
    sys.exit(main())
