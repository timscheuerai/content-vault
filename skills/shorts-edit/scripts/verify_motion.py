#!/usr/bin/env python3
"""Prove every motion graphic fires ON the word it belongs to.

This exists because hand-typed timestamps failed badly and INVISIBLY: on the tier-list
clip, six of eight graphics were out of sync and one showed the "F" grade 5.7 seconds
before he said it. In a tier list the grade IS the punchline, so that one error ruined
the beat — and nothing in the render flagged it. It looked fine frame by frame.

Checks, per graphic:
  * the cue phrase actually exists in the transcript (a typo silently drops the graphic)
  * the payload frame — the grade filling, the number landing — coincides with the
    spoken cue within TOL
  * no two graphics overlap (a stacked panel overwrites its neighbour mid-animation)
  * the graphic fits inside the clip

    python verify_motion.py "<clip>"     # exits 1 on any failure
"""
import sys

from motion import LEAD, PAYLOAD, load_plan, resolve_cue, resolve_plan
from make_captions import build_events
from paths import TIGHT, FPS

TOL = 0.20      # seconds

# WHERE A PRIMITIVE'S PAYLOAD ACTUALLY FIRES, in frames after its entrance.
#
# This used to be assumed to be PAYLOAD for everything, and that assumption made this
# verifier certify a real defect. `logo` and `chips` have nothing that lands later — the
# mark appearing IS the payload — so holding them to "entrance + 0.7s == the word" pushed
# the entrance 0.7s AHEAD of the word, and the Lovable mark was on screen most of a second
# before he said "Lovable". Every run reported `ok`. A verifier that models one primitive's
# choreography and applies it to all of them agrees with the bug.
ENTRANCE_IS_PAYLOAD = {"logo", "chips"}


def payload_offset(kind):
    return 0 if kind in ENTRANCE_IS_PAYLOAD else PAYLOAD


def check_lanes(name, f0, f1, g):
    """`flow` has no single payload: each lane lands on its OWN cue, seconds apart. Its
    per-lane frames are resolved in resolve_plan (`_at`), so drift is 0 by construction —
    what can still go wrong is a typo'd lane cue (the lane silently never fills), lanes
    out of order, or a lane landing outside the panel's window."""
    ok = bad = 0
    lanes = g.get("lanes") or []
    prev = -1
    for lane in lanes:
        tag = lane.get("badge") or lane.get("to") or "lane"
        at = lane.get("_at")
        if at is None:
            bad += 1
            print(f"        FAIL  {tag:14} cue {lane.get('cue')!r} not found — never fills")
            continue
        t = (f0 + at) / FPS
        if at <= prev:
            bad += 1
            print(f"        FAIL  {tag:14} lands out of order at {t:.1f}s")
        elif f0 + at >= f1:
            bad += 1
            print(f"        FAIL  {tag:14} lands at {t:.1f}s, after the panel is gone")
        else:
            ok += 1
            print(f"        ok    {tag:14} fills @{t:6.1f}s  on {lane.get('cue')!r}")
        prev = at
    return ok, bad


def check_tierboard(name, spec):
    """The board is a whole-clip element, so the checks differ: every verdict cue must
    resolve (a typo silently drops a channel from the board), the verdicts must be in
    ascending time order (the board builds — a chip cannot land before the one it follows),
    and the hook must sit before the first verdict."""
    import tierboard as TB
    _, total = build_events(name)
    hook, vs, cues, lead = TB.plan_windows(spec, name, FPS)

    ok = bad = 0
    print(f"\n=== {name} (tier board) ===")
    dropped = len(spec["verdicts"]) - len(vs)
    if dropped:
        bad += dropped
        print(f"  FAIL  {dropped} verdict(s) dropped — cue not found in the transcript")
    if hook and cues and hook[1] > cues[0]:
        bad += 1
        print("  FAIL  the blurred hook is still on screen when the first channel lands")
    elif hook:
        ok += 1
        print(f"  ok    hook (blurred) {hook[0]/FPS:.1f}-{hook[1]/FPS:.1f}s")

    prev = -1
    for v, c in zip(vs, cues):
        if c <= prev:
            bad += 1
            print(f"  FAIL  {v['label']:20} lands out of order at {c/FPS:.1f}s")
        elif c / FPS > total:
            bad += 1
            print(f"  FAIL  {v['label']:20} falls past the end of the clip")
        else:
            ok += 1
            print(f"  ok    {v['grade']}  {v['label']:20} @{c/FPS:6.1f}s  on {v['cue']!r}")
        prev = c
    return ok, bad


def check(name):
    plan = load_plan(name)
    if not plan:
        return 0, 0
    if isinstance(plan, dict) and plan.get("kind") == "tierboard":
        return check_tierboard(name, plan)
    _, total = build_events(name)
    resolved = resolve_plan(plan, name, FPS)

    ok = bad = 0
    print(f"\n=== {name} ===")
    for f0, f1, g in resolved:
        cue = g.get("cue", "")
        off = payload_offset(g["kind"])

        # A multi-lane board has no single payload — its entrance is just the panel
        # arriving, and every lane is checked against its own cue below.
        if g.get("lanes"):
            print(f"  ---   {g['kind']:18} panel up @{f0/FPS:6.1f}s  on {cue!r}")
            o, b = check_lanes(name, f0, f1, g)
            ok += o
            bad += b
            continue

        t = resolve_cue(name, cue, FPS) if cue else float(g.get("at", 0)) + LEAD
        payload_t = (f0 + off) / FPS              # when the payload actually fires
        drift = payload_t - t
        problems = []
        if abs(drift) > TOL:
            problems.append(f"payload {drift:+.2f}s off the spoken cue")
        if f1 - f0 < off + 8:
            problems.append(f"too short — payload never lands (dur {(f1-f0)/FPS:.1f}s)")
        if f1 / FPS > total + 0.1:
            problems.append("runs past the end of the clip")

        tag = g.get("label") or g.get("text") or g.get("value") or g["kind"]
        if problems:
            bad += 1
            print(f"  FAIL  {tag:22} @{payload_t:6.1f}s  " + "; ".join(problems))
        else:
            ok += 1
            print(f"  ok    {tag:22} @{payload_t:6.1f}s  fires on {cue!r}")

    dropped = len(plan) - len(resolved)
    if dropped:
        bad += dropped
        print(f"  FAIL  {dropped} graphic(s) dropped — cue not found in the transcript")
    return ok, bad


def main():
    names = sys.argv[1:] or [p.stem for p in sorted(TIGHT.glob("*.json"))]
    O = B = 0
    for n in names:
        o, b = check(n)
        O += o
        B += b
    print(f"\nTOTAL {O}/{O+B} graphics fire on their cue" +
          ("  <-- FAILURES" if B else "  — all in sync"))
    return 1 if B else 0


if __name__ == "__main__":
    sys.exit(main())
