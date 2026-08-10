#!/usr/bin/env python3
"""Project layout. Every other script imports PROJ from here.

A project is any directory containing `raw/` with the source recordings:

    <project>/
      raw/            source .mov / .mp4 (untouched)
      clips/          <name>_final.mp4  <- deliverables
      edit/           everything derived (transcripts, EDLs, caption frames, scripts)

Point at it with $SHORTS_PROJECT, or pass --project, or run from inside it.
"""
import os
import sys
from pathlib import Path


def project() -> Path:
    for i, a in enumerate(sys.argv):
        if a == "--project" and i + 1 < len(sys.argv):
            return Path(sys.argv[i + 1]).expanduser()
    env = os.environ.get("SHORTS_PROJECT")
    if env:
        return Path(env).expanduser()
    cwd = Path.cwd()
    for c in (cwd, *cwd.parents):
        if (c / "raw").is_dir():
            return c
    raise SystemExit(
        "No project found. Set SHORTS_PROJECT=/path/to/project, pass --project <dir>, "
        "or run from a directory containing raw/."
    )


PROJ = project()
RAW = PROJ / "raw"
CLIPS = PROJ / "clips"
EDIT = PROJ / "edit"
TRANSCRIPTS = EDIT / "transcripts"
WORDS = EDIT / "words"
PARTS = EDIT / "edl_parts"
TIGHT = EDIT / "edl_parts_tight"
WORK = EDIT / "caption_work"

FPS = 30

# Mastering resolution (2026-07-19, "editor-level quality" pass). The OBS source is
# 360x640 at ~246 kbps — that ceiling is unavoidable for the VIDEO, but it must not be
# the ceiling for the type. Rendering overlays at source resolution meant every caption,
# card and panel was a ~360px raster that LinkedIn then upscaled 3x into mush. Now the
# video is upscaled ONCE (lanczos, inside the single encode) and all overlays are
# rasterized natively at 1080x1920 — sharp vector-grade type over an honest upscale,
# which is exactly what a desktop editor ships. Layout code everywhere keeps thinking in
# 360x640 "logical px"; S is the only bridge. (Fix the OBS canvas and S becomes 1.)
OUT_W, OUT_H = 1080, 1920
S = OUT_W // 360   # logical -> output multiplier (3)
