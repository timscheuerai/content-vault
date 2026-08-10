#!/usr/bin/env python3
"""The classic tier-list board — persistent and CUMULATIVE.

This is a different shape from the other primitives. Instead of eight separate panels that
appear and vanish, there is ONE board that builds: the hook shows it complete but BLURRED
(the payoff is teased, not given), and then each verdict drops its channel onto the right
row as he says it. By the end the viewer has watched the board fill in.

That is what makes a tier-list video work — the board is the content, not decoration.

The renderer computes the cumulative state itself. The plan lists the verdicts in order;
at verdict k the board shows verdicts 0..k, with k popping in.
"""
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from assets import FONT_PATH as FONT, REGULAR, BOLD, MEDIUM

W, H = 360, 640
# NOT YET PORTED to the 1080x1920 mastering pass (paths.OUT_W/S, 2026-07-19): this module
# still rasterizes at 360x640, so compositing it onto OUT-sized caption frames raises a
# size mismatch — loudly, not silently. Port it like motion.py (_SD scaled draw) before
# rebuilding any tierboard clip (e.g. 15-06-06).

# tiermaker's palette, as given
ROW_COLOURS = {
    "S": (255, 127, 127), "A": (255, 191, 127), "B": (255, 255, 127),
    "C": (127, 255, 127), "D": (127, 191, 255), "E": (127, 127, 255),
    "F": (255, 127, 255),
}
ROWS = ("S", "A", "B", "C", "D", "E", "F")

BOARD_BG = (12, 12, 12)
ROW_BG = (26, 26, 26)
GRID = (58, 58, 58)
CHIP_BG = (244, 244, 245)
CHIP_INK = (10, 10, 10)

PADX = 12
ROW_H = 30          # smaller board — it was eating half the frame
LABEL_W = 32
CHIP_FONT = 11     # the channel names read as titles, so give them the weight
GAP = 2


def _f(sz, face=BOLD):
    return ImageFont.truetype(FONT, sz, index=face)


