#!/usr/bin/env python3
"""Word-by-word captions, mapped onto the OUTPUT (cut) timeline, one PNG per frame.

Two things make this non-trivial.

1. The clips are CUT. A word's time in the source is not its time in the finished video:
       output_time = word.start - segment.start + segment_offset
   Words inside deleted regions are dropped — they are not in the video.

2. ASR word END times are fiction. They pad deep into the following silence (Scribe
   claimed a word ran 1.3s past where the voice actually stopped) and can be phantom
   words over dead-silent audio. So the caption OUT point is NEVER word.end: each word is
   held until the NEXT word begins. Word START times are reliable, and that is all
   "aligned with the spoken word" needs.

TRAP — never let ffmpeg derive caption timing from durations. A concat list of images
with `duration` directives drifts: it re-times to CFR on output and rounds boundaries
however it likes. Float durations put the wrong word on screen; durations that were exact
multiples of 1/FPS ALSO failed (a 1-frame word landed a frame late, a 1-frame gap
stretched to two). One PNG per output frame via image2 has no durations to round — file N
IS frame N. Repeated frames are hardlinked, so it costs no disk.
"""
import json
import os
import re
import shutil

from caption_render import draw_word
from paths import TIGHT, TRANSCRIPTS, WORK, FPS, EDIT

MIN_FRAMES = 2      # a 1-frame caption is a 33ms flash the eye cannot read, and it is
                    # fragile to any single-frame slip. Give every word at least two.
MAX_HOLD = 1.4      # never leave one word up longer than this


_FIXES_CACHE = {}


def fixes_raw(name: str) -> dict:
    p = EDIT / "word_fixes.json"
    d = json.loads(p.read_text()) if p.exists() else {}
    return d.get(name, {})


def fixes_for(name: str) -> dict:
    """ASR mishears domain words ("moat" -> "mode"). edit/word_fixes.json corrects the
    CAPTION text only; the audio is never touched. Shape:
        {"global": {"...": "..."}, "<clip name>": {"mode": "moat"}}
    """
    if name in _FIXES_CACHE:
        return _FIXES_CACHE[name]
    p = EDIT / "word_fixes.json"
    d = json.loads(p.read_text()) if p.exists() else {}
    merged = {**d.get("global", {}), **d.get(name, {})}
    _FIXES_CACHE[name] = {k.lower(): v for k, v in merged.items()
                          if not k.startswith("_") and isinstance(v, str)}
    return _FIXES_CACHE[name]


def clean(word: str, name: str = "") -> str:
    """Drop trailing punctuation, then apply this clip's ASR corrections."""
    w = re.sub(r"[,.…]+$", "", word.strip().strip('"\u201c\u201d'))
    return fixes_for(name).get(w.lower(), w) if name else w


def build_events(name: str, edl=None):
    """[(out_start, out_end, word)] on the finished video's timeline."""
    edl = edl or json.loads((TIGHT / f"{name}.json").read_text())
    words = [w for w in json.loads((TRANSCRIPTS / f"{name}.json").read_text())["words"]
             if w.get("type") == "word"]

    # ASR sometimes MERGES a repeated word into one token ("X ... X" -> a single "XX"
    # spanning both). If the edit then drops the first utterance, the surviving one has no
    # caption at all, because the token's start time now sits outside the segment. An
    # insert puts the word back at the time it is actually spoken, in SOURCE time, so it
    # flows through the EDL mapping like any other word.
    for ins in fixes_raw(name).get("_insert", []):
        words.append({"type": "word", "text": ins["word"],
                      "start": float(ins["src_at"]),
                      "end": float(ins["src_at"]) + float(ins.get("dur", 0.25))})
    words.sort(key=lambda w: w["start"])
    events, offset = [], 0.0
    for r in edl["ranges"]:
        s, e = float(r["start"]), float(r["end"])
        seg_len = e - s
        seg = [w for w in words if s <= w["start"] < e]
        for i, w in enumerate(seg):
            txt = clean(w["text"], name)
            if not txt:
                continue
            a = w["start"] - s + offset
            b = (seg[i + 1]["start"] - s + offset) if i + 1 < len(seg) else seg_len + offset
            b = min(b, a + MAX_HOLD)
            if b - a >= 0.05:
                events.append((a, b, txt))
        offset += seg_len
    return events, offset


def caption_frames(name: str, events, total: float, size=None, raise_frames=None,
                   hide_frames=None):
    wd = WORK / re.sub(r"[^A-Za-z0-9]", "_", name)
    frames = wd / "frames"
    if wd.exists():
        shutil.rmtree(wd)
    frames.mkdir(parents=True)

    kw = {} if size is None else {"size": size}
    blank = wd / "blank.png"
    draw_word("", **kw).save(blank)

    # The tier board occupies the lower ~45% of the frame and would swallow the captions.
    # Rather than hide them for 100s, lift them above it for exactly those frames.
    raise_frames = raise_frames or set()
    # A tall glass panel spans the raised row too, so lifting is not enough: the word
    # renders INSIDE the card. For those windows the graphic IS the message.
    hide_frames = hide_frames or set()
    RAISED_Y = 0.60

    total_f = round(total * FPS)
    plan = [blank] * total_f
    schedule, cursor = [], 0
    for i, (a, b, txt) in enumerate(events):
        sf = max(cursor, round(a * FPS))
        ef = min(max(sf + MIN_FRAMES, round(b * FPS)), total_f)
        if sf >= total_f:
            break
        p = wd / f"w{i:04d}.png"
        draw_word(txt, **kw).save(p)
        hi = wd / f"w{i:04d}_hi.png"
        need_hi = any(f in raise_frames for f in range(sf, ef))
        if need_hi:
            draw_word(txt, y_frac=RAISED_Y, **kw).save(hi)
        for f in range(sf, ef):
            if f in hide_frames:
                plan[f] = blank
            else:
                plan[f] = hi if (f in raise_frames and need_hi) else p
        schedule.append({"word": txt, "start_frame": sf, "end_frame": ef,
                         "raised": bool(need_hi)})
        cursor = ef

    for f, src in enumerate(plan):
        os.link(src, frames / f"f_{f:06d}.png")

    (wd / "schedule.json").write_text(json.dumps(schedule, indent=1))
    return frames, schedule
