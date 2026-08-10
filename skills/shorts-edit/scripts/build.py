#!/usr/bin/env python3
"""Build finished clips: cut + captions + audio, in ONE video encode.

    python build.py                       # every EDL in edl_parts_tight/
    python build.py "<clip-name>"         # one clip
    python build.py --audio hp            # override the audio chain
    python build.py --polish --progress   # opt in to the top progress bar (off by default)

Audio default is `hp`: highpass 60Hz + a constant gain. NO denoiser.

Chosen by ear on headphones after A/Bing everything. Every spectral denoiser reconstructs
the signal instead of just attenuating it, and that reconstruction is audible as an
unnatural tone on headphones — afftdn blind (burbling), a learned noise print at nr=12,
even a 50/50 blend of it. The honest room tone won.

Rejected, with reasons:
  loudnorm            -> silently drops linear mode and pumps (see render_final.py)
  afftdn nr=20 blind  -> the artificial, burbling sound. It guesses the noise.
  learned print nr=12 -> 23 dB quieter, but still reads as processed on headphones
  RNNoise             -> same problem, 17.6 dB
  noise gate          -> useless once the edit is done: the cut is ~96% speech, there
                         are no gaps left to gate. The noise is UNDER the voice.
If a noisier take genuinely needs help, `--audio print12@50` was the best compromise.
"""
import json
import sys
import wave
from pathlib import Path

import numpy as np

from make_captions import build_events, caption_frames
from paths import TIGHT, EDIT, FPS
from render_final import render, DEFAULT_AUDIO