def board(items, pop=None, pop_t=1.0, row_h=ROW_H, blur=0.0):
    """Render the board.

    items  : {"S": ["LinkedIn content"], "B": ["Cold email", ...], ...}
    pop    : (grade, label) of the chip currently landing — it scales + fades in
    blur   : gaussian radius applied to the CONTENT lanes only. The row letters stay sharp,
             so the hook reads as "here are the tiers, the answers are hidden".
    """
    bw = W - 2 * PADX
    bh = len(ROWS) * (row_h + GAP) + GAP
    img = Image.new("RGBA", (bw, bh), BOARD_BG + (255,))
    d = ImageDraw.Draw(img)

    lanes = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
    ld = ImageDraw.Draw(lanes)

    for r, g in enumerate(ROWS):
        y = GAP + r * (row_h + GAP)
        # the coloured letter cell
        d.rectangle([GAP, y, GAP + LABEL_W, y + row_h], fill=ROW_COLOURS[g] + (255,))
        d.text((GAP + LABEL_W // 2, y + row_h // 2), g, font=_f(13, BOLD),
               fill=(20, 20, 20, 255), anchor="mm")
        # the lane
        lx0 = GAP + LABEL_W + GAP
        d.rectangle([lx0, y, bw - GAP, y + row_h], fill=ROW_BG + (255,), outline=GRID + (255,))

        # chips go on their own layer so only THEY get blurred
        x = lx0 + 6
        for lab in items.get(g, []):
            cf = _f(CHIP_FONT, BOLD)
            tw = ld.textlength(lab, font=cf)
            cw = int(tw) + 14
            if x + cw > bw - GAP - 4:
                break                                  # lane is full; don't overflow
            is_pop = pop and pop == (g, lab)
            t = pop_t if is_pop else 1.0
            s = 0.82 + 0.18 * t                        # the new chip scales in
            ch = int(22 * s)
            cwp = int(cw * s)
            cy = y + (row_h - ch) // 2
            ld.rounded_rectangle([x, cy, x + cwp, cy + ch], radius=5,
                                 fill=CHIP_BG + (int(255 * t),))
            ld.text((x + cwp // 2, cy + ch // 2), lab, font=cf,
                    fill=CHIP_INK + (int(255 * t),), anchor="mm")
            x += cw + 5

    if blur > 0:
        lanes = lanes.filter(ImageFilter.GaussianBlur(blur))
    img.alpha_composite(lanes)
    return img


def cumulative(verdicts, upto):
    """Board state after verdict `upto` (inclusive)."""
    items = {}
    for v in verdicts[: upto + 1]:
        items.setdefault(v["grade"].upper(), []).append(v["label"])
    return items


def full(verdicts):
    return cumulative(verdicts, len(verdicts) - 1)


def _ease(t):
    return 1 - (1 - min(max(t, 0.0), 1.0)) ** 3


def hook_frame(i, n, verdicts, blur=7.0):
    """The hook: the FINISHED board, results blurred. Tease the payoff, don't give it."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    a = int(255 * min(_ease(i / 6), _ease((n - i) / 6)))
    b = board(full(verdicts), row_h=38, blur=blur)
    x = (W - b.width) // 2
    y = (H - b.height) // 2 + int(12 * (1 - _ease(i / 6)))
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    lay.alpha_composite(b, (x, y))
    if a < 255:
        lay.putalpha(lay.getchannel("A").point(lambda v: v * a // 255))
    img.alpha_composite(lay)
    return img


def verdict_frame(i, n, verdicts, idx, payload):
    """One verdict: the cumulative board, with this channel dropping onto its row."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    intro = _ease(i / 6)
    a = int(255 * min(intro, _ease((n - i) / 5)))
    v = verdicts[idx]
    pop_t = _ease((i - payload + 3) / 8)               # the chip lands ON the spoken grade

    b = board(cumulative(verdicts, idx), pop=(v["grade"].upper(), v["label"]), pop_t=pop_t)
    x = (W - b.width) // 2
    y = H - 18 - b.height + int(14 * (1 - intro))
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    lay.alpha_composite(b, (x, y))
    if a < 255:
        lay.putalpha(lay.getchannel("A").point(lambda v_: v_ * a // 255))
    img.alpha_composite(lay)
    return img


# --------------------------------------------------------------------- placement

BOARD_TOP = H - 18 - (len(ROWS) * (ROW_H + GAP) + GAP)    # ~354 with ROW_H=36


def plan_windows(spec, name, fps=30):
    """Resolve cues -> (hook window, board window, per-verdict payload frames).

    The board PERSISTS: once the first channel lands it stays up and accumulates, which is
    what makes the viewer watch it fill. It is not eight separate panels.
    """
    from motion import resolve_cue, LEAD
    lead_f = round(LEAD * fps)

    hook = None
    if spec.get("hook"):
        h = spec["hook"]
        # `at` lets the board reveal be SEQUENCED after a text hook. Running both at once
        # buried the text under the board and produced mush.
        t = float(h["at"]) if "at" in h else resolve_cue(name, h["cue"], fps)
        if t is not None:
            f0 = max(0, round(t * fps))
            hook = (f0, f0 + round(float(h.get("dur", 4.0)) * fps))

    vs, cues = [], []
    for v in spec["verdicts"]:
        t = resolve_cue(name, v["cue"], fps)
        if t is None:
            print(f"    !! cue not found, dropping verdict: {v['cue']!r}")
            continue
        vs.append(v)
        cues.append(round(t * fps))
    return hook, vs, cues, lead_f


def place(frames_dir, spec, name, total_s, fps=30):
    import os
    hook, vs, cues, lead_f = plan_windows(spec, name, fps)
    if not vs:
        return None, None

    if hook:
        for i in range(hook[1] - hook[0]):
            p = frames_dir / f"f_{hook[0] + i:06d}.png"
            if not p.exists():
                continue
            base = Image.open(p).convert("RGBA")
            base.alpha_composite(hook_frame(i, hook[1] - hook[0], vs))
            os.unlink(p)
            base.save(p)

    start = max(0, cues[0] - lead_f)
    end = round(total_s * fps)
    for f in range(start, end):
        p = frames_dir / f"f_{f:06d}.png"
        if not p.exists():
            continue
        idx = 0
        for k, c in enumerate(cues):
            if f >= c - lead_f:
                idx = k
        pop_t = _ease((f - cues[idx] + 3) / 8)
        intro = _ease((f - start) / 6)
        a = int(255 * intro)

        b = board(cumulative(vs, idx), pop=(vs[idx]["grade"].upper(), vs[idx]["label"]),
                  pop_t=pop_t)
        lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        lay.alpha_composite(b, ((W - b.width) // 2, H - 18 - b.height + int(14 * (1 - intro))))
        if a < 255:
            lay.putalpha(lay.getchannel("A").point(lambda v_: v_ * a // 255))

        base = Image.open(p).convert("RGBA")
        base.alpha_composite(lay)
        os.unlink(p)
        base.save(p)

    return hook, (start, end)
