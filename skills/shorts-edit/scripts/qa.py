#!/usr/bin/env python3
"""THE QA GATE. Run this before a clip ships. Nothing is "done" until it passes.

Every check here exists because a real defect got through review looking fine:

  cuts       a cut through a voiced "um"          — inaudible in a frame-by-frame check
  captions   "THING" on screen where "THE" belonged — every eyeball check hit long words
  motion     the "F" grade revealed 5.7s early     — spoiled the punchline, nothing flagged it
  audio      loudnorm silently pumping             — sounded "weird", cause was invisible
  audio      a mono SFX bed downmixing the voice   — clipped at +0.83 dBFS
  video      a second encode softening the image   — SSIM 0.977 vs 0.998
  retention  91% of the clip with nothing changing — passed every other check

    python qa.py                 # every clip
    python qa.py "<clip>"        # one
Exit code 1 if anything fails.
"""
import json
import os
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np

from paths import PROJ, RAW, CLIPS, TIGHT, FPS, OUT_W, OUT_H, S

# PER-PROCESS. This was a single shared dir, and two qa.py runs in parallel overwrote each
# other's ref.yuv/out.yuv — so the gate compared frames from a DIFFERENT CLIP and reported
# SSIM 0.9514 on a clip that actually measures 0.9976. A verifier that is not safe to run
# concurrently will eventually lie, and it will lie in the direction of failing good work.
SC = Path(f"/tmp/shorts_qa/{os.getpid()}")
SC.mkdir(parents=True, exist_ok=True)


