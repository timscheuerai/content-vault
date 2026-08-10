---
name: shorts-edit
description: Turn raw talking-head recordings (OBS, webcam, screen capture) into finished vertical shorts — cut the retakes and dead air, clean the audio, burn word-by-word captions, add cue-anchored motion graphics and retention pattern-interrupts, all in a single video encode, then prove it with a QA gate. Use when asked to edit/cut/clip raw talking-head footage, remove retakes or dead air, denoise recording audio, add captions or motion graphics to a talking-head video, or improve a video's retention.
---

# shorts-edit

The orchestrator. Raw takes in, postable vertical shorts out.

Built and hardened on a real session: 14 OBS recordings, 57 minutes of raw → 21 minutes of
cut. **Every rule below exists because a defect got through review looking fine.**

## The prime directive

> **Nothing is done until `qa.py` passes. Not "looks good" — passes.**

Every single bug in this pipeline's history was invisible to eyeballs and obvious to a
measurement. A caption verifier that sampled long words reported perfect while short words
were silently wrong. A tier grade was revealed 5.7s before it was spoken and every frame
looked fine in isolation. Audio "sounded weird" and the cause was a filter silently
changing mode. **Do not trust your eyes on this material. Measure.**

## Subskills

| Skill | Owns |
|---|---|
| **shorts-cut** | take selection, dead air, why ASR word-ends are fiction |
| **shorts-audio** | the two silent audio traps, and why the answer was no denoiser |
| **shorts-motion** | scout → plan → render, cue anchoring, the brand, the tier board |
| **shorts-qa** | the gate. 7 checks. Run it before anything ships. |

Read the one you need. Read **shorts-qa** always.

## Project layout

```
<project>/
  raw/     source recordings (untouched)
  clips/   <name>_final.mp4   <- deliverables
  edit/    everything derived
    transcripts/       cached word-level ASR — NEVER re-transcribe
    edl_parts_tight/   the cut decisions — SOURCE OF TRUTH
    motion.json        the graphics plan (cue-anchored)
    word_fixes.json    ASR corrections + caption inserts
    caption_work/      per-frame PNG sequence + schedule.json
```

Scripts find the project via `$SHORTS_PROJECT`, `--project <dir>`, or by walking up from
the cwd for `raw/`.

## SETUP

```bash
brew install ffmpeg                 # every stage shells out to it
pip install pillow numpy            # the renderers

# transcription runs through the vendored video-use helpers
export ELEVENLABS_API_KEY=...
```

Then point two shell vars at this vault so the pipeline below copy-pastes:

```bash
V=~/.claude/skills/content-vault/skills    # wherever you cloned content-vault
S=$V/shorts-edit/scripts
```

Optional, all with sane fallbacks — see `scripts/assets.py`:

| Env | Default | If unset |
|---|---|---|
| `SHORTS_FONT` | macOS Helvetica Neue `.ttc` | on Linux/Windows, set it — there is no fallback face |
| `SHORTS_SFX_DIR` | `shorts-edit/assets/sfx/` | synthesised whoosh/impact/riser, measures clean |
| `SHORTS_BRAND_MD` | `shorts-edit/assets/BRAND.md` | ships conformant; edit it to your brand |

## The pipeline

```bash
export SHORTS_PROJECT="/path/to/project"

# 1. transcribe (word-level, CACHED)
python $V/video-use/helpers/transcribe_batch.py "$SHORTS_PROJECT/raw" \
       --edit-dir "$SHORTS_PROJECT/edit" --workers 4
python $V/video-use/helpers/pack_transcripts.py --edit-dir "$SHORTS_PROJECT/edit"
python $S/words_dump.py

# 2. pick takes   -> edit/edl_parts/*.json     (see shorts-cut)
# 3. tighten dead air inside kept takes
python $S/tighten_edl.py                        # -> edit/edl_parts_tight/

# 4. plan graphics (see shorts-motion)
python $S/motion_scout.py "<clip>"              # find the visualizable moments
#   -> hand-write edit/motion.json, CUE-ANCHORED

# 5. build — cut + captions + audio + graphics + polish, ONE encode
python $S/build.py "<clip>" --polish

# 6. THE GATE — nothing ships until this passes
python $S/qa.py "<clip>"
```

## Hard rules (violating any of these produces a silent failure)

1. **ONE video encode.** Trim → concat → zoom → overlay → encode, all in one filtergraph.
   Two encodes softened a 246 kbps source from SSIM 0.998 to 0.977. Never re-encode a
   finished clip to add something to it.
2. **ASR word END times are fiction.** They pad into the following silence and can be
   phantom words over dead-silent audio. Word STARTs are reliable. **All silence reasoning
   comes from the audio (`silencedetect`/RMS), never the transcript.**
3. **Never let ffmpeg derive caption/graphic timing from durations.** The concat demuxer
   re-times to CFR and rounds boundaries as it pleases. Use one PNG per output frame.
4. **Never use `loudnorm` for gain.** See shorts-audio. It silently pumps.
5. **Graphics are cue-anchored, never hand-timed.** See shorts-motion.
6. **Fades only at real cut edges.** A mid-beat framing change is not a cut — the audio
   runs straight through it. A 30ms fade there dips the voice audibly.
7. **`concat` wants inputs interleaved** `v0,a0,v1,a1,…` — not all video then all audio.
   The two are identical for one segment, so a single-segment test clip hides the bug.
8. **PIL's ImageDraw with a partial-alpha fill OVERWRITES pixels, it does not composite.**
   Draw at full opacity on a layer, then fade the layer. Otherwise a fading element punches
   a transparent hole through whatever is beneath it.

## What shipped

| | |
|---|---|
| video | libx264 CRF 6, preset slow, native res/fps, bt709/tv — SSIM 0.9996 vs source |
| audio | highpass 60Hz + a constant gain to −1.5 dBTP. **No denoiser.** |
| captions | Helvetica Neue Medium, lowercase, 18px, tracking −1, no stroke |
| graphics | cue-anchored, on-brand, drawn per frame at 30fps |
| retention | pattern interrupt every ≤4.8s; dead-air 0% |

## Fix the capture, not the edit

The source was **360×640, 246 kbps, −43 LUFS**. No post-processing recovers detail that was
never recorded. Raising the OBS canvas and input gain improves every future edit for free.
