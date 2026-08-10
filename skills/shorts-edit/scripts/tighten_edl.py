#!/usr/bin/env python3
"""Pass 2: remove dead air that survives INSIDE a kept take.

Pass 1 (the editor's take-selection) removes the pauses BETWEEN beats. But a speaker
also pauses mid-thought inside a take. In the reference session that was 19.1s across
14 clips, and the ASR transcript claimed it was only 2.5s.

So: find acoustic silence (>= MIN_GAP at -60dB) inside every kept range and split the
range around it, leaving AIR seconds each side. Cutting inside silence can never clip a
word, so this needs no transcript at all — and acoustic silence is the ground truth in a
way ASR word timings are not.

  edl_parts/*.json  ->  edl_parts_tight/*.json   (the tight ones are the source of truth)
"""
import json
import re
import subprocess

from paths import PARTS, TIGHT, RAW

MIN_GAP = 0.60   # only touch silences at least this long
AIR = 0.12       # breathing room left on each side of the cut
MIN_WIN = 0.15   # skip if we'd reclaim less than this
EDGE = 0.05      # silence within this of a range edge is leading/trailing, not internal


def silences(src, start, dur):
    err = subprocess.run(
        ["ffmpeg", "-hide_banner", "-ss", f"{start:.3f}", "-t", f"{dur:.3f}", "-i", str(src),
         "-af", f"silencedetect=noise=-60dB:d={MIN_GAP}", "-f", "null", "-"],
        capture_output=True, text=True).stderr
    ss = [float(m) for m in re.findall(r"silence_start: ([\d.]+)", err)]
    ee = [float(m) for m in re.findall(r"silence_end: ([\d.]+)", err)]
    return [(start + s, start + (ee[i] if i < len(ee) else dur)) for i, s in enumerate(ss)]


def tighten(r, src):
    s, e = float(r["start"]), float(r["end"])
    sils = silences(src, s, e - s)
    if not sils:
        return [r]
    out, cur = [], s
    for a, b in sils:
        if a - s < EDGE:                     # leading silence: just start later
            cur = max(cur, b - AIR)
            continue
        if e - b < EDGE:                     # trailing silence: stop earlier
            e = min(e, a + AIR)
            break
        if (b - a) - 2 * AIR < MIN_WIN:
            continue                          # not worth a jump cut; leave the rhythm
        left = a + AIR
        if left - cur > 0.20:
            out.append({**r, "start": round(cur, 3), "end": round(left, 3), "reason": "tightened"})
        cur = b - AIR
    if e - cur > 0.20:
        out.append({**r, "start": round(cur, 3), "end": round(e, 3)})
    return out or [r]


def main():
    TIGHT.mkdir(parents=True, exist_ok=True)
    before = after = 0.0
    for p in sorted(PARTS.glob("*.json")):
        edl = json.loads(p.read_text())
        src = next(RAW.glob(f"{edl['source']}.*"))
        b = sum(float(r["end"]) - float(r["start"]) for r in edl["ranges"])
        new = [x for r in edl["ranges"] for x in tighten(r, src)]
        a = sum(float(r["end"]) - float(r["start"]) for r in new)
        edl["ranges"] = new
        (TIGHT / p.name).write_text(json.dumps(edl, indent=2))
        before, after = before + b, after + a
        print(f"{edl['source']}: {len(new):2d} segs  {b:6.1f}s -> {a:6.1f}s  (-{b - a:.1f}s)")
    print(f"\nreclaimed {before - after:.1f}s of dead air")


if __name__ == "__main__":
    main()
