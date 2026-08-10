#!/usr/bin/env python3
"""Machine-local assets: the font, the SFX kit, the brand token file.

This is the only part of the pipeline that is not portable, so it is the only part you
may need to configure. Each entry has an environment override — never edit a renderer to
change one of these.

    export SHORTS_FONT=/path/to/YourFace.ttc      # the typeface every renderer draws with
    export SHORTS_SFX_DIR=/path/to/sfx            # optional designed whoosh/impact/riser
    export SHORTS_BRAND_MD=/path/to/BRAND.md      # optional colour-token table for the lint

Deliberately imports nothing from `paths` — `paths` resolves a project and exits if there
isn't one, and both the caption renderer and the brand lint must import without a project.
"""
import os
from pathlib import Path

_SKILL = Path(__file__).resolve().parent.parent

# The typeface. The default is the macOS system Helvetica Neue collection — a .ttc, from
# which the renderers select a face by index (see FACE_INDEX). Point SHORTS_FONT at any
# .ttc/.otf/.ttf you have the rights to use; if it is not a collection the index is
# ignored and you get its single face at whatever weight it ships.
FONT_PATH = os.environ.get("SHORTS_FONT", "/System/Library/Fonts/HelveticaNeue.ttc")

# Face indices inside the default Helvetica Neue .ttc. If you swap FONT_PATH for a
# different collection these select different weights — list yours with:
#   python -c "from PIL import ImageFont; import assets; \
#     [print(i, ImageFont.truetype(assets.FONT_PATH,20,index=i).getname()) for i in range(12)]"
REGULAR, BOLD, MEDIUM = 0, 1, 10

# Optional designed SFX kit: whoosh.mp3 / impact.mp3 / riser.mp3. Absent is fine —
# polish.py falls back to synthesised sounds that measure clean. A designed kit just
# reads as produced rather than approximated.
SFX_DIR = Path(os.environ.get("SHORTS_SFX_DIR", _SKILL / "assets" / "sfx")).expanduser()

# Optional BRAND.md carrying a markdown table of colour tokens, in the form
# `| `--token-name` | `#rrggbb` | ...`. brand_lint.py parses it and fails on any drift
# between it and the constants the renderers use. Without it the lint prints the
# constants it found and skips the comparison.
BRAND_MD = Path(os.environ.get("SHORTS_BRAND_MD", _SKILL / "assets" / "BRAND.md")).expanduser()