def main():
    argv = [a for a in sys.argv[1:] if not a.startswith("--")]
    audio = DEFAULT_AUDIO
    if "--audio" in sys.argv:
        audio = sys.argv[sys.argv.index("--audio") + 1]
    polish = "--polish" in sys.argv          # zooms + film burns + transition sfx
    progress = "--progress" in sys.argv      # top progress bar. OFF by default — it is ugly.
    # Silent polish: keep the zooms and the burns, drop the sound design. On a talking-head
    # clip the only thing on the audio bus is a voice, so ANY synthetic sound is heard as a
    # sound — there is no music bed for it to sit inside. "Remove the weird sounds."
    nosfx = "--no-sfx" in sys.argv
    names = argv or [p.stem for p in sorted(TIGHT.glob("*.json"))]

    for n in names:
        edl = json.loads((TIGHT / f"{n}.json").read_text())
        ranges = edl["ranges"]
        total = sum(float(r["end"]) - float(r["start"]) for r in ranges)
        events, _ = build_events(n, edl)

        # A tierboard plan is a whole-clip element: it changes where the captions can sit,
        # so it must be resolved BEFORE the caption frames are drawn.
        from motion import load_plan
        raw_plan = load_plan(n)
        tb = raw_plan if isinstance(raw_plan, dict) and raw_plan.get("kind") == "tierboard" else None
        raise_frames = set()
        hide_frames = set()
        if tb:
            import tierboard as TB
            _hook, _vs, _cues, _lead = TB.plan_windows(tb, n, FPS)
            if _vs:
                raise_frames = set(range(max(0, _cues[0] - _lead), round(total * FPS)))

        gplan = [] if tb else (raw_plan or [])

        # A PANEL AND A CAPTION CANNOT SHARE A ROW.
        # Captions sit at 0.78H (y=499). A `stat` panel starts at y=446 and a `steps` panel
        # at y=422 — so the caption lands INSIDE the panel and white type renders on white
        # surface. The tier board already lifts the captions; nothing lifted them for the
        # other primitives, and it shipped, because a caption on a panel is still *legible*
        # against a half-faded panel and only turns invisible at full opacity.
        # `label` is exempt on purpose: its chip sits at 0.86H, 40px clear of the caption.
        if gplan:
            from motion import resolve_plan
            for _f0, _f1, _g in resolve_plan(gplan, n, FPS):
                if _g["kind"] in ("stat", "steps"):
                    raise_frames |= set(range(_f0, _f1))
                elif _g["kind"] in ("people", "cards", "chips", "leads", "flow"):
                    # These hang off a y=470 baseline, so they stop 29px CLEAR of the
                    # caption band and the caption can simply stay where it is. It used
                    # to be hidden for all of them, which cost this clip 13 of its 73
                    # seconds of captions to a collision that the geometry rules out.
                    pass
                elif _g["kind"] == "table":
                    # the only genuinely full-frame primitive: nothing can share with it
                    hide_frames |= set(range(_f0, _f1))

        frames, _ = caption_frames(n, events, total, raise_frames=raise_frames,
                                   hide_frames=hide_frames)

        zooms = sfx = None
        note = ""

        # Motion graphics (edit/motion.json). Independent of --polish: they are content,
        # not decoration. They draw into the same per-frame RGBA sequence, so they cost no
        # extra ffmpeg input and no extra encode.
        if tb:
            import tierboard as TB
            TB.place(frames, tb, n, total, FPS)
            note += f" | tier board ({len(tb['verdicts'])} verdicts, hook blurred)"
        from motion import place
        if gplan:
            place(frames, gplan, FPS, name=n)
            # Count what is ACTUALLY in the plan. This used to iterate a hardcoded list
            # of kinds, so three new primitives rendered correctly and were reported as
            # absent — a build log that quietly disagrees with the render is worse than
            # no log, because it gets trusted instead of the pixels.
            from collections import Counter
            kinds = ", ".join(f"{k}x{c}" for k, c in
                              Counter(g["kind"] for g in gplan).most_common())
            note += f" | motion: {kinds}"

        # Text-BEHIND-subject. Resolve its cues first: any chunk carrying one must be
        # forced to `wide`, or the person cut-out (taken from the raw source) will not line
        # up with a zoomed video frame and you get a soft double-edge around him.
        behind_plan = []
        raw_behind = (raw_plan.get("behind") if isinstance(raw_plan, dict) else None) or []
        if raw_behind:
            from motion import resolve_cue, LEAD
            for b in raw_behind:
                if "at" in b:
                    t = float(b["at"]) + 0.35     # the opener has no cue to anchor to
                else:
                    t = resolve_cue(n, b["cue"], FPS)
                    if t is None:
                        print(f"    !! behind cue not found: {b['cue']!r}")
                        continue
                behind_plan.append({
                    "at_frame": max(0, round((t - 0.35) * FPS)),
                    "dur_frames": round(float(b.get("dur", 1.8)) * FPS),
                    "text": b["text"],
                    "size": int(b.get("size", 74)),
                })

        chunks = None
        if polish:
            from polish import (zooms_for, scene_changes, apply_burns, sfx_bed, SR,
                                plan_chunks, leak_report)
            chunks = plan_chunks(ranges)          # pattern interrupts every ~6s
            if behind_plan:
                # force every chunk overlapping a behind-text to `wide` (see behind.py)
                off = 0.0
                for c in chunks:
                    d = c["end"] - c["start"]
                    f0, f1 = round(off * FPS), round((off + d) * FPS)
                    for b in behind_plan:
                        if f0 < b["at_frame"] + b["dur_frames"] and b["at_frame"] < f1:
                            c["zoom"] = "wide"
                    off += d
            zooms = zooms_for(ranges)
            burns = scene_changes(ranges, FPS)
            apply_burns(frames, burns)               # composited into the caption PNGs
            hook_at = None
            if tb and _vs:
                hook_at = (_cues[0] - _lead) / FPS   # the riser resolves on the board reveal
            if not nosfx:
                bed = sfx_bed(total, burns, FPS, hook_at=hook_at)
                aw = EDIT / "audio_work"
                aw.mkdir(parents=True, exist_ok=True)
                sfx = aw / f"{n}_sfx.wav"
                with wave.open(str(sfx), "wb") as w:
                    w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
                    w.writeframes((bed * 32767).astype(np.int16).tobytes())
            moves = ", ".join(f"{m}x{zooms.count(m)}" for m in ("wide", "in", "close", "out")
                              if zooms.count(m))
            gt = []
            if tb:
                gt = [c / FPS for c in _cues]
            _, leak = leak_report(chunks, gt, total, FPS)
            note += (f" | {len(chunks)} chunks ({len(chunks)-len(ranges)} interrupts)"
                     f" | leak {100*leak/total:.0f}% | {len(burns)} burn(s)")

        if behind_plan and chunks:
            import tempfile, behind as BH
            from render_final import src_for
            with tempfile.TemporaryDirectory() as td:
                BH.place(frames, behind_plan, n, chunks, src_for(n), Path(td), FPS)
            note += f" | {len(behind_plan)} text-behind"

        out = render(n, audio, frames, "_final", zooms=zooms, sfx_wav=sfx,
                     chunks=chunks, progress=progress)
        print(f"{n}: {len(events):4d} captions | {total:6.1f}s -> {out.name}{note}")


if __name__ == "__main__":
    main()
