#!/usr/bin/env python3
"""Draw one caption word to a transparent PNG.

Default look (chosen by ear/eye on the reference session): Helvetica Neue Medium,
lowercase, 18px, tracking -1, white, NO stroke, NO box, NO shadow. Bare type.

Why PIL and not ffmpeg: many ffmpeg builds (including Homebrew's slim one) ship WITHOUT
libass and libfreetype, so `subtitles`, `ass` and `drawtext` do not exist at all. PIL is
also the only way to honour negative letter-spacing — `drawtext` has no letter-spacing
option — so we draw glyph by glyph and control the advance ourselves.

Sizes are in SOURCE pixels. On a 360x640 frame, 10px is illegible and -2 tracking makes
letters physically collide; 18px is about the floor that still reads.
"""
from PIL import Image, ImageDraw, ImageFont

from assets import FONT_PATH, REGULAR, BOLD, MEDIUM   # face indices inside the .ttc

SIZE = 18
TRACKING = -1.0
FACE = MEDIUM
Y_FRAC = 0.78                              # 0 = top, 1 = bottom
FILL = (255, 255, 255, 242)
SHADOW = None                              # set e.g. (0,0,0,90) if the plate is bright
SHADOW_OFF = 1
MAX_W_FRAC = 0.85                          # shrink a word that would touch the edges


def load(size, face=FACE):
    return ImageFont.truetype(FONT_PATH, size, index=face)


def measure(font, text, tracking):
    if not text:
        return 0.0
    return sum(font.getlength(c) + tracking for c in text) - tracking


def draw_word(text, w=360, h=640, size=SIZE, tracking=TRACKING, y_frac=Y_FRAC,
              face=FACE, fill=FILL, shadow=SHADOW, shadow_off=SHADOW_OFF,
              upper=False, max_w_frac=MAX_W_FRAC):
    # Callers stay in logical 360x640 units; the raster is produced at OUT (1080x1920)
    # so the type is native-resolution sharp instead of platform-upscaled. See paths.S.
    from paths import S
    w, h, size = w * S, h * S, size * S
    tracking, shadow_off = tracking * S, shadow_off * S
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    if not text:
        return img
    text = text.upper() if upper else text.lower()

    font = load(size, face)
    cap = w * max_w_frac
    while size > 6 and measure(font, text, tracking) > cap:
        size -= 1
        font = load(size, face)

    d = ImageDraw.Draw(img)
    x0 = (w - measure(font, text, tracking)) / 2.0
    y = h * y_frac

    for pass_ in ("shadow", "fill"):
        if pass_ == "shadow" and not shadow:
            continue
        off = shadow_off if pass_ == "shadow" else 0
        col = shadow if pass_ == "shadow" else fill
        x = x0 + off
        for ch in text:
            d.text((x, y + off), ch, font=font, fill=col, anchor="ls")
            x += font.getlength(ch) + tracking
    return img
