#!/usr/bin/env python3
"""Text BEHIND the subject — the "he's standing in front of the word" look.

Composite order per frame:   video  ->  big text  ->  the person, cut back out on top.

THE CONSTRAINT THAT MAKES THIS WORK IN ONE ENCODE
--------------------------------------------------
The naive way is a second pass: render the cut video, then re-read it, segment, composite,
re-encode. That is a SECOND ENCODE, and a second encode measurably softens the image
(SSIM 0.998 -> 0.977 on an already-compressed source). We fought hard for one encode.

So instead the person is baked into the SAME per-frame RGBA overlay the captions use. The
overlay carries [text] + [the person's pixels], and ffmpeg composites it over the video.
The person's pixels are read from the RAW SOURCE — the exact frames ffmpeg is decoding —
so the cutout lands on top of itself and there is no seam.

That only holds if the video underneath is UNTOUCHED. A zoomed chunk is scaled by
zoompan/lanczos inside ffmpeg, and re-deriving that transform in PIL would never match
pixel-for-pixel — you would see a soft double-edge around him. **Therefore any chunk
carrying a behind-text is forced to `wide`.** That is not a limitation to work around; it
is what keeps the effect seamless and the encode single.

COST: ~0.2s/frame to segment. Use it on 2-4 hero moments, not the whole clip.
"""
import os
import subprocess

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from assets import FONT_PATH as FONT, BOLD
W, H = 360, 640

SIZE = 74
FILL = (255, 255, 255, 255)
Y_FRAC = 0.47          # behind the head, not over the mouth
MODEL = "u2netp"       # the small u2net. Plenty at 360x640, and ~5x faster than u2net.

_SESSION = None


def _session():
    global _SESSION
    if _SESSION is None:
        from rembg import new_session
        _SESSION = new_session(MODEL)
    return _SESSION


def cutout(frame: Image.Image) -> Image.Image:
    """The person, background removed."""
    from rembg import remove
    return remove(frame.convert("RGBA"), session=_session())


def source_frame(src, t: float, tmp) -> Image.Image:
    """The RAW frame ffmpeg will decode at this instant — not a re-encode of it."""
    p = tmp / "sf.png"
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", f"{t:.4f}", "-i", str(src),
         "-frames:v", "1", str(p), "-y"], check=True)
    return Image.open(p).convert("RGBA")


def text_layer(text, i, n, size=SIZE, y_frac=Y_FRAC, fill=FILL):
    """The word, scaling in behind him. Big, bare, no stroke — it is furniture, not a caption."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    t = min(max(i / 6, 0.0), 1.0)
    ease = 1 - (1 - t) ** 3
    out = min(max((n - i) / 5, 0.0), 1.0)
    a = int(255 * min(ease, 1 - (1 - out) ** 3))
    if a <= 0:
        return img

    sz = int(size * (0.90 + 0.10 * ease))
    d = ImageDraw.Draw(img)
    # SHRINK TO FIT. A hook word that runs off both edges is not a hook, it is a bug.
    MAX_W = W * 0.90
    f = ImageFont.truetype(FONT, sz, index=BOLD)
    while sz > 20 and d.textlength(text.upper(), font=f) > MAX_W:
        sz -= 2
        f = ImageFont.truetype(FONT, sz, index=BOLD)
    d.text((W // 2, int(H * y_frac)), text.upper(), font=f,
           fill=fill[:3] + (a,), anchor="mm")
    return img


def place(frames_dir, plan, name, chunks, src, tmp, fps=30):
    """plan = [{at_frame, dur_frames, text}] with the OUTPUT frame already resolved."""
    # output frame -> source time, straight off the chunk list
    f2t, off = {}, 0.0
    for c in chunks:
        d = c["end"] - c["start"]
        f0, f1 = round(off * fps), round((off + d) * fps)
        for f in range(f0, f1):
            f2t[f] = c["start"] + (f - f0) / fps
        off += d

    for g in plan:
        f0, n = g["at_frame"], g["dur_frames"]
        for i in range(n):
            f = f0 + i
            p = frames_dir / f"f_{f:06d}.png"
            if not p.exists() or f not in f2t:
                continue
            base = Image.open(p).convert("RGBA")      # captions + board, already drawn
            raw = source_frame(src, f2t[f], tmp)

            # LAYER ORDER IS THE WHOLE TRICK:
            #     video  ->  text  ->  person  ->  captions + board
            #
            # The person must go UNDER the UI, not over it. Compositing him last put his
            # shoulder on top of the tier board and clipped the lanes — he was occluding a
            # user-interface element, which reads as a rendering fault. So the word and the
            # cut-out go down first, and the existing overlay (captions, board) goes back on
            # top of them.
            lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            lay.alpha_composite(text_layer(g["text"], i, n,
                                           size=g.get("size", SIZE)))   # 1. the word, behind him
            lay.alpha_composite(cutout(raw))                   # 2. him, in front of it
            lay.alpha_composite(base)                          # 3. the UI, in front of both

            os.unlink(p)                                        # break the hardlink
            lay.save(p)
