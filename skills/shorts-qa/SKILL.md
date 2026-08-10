---
name: shorts-qa
description: The quality gate for edited talking-head shorts. Seven measured checks — cuts, captions, motion-graphic sync, video fidelity vs source, audio integrity, decode, and retention. Use before shipping any clip produced by shorts-edit, or when asked whether a video is ready, whether quality was lost, or to verify an edit.
---

# shorts-qa

## Align before you measure

The SSIM check answers exactly one question: **did the encode soften the image.** It must
therefore be read at the *best* alignment, because `src_t -> out_t` comes from EDL floats
and can slip by a frame — and on a talking head **one frame of head movement costs
0.005-0.009 SSIM**, which straddles the 0.995 threshold precisely.

It failed two perfectly good clips for *moving*: 0.9897 at the assumed offset, **0.9979 one
frame over**. `check_video` now takes the max mean over ±2 frames and prints the alignment.
Timing is a different question, and `verify_cuts` already owns it.

Same check, second bug: it scored `vals[-1]`, the **last per-frame line** of 60, not the
window mean. A gate whose number is a coin toss on one frame is not a gate.

Third: **measure between the burns.** A film burn is a deliberate full-frame warm flash.
Five flashed frames out of sixty drag the mean to 0.984, and the gate then shouts SOFTENED
at the one effect we added on purpose. `check_video` now rejects any window containing a
burn.

## The verifier must be safe to run concurrently

`SC` was one shared `/tmp/shorts_qa`, so two `qa.py` processes overwrote each other's
`ref.yuv` / `out.yuv` and the gate **compared frames from a different clip** — reporting
SSIM **0.9514** on a clip that actually measures **0.9976**. It is now per-PID.

Three of the four "failures" in that batch were the harness, not the footage. A verifier
that is unsafe under parallelism will eventually lie, and it lies in the direction of
**failing good work** — which is the direction that gets gates switched off.


> **Nothing is done until this passes. Not "looks good" — passes.**

```bash
export SHORTS_PROJECT="/path/to/project"
S=~/.claude/skills/content-vault/skills/shorts-edit/scripts   # wherever you cloned it
python $S/qa.py            # every clip
python $S/qa.py "<clip>"   # one
```
Exit code 1 on any failure.

## Why this exists

**Every bug in this pipeline's history was invisible to eyeballs and obvious to a
measurement.** Not one was caught by watching the video.

| Check | The defect it exists to catch |
|---|---|
| **cuts** | A cut through a voiced "um". Inaudible frame-by-frame; a chewed syllable in motion. |
| **captions** | "THING" on screen where "THE" belonged. Every eyeball check happened to land on long words and looked perfect; "THE" is 3 frames long. |
| **motion** | A tier grade revealed 5.7s before it was spoken — the punchline, spoiled. Nothing flagged it; every frame was individually correct. |
| **video** | A second encode softening the image. SSIM 0.977 vs 0.998. Invisible on a phone, real on a 246 kbps source. |
| **audio** | `loudnorm` silently abandoning linear mode and pumping. And a mono SFX bed downmixing the stereo voice into +0.83 dBFS clipping. |
| **decode** | Corrupt output that still plays in QuickTime. |
| **retention** | 91% of a clip sitting in blocks where nothing changes for >5s. Passed every other check. |

## The seven checks

1. **cuts** — no cut edge lands on live speech. The intersection of two tests: it must land
   *inside a word* (per the transcript) AND be *voiced* (per the audio). Either alone is
   useless — the word grid gave 25 false alarms, and "voiced at the edge" flags every
   deliberate filler deletion.
2. **captions** — pixel-matches each rendered frame against the word bitmap we drew, scored
   against the expected word *and its neighbours*, **sampling biased toward the shortest
   words**. Reads the schedule the renderer wrote.
3. **motion** — every graphic fires within 0.2s of its spoken cue; no typo'd cue silently
   dropping a graphic; no overlapping panels.
4. **video** — native res/fps preserved, and SSIM > 0.995 vs the source.
5. **audio** — zero clipped samples, peak under −0.5 dBFS, stereo preserved.
6. **decode** — clean full decode.
7. **retention** — the 2026 five-second rule: no block >5s with nothing changing.

## The meta-lesson: a verifier that assumes is a verifier that lies

Three times, the *verifier* was the bug:

- It **recomputed** the caption frame numbers instead of reading what the renderer wrote —
  so it re-implemented the code under test and cheerfully agreed with its off-by-one.
  **Fix: verifiers read the artifact the renderer produced, never recompute it.**
- It measured the video's SSIM over a region containing **the graphics and the progress
  bar**, cried "SOFTENED" at 0.894, and was comparing a blurred overlay to raw video.
  **Fix: measure only where the pipeline is the only thing touching the pixels.**
- It read ffmpeg's SSIM from **stderr** when it goes to stdout, and reported "not
  measurable" — which *passed*. **A check that cannot measure is worse than no check.**

When a check fails, first ask whether the *check* is wrong. Then fix the video.

## When the gate fails

Read the message, don't just re-run. Each failure names the file and the moment. The gate
prints the numbers so you can see whether a value is marginal or catastrophic.

Known-acceptable warnings:
- `107s > 90s LinkedIn sweet spot` — informational; shorter is better but not a defect.
