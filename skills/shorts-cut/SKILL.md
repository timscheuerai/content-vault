---
name: shorts-cut
description: Cut raw talking-head takes down to the usable performance — pick the last COMPLETE attempt of each beat, drop false starts, and remove dead air from inside the kept takes. Use when asked to cut/clip raw recordings, remove retakes or false starts, or tighten pauses in talking-head footage.
---

# shorts-cut

Stage 1 of shorts-edit. The judgment-heavy stage.

## The rule

Each recording is ONE short, recorded with many attempts per beat.

> For each beat keep the **LAST** attempt — but only one that actually **finishes**.

Aborted fragments (trailing off into "So…", "and…", a cut-off word like "succes-") are
**not attempts**. Skip them and fall back to the last attempt that completes.

**This matters.** Taking "last" literally ships broken sentences. In the reference session
one clip had **seven** attempts at a beat and the last **three** all failed. A blind
"last attempt" rule would have shipped a garbled step 5.

Retakes often happen *inside* one phrase, separated by a sub-0.5s breath — so cuts must be
made at word boundaries from the word-level view, not at phrase boundaries.

## How

```bash
python $S/words_dump.py        # word-level view with [GAP] markers
# -> spawn one sub-agent per clip, in parallel, with the rule above
# -> each writes edit/edl_parts/<clip>.json
python $S/tighten_edl.py       # pass 2 -> edit/edl_parts_tight/  (SOURCE OF TRUTH)
```

EDL shape: `{"source": "<name>", "ranges": [{"start": s, "end": e, "beat": "...", "reason": "..."}]}`
Cut mechanics: start = first kept word − 0.06s; end = last kept word + 0.15s.

**Pass 2 (`tighten_edl.py`)** removes dead air *inside* a kept take — the speaker pausing
mid-thought. That was 19.1s across 14 clips. It splits each range at **acoustic** silence
(≥0.6s at −60dB), leaving 120ms of air. Cutting inside silence can never clip a word, so
this needs no transcript at all.

## THE TRAP: ASR word END times are fiction

This is the single most expensive lesson in the whole pipeline.

Scribe pads a word's `end` deep into the following pause — one word claimed to run **1.3
seconds** past where the voice actually stopped. It also emits **phantom words over
dead-silent audio**.

Consequences, all measured:
- A word-gap scan reported **2.5s** of internal silence where the audio had **19.1s**.
- Checking cut edges against the word grid produced **25 "cuts inside a word" alarms**.
  Measuring the audio showed **24 were sitting in silence**. Only **one** was real.

> **Word STARTs are reliable. Everything about silence comes from the audio.**
> Use word timings only to avoid cutting mid-word — never to find a pause.

## The other trap: ASR merges repeated words

The speaker said "X", dragged for 0.8s, then said "X" again. ASR merged **both** into a
single `"XX"` token — so the take-picker literally could not see the duplicate; it looked
like one word.

Two follow-on effects:
1. The EDL kept a 0.5s segment that was *just* the first X.
2. Once that was dropped, the surviving X had **no caption**, because the merged token's
   start time now sat outside the segment.

Fix: `edit/word_fixes.json` supports `_insert` — put a word back at the time it is actually
spoken (in SOURCE seconds), and it flows through the EDL like any other word.

```json
{"<clip>": {"_insert": [{"src_at": 256.68, "word": "X", "dur": 0.30}]}}
```

The same file corrects mis-hearings for CAPTIONS only (audio is never touched):
```json
{"<clip>": {"mode": "moat"}}
```

## Expect this much waste

**55–75% of every raw take** is false starts and dead air. If your cut is only removing
20%, you are not looking hard enough at the retakes.

## Verify

`python $S/verify_cuts.py` — no cut edge may land on live speech. It requires **both**
tests to fire: inside a word *and* voiced. See shorts-qa for why either alone is useless.