def sh(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def ffprobe(f, entries, stream=None):
    c = ["ffprobe", "-v", "error"]
    if stream:
        c += ["-select_streams", stream]
    c += ["-show_entries", entries, "-of", "csv=p=0", str(f)]
    return sh(c).stdout.strip()


def run_verifier(script, name):
    r = sh([sys.executable, str(Path(__file__).parent / script), name])
    return r.returncode == 0, (r.stdout or "").strip().splitlines()[-1:] or [""]


# ---------------------------------------------------------------- checks

def check_decode(f):
    err = sh(["ffmpeg", "-v", "error", "-i", str(f), "-f", "null", "-"]).stderr.strip()
    return (not err), err.splitlines()[0] if err else "clean"


def check_video(name, f):
    """Native res/fps preserved, one encode, and the image still matches the source.

    SSIM is measured on the FIRST segment, which the zoom cycle always leaves un-zoomed —
    so any loss there is the pipeline's fault, not the zoom's.
    """
    w = ffprobe(f, "stream=width,height,r_frame_rate", "v")
    src = next(RAW.glob(f"{name}.*"))
    sw = ffprobe(src, "stream=width,height,r_frame_rate", "v")
    # The pipeline masters at OUT (one lanczos upscale inside the single encode) so the
    # overlays rasterize at native output resolution — see paths.py. The invariant is now
    # "output == mastering target at the source's fps", not "output == source".
    want = f"{OUT_W},{OUT_H},{sw.split(',')[2]}"
    if w != want:
        return False, f"resolution/fps wrong: {w} (want {want}, source {sw})"

    # Measure where the PIPELINE is the only thing touching the pixels:
    #   * inside a "wide" chunk        (a zoomed chunk is genuinely softer — that is what
    #                                   zooming a 360px source means, not a pipeline fault)
    #   * after the hook graphic ends  (else you measure the blurred board, not the encode)
    #   * cropped to the top of frame  (below that sit the captions and the tier board,
    #                                   which REPLACE pixels by design)
    # Measuring the whole first 4 seconds reported SSIM 0.894 and cried "softened" — it was
    # measuring the hook graphic. A check that measures the wrong region is a false alarm
    # generator, and false alarms get gates switched off.
    #   * and NO FILM BURN inside it. A burn is a deliberate full-frame warm flash. Five
    #     flashed frames out of sixty drag the mean SSIM to 0.984 and the gate shouts
    #     "SOFTENED" at the one effect we intentionally added. Measure between the burns.
    from polish import plan_chunks, scene_changes
    rg = json.loads((TIGHT / f"{name}.json").read_text())["ranges"]
    chunks = plan_chunks(rg)
    burns = scene_changes(rg, FPS)
    off, pick = 0.0, None
    for c in chunks:
        cd = c["end"] - c["start"]
        if c["zoom"] == "wide" and off > 6.0 and cd > 2.0:
            d = min(2.0, cd - 0.2)
            f0, f1 = round(off * FPS), round((off + d) * FPS)
            if not any(f0 - 6 <= b <= f1 for b in burns):   # BURN_LEN is 5 frames
                pick = (c["start"], off, d)
                break
        off += cd
    if pick is None:
        return True, f"{w} (no clean window to measure)"
    src_t, out_t, d = pick

    # y=6 down: BELOW the 3px progress bar. Including it compares emerald against video
    # and drags SSIM from 0.9996 to 0.9908 — a false "softened" alarm.
    # The reference is the source put through THE SAME lanczos upscale the pipeline
    # applies — so SSIM still answers "did the encode soften the image", not "is an
    # upscale an upscale" (which would always fail).
    CROP = f"crop=360:334:0:6,scale={360 * S}:{334 * S}:flags=lanczos"
    OUT_CROP = f"crop={360 * S}:{334 * S}:0:{6 * S}"
    wh = f"{360 * S}x{334 * S}"

    def mean_ssim(src_shift):
        """Mean SSIM over the window, with the source nudged by `src_shift` seconds."""
        sh(["ffmpeg", "-v", "error", "-ss", f"{src_t + src_shift}", "-t", f"{d}", "-i", str(src),
            "-an", "-vf", CROP, "-c:v", "rawvideo", "-pix_fmt", "yuv420p", str(SC / "ref.yuv"), "-y"])
        sh(["ffmpeg", "-v", "error", "-ss", f"{out_t}", "-t", f"{d}", "-i", str(f),
            "-an", "-vf", OUT_CROP, "-c:v", "rawvideo", "-pix_fmt", "yuv420p", str(SC / "out.yuv"), "-y"])
        r = sh(["ffmpeg", "-v", "error", "-s", wh, "-pix_fmt", "yuv420p", "-i", str(SC / "out.yuv"),
                "-s", wh, "-pix_fmt", "yuv420p", "-i", str(SC / "ref.yuv"),
                "-lavfi", "[0:v][1:v]ssim=stats_file=-", "-f", "null", "-"])
        # ssim writes its per-frame stats to STDOUT, not stderr. Reading the wrong stream made
        # this check silently report "not measurable" — a check that cannot measure is worse
        # than no check, because it passes.
        vals = [float(l.split("All:")[1].split()[0])
                for l in (r.stdout + r.stderr).splitlines() if "All:" in l]
        # And it is the MEAN over the window, not `vals[-1]`. Scoring the last frame of 60
        # made the number a coin toss on whichever frame happened to land there.
        return sum(vals) / len(vals) if vals else None

    # ALIGN BEFORE YOU MEASURE.
    # src_t -> out_t is derived from EDL floats, so it can be off by a frame. On a talking
    # head ONE frame of head movement costs 0.005-0.009 SSIM — which straddles the 0.995
    # threshold exactly, and this gate failed two perfectly good clips for MOVING rather
    # than for softening (0.9897 at the assumed offset, 0.9979 one frame over). SSIM here
    # answers "did the encode soften the image", so it must be read at the best alignment;
    # a timing slip is a different question and `verify_cuts` already owns it.
    scores = [(mean_ssim(k / 30.0), k) for k in (-2, -1, 0, 1, 2)]
    scores = [(v, k) for v, k in scores if v is not None]
    if not scores:
        return False, f"{w} — SSIM could not be measured (check is broken, not the clip)"
    val, at = max(scores)
    ok = val > 0.995
    return ok, (f"{w} | SSIM vs source {val:.4f}" + (f" (aligned {at:+d}f)" if at else "")
                + ("" if ok else "  <-- SOFTENED"))


def check_audio(f):
    """No clipping, no limiter, stereo preserved."""
    sh(["ffmpeg", "-v", "error", "-i", str(f), "-vn", "-ac", "1", "-ar", "48000",
        "-c:a", "pcm_s16le", str(SC / "a.wav"), "-y"])
    w = wave.open(str(SC / "a.wav"))
    x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(float) / 32768.
    peak = 20 * np.log10(np.abs(x).max() + 1e-12)
    clipped = int((np.abs(x) >= 0.999).sum())
    ch = ffprobe(f, "stream=channels", "a")
    ok = clipped == 0 and peak < -0.5 and ch == "2"
    return ok, (f"peak {peak:+.2f} dBFS | {clipped} clipped | {ch}ch"
                + ("" if ok else "  <-- CLIPPING / DOWNMIX"))


def check_sfx(name, f):
    """The SFX must be audible ON A PHONE. This exists because a kit shipped that measured
    as perfectly clean audio and was effectively SILENT: prompts asking for a "deep impact
    thud" produced 97-99% sub-bass energy, of which 0.1% survives a phone speaker. Nothing
    else in the gate noticed — the mix was clean, the peak was right, nothing clipped."""
    from polish import SFX_DIR
    import subprocess as sp, io, wave as wv
    bad = []
    for n in ("whoosh", "impact", "riser"):
        p = SFX_DIR / f"{n}.mp3"
        if not p.exists():
            continue
        raw = sp.run(["ffmpeg", "-v", "error", "-i", str(p), "-ac", "1", "-ar", "48000",
                      "-f", "wav", "-"], capture_output=True).stdout
        x = np.frombuffer(wv.open(io.BytesIO(raw)).readframes(-1), dtype=np.int16).astype(float)
        if not len(x):
            continue
        X = np.abs(np.fft.rfft(x * np.hanning(len(x)))) ** 2
        fr = np.fft.rfftfreq(len(x), 1 / 48000)
        phone = 100 * X[fr >= 200].sum() / (X.sum() + 1e-20)
        if phone < 60:
            bad.append(f"{n} {phone:.0f}%")
    ok = not bad
    return ok, ("all phone-audible" if ok
                else "INAUDIBLE ON A PHONE: " + ", ".join(bad))


def check_retention(name, f):
    """The 2026 five-second rule: no >5s block with nothing changing."""
    from polish import plan_chunks, leak_report
    from motion import load_plan
    rg = json.loads((TIGHT / f"{name}.json").read_text())["ranges"]
    total = sum(float(r["end"]) - float(r["start"]) for r in rg)
    gt = []
    plan = load_plan(name)
    if isinstance(plan, dict) and plan.get("kind") == "tierboard":
        import tierboard as TB
        _, _vs, cues, _ = TB.plan_windows(plan, name, FPS)
        gt = [c / FPS for c in cues]
    elif plan:
        from motion import resolve_plan
        gt = [f0 / FPS for f0, _, _ in resolve_plan(plan, name, FPS)]
    leaks, leak = leak_report(plan_chunks(rg), gt, total, FPS)
    pct = 100 * leak / total
    ok = pct < 10
    dur_note = "" if total <= 90 else f" | {total:.0f}s > 90s LinkedIn sweet spot"
    return ok, f"dead-air {pct:.0f}% of runtime ({len(leaks)} leaks){dur_note}"


CHECKS = [
    ("cuts     ", lambda n, f: run_verifier("verify_cuts.py", n)),
    ("captions ", lambda n, f: run_verifier("verify_captions.py", n)),
    ("motion   ", lambda n, f: run_verifier("verify_motion.py", n)),
    ("video    ", lambda n, f: check_video(n, f)),
    ("audio    ", lambda n, f: check_audio(f)),
    ("sfx      ", lambda n, f: check_sfx(n, f)),
    ("decode   ", lambda n, f: check_decode(f)),
    ("retention", lambda n, f: check_retention(n, f)),
]


def main():
    names = sys.argv[1:] or [p.stem for p in sorted(TIGHT.glob("*.json"))]
    failed = 0
    for n in names:
        f = CLIPS / f"{n}_final.mp4"
        print(f"\n=== {n} ===")
        if not f.exists():
            print("  NOT BUILT")
            failed += 1
            continue
        for label, fn in CHECKS:
            try:
                ok, msg = fn(n, f)
            except Exception as e:
                ok, msg = False, f"check errored: {e}"
            if isinstance(msg, list):
                msg = msg[0] if msg else ""
            print(f"  [{'PASS' if ok else 'FAIL'}] {label}  {msg}")
            if not ok:
                failed += 1
    print("\n" + ("=" * 60))
    print("QA GATE: PASS — ship it" if not failed else f"QA GATE: {failed} FAILURE(S) — do not ship")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
