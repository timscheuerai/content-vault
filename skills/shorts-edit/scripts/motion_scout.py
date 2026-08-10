#!/usr/bin/env python3
"""Stage 1 of 3 — find the moments where a motion graphic would actually EARN its place.

A graphic earns its place when the words are doing work a picture does better: a hard
number, an enumeration, a ranking, a named stack. Everywhere else it is decoration, and
decoration on a talking-head short costs you the face, which is the thing carrying it.

So this does not invent graphics. It surfaces CANDIDATES with their time on the finished
timeline, and a human (or the agent) picks and writes the copy into edit/motion.json.

    python motion_scout.py "<clip>"        # candidates for one clip
    python motion_scout.py                 # all clips
"""
import re
import sys

from make_captions import build_events
from paths import TIGHT

NUM = re.compile(r"^\$?\d[\d,.]*(k|m|%|x)?$", re.I)
WORD_NUM = {"zero", "one", "two", "three", "four", "five", "six", "seven", "eight",
            "nine", "ten", "hundred", "thousand", "million"}
ORDINAL = re.compile(r"\b(first|second|third|fourth|fifth|next|final|last)\b", re.I)
STEP = re.compile(r"\bstep (number )?(one|two|three|four|five|\d)\b", re.I)
TIER = re.compile(r"\b([sabcdf]) tier\b", re.I)
TOOLS = {"oxygen", "linkedin", "apollo", "clay", "instantly", "claude", "youtube",
         "instagram", "tiktok", "facebook", "x", "hubspot", "paperclip"}


def scan(name, fps=30):
    events, _ = build_events(name)
    words = [w.lower().strip(".,?!") for _, _, w in events]
    starts = [a for a, _, _ in events]
    hits = []

    for i, w in enumerate(words):
        ctx = " ".join(words[max(0, i - 6): i + 7])
        t = starts[i]

        if NUM.match(w) and w not in ("1", "2"):
            hits.append((t, "stat", w, ctx))
        elif STEP.search(" ".join(words[i: i + 3])):
            hits.append((t, "steps", " ".join(words[i: i + 3]), ctx))
        elif i + 1 < len(words) and TIER.search(f"{w} {words[i+1]}"):
            hits.append((t, "tier", f"{w} {words[i+1]}", ctx))
        elif w in TOOLS:
            hits.append((t, "stack", w, ctx))

    # collapse anything landing within 2.5s — one graphic per moment
    out, last = [], -99.0
    for t, kind, tok, ctx in sorted(hits):
        if t - last < 2.5:
            continue
        out.append((t, kind, tok, ctx))
        last = t
    return out


def main():
    names = sys.argv[1:] or [p.stem for p in sorted(TIGHT.glob("*.json"))]
    for n in names:
        rows = scan(n)
        if not rows:
            continue
        print(f"\n=== {n} ===")
        for t, kind, tok, ctx in rows:
            print(f"  {t:6.1f}s  {kind:6}  {tok!r:22} … {ctx[:70]} …")


if __name__ == "__main__":
    main()
