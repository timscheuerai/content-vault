---
name: shorts-motion
description: Add on-brand motion graphics and retention pattern-interrupts to a talking-head short — cue-anchored stats, step lists, tier boards and lower-thirds, drawn per frame, plus zoom interrupts that plug retention leaks. Use when asked to add motion graphics, animations, overlays, b-roll cards, a tier list, or to improve a video's retention/pacing.
---

# shorts-motion

Stage 4 of shorts-edit. **Scout → Plan → Render → Verify.** Never skip the scout.

The pipeline already composites a **per-frame RGBA sequence** for captions, which means it
is *already a motion-graphics engine*: anything drawable in PIL can be animated at frame
resolution with **no extra ffmpeg input and no extra encode**.

---

## The three rules that make a graphic land

**1. ANCHOR TO THE WORDS, NEVER TO A TIMESTAMP.**

Hand-typed times failed catastrophically and invisibly: six of eight graphics were out of
sync and one revealed the **"F" tier grade 5.7 seconds before he said it**. In a tier list
the grade IS the punchline. Every frame was individually correct; nothing flagged it.

The plan names a **phrase**, not a time. `resolve_cue()` finds when it is spoken and fires
the payload — the grade filling, the number landing — exactly on the word.

```json
{ "cue": "definitely f tier", "grade": "F", "label": "Instagram / TikTok" }
```

**2. OVERLAY PANELS, NOT FULL-SCREEN CARDS.**

A full-screen card doesn't add a graphic — it *removes the presenter*, and on a talking-head
short the face is what carries it. Panels sit in the lower third; he stays on camera.
Full-screen is reserved for a genuine chapter break or a hook.

**3. THE MOTION MUST TRACK THE SPEECH.**

A card that fades in is a slide. A number that counts up and *lands* on the word, a list
that builds as he names each item, a tier chip that fills the instant he says "S tier" —
those feel authored. Everything else feels pasted on.

---

## Scout first — do not invent moments

```bash
python $S/motion_scout.py "<clip>"
```

It surfaces where a graphic would actually *earn* its place: hard numbers, enumerations,
rankings, named tools. On the reference session it found one clip was a **tier list**
(8 verdicts), another a **5-step system with a 0→300 users target**, another carrying
**14% / 11% / 0.5% reply rates**. Content that was invisible to a blind pass.

**Copy is editorial, never generated.** Auto-deriving it from the transcript produced
headlines like *"step number five is actually relaunching your saas every two weeks with a
launch"*. A bad graphic is worse than none. A clip with no plan entry simply gets none.

## Primitives (`motion.py`)

| kind | use for | motion |
|---|---|---|
| `stat` | a hard number | counts up and lands on the word |
| `steps` | an enumeration | rows build one at a time; the live row goes bold + emerald |
| `tier` | a ranking | chips greyed, the called grade fills emerald and pops |
| `label` | anything else | a lower-third chip — the lightest touch |
| `logo` | naming a product | brand mark parks just above the caption band |
| `people` | real accounts | profile cards, follower counts counting up |
| `chips` | a list of sources | small title-only cards landing left to right |
| `leads` | a lead table | LinkedIn rows stream, then the scores land on a second cue |
| `flow` | a routing decision | lanes greyed; each fills, and its wire draws, on its own cue |

Everything except `stat`/`table` hangs off a **y=470 baseline**, which stops 29px clear of
the caption band. Panels built that way need no caption lift and no caption hide — the
captions just keep running. `hide_frames` had been applied to every mid-frame panel, which
cost the Lovable clip 13 of its 73 seconds of captions to a collision the geometry ruled
out.

## Nested cues — when one panel spans several beats

A graphic that stays up across a long beat (the routing board: tier 1 at 28.0s, tier 2 at
30.1s, tier 3 at 34.3s) cannot stagger its rows off a frame counter — the stagger drifts
the moment the speech does, which is the same class of failure as a hand-typed timestamp.
Give each row its own `cue`; `resolve_plan()` resolves it to `_at`, in frames relative to
the panel's window.

```json
{"kind": "flow", "cue": "hand over all the", "dur": 12.6, "lanes": [
  {"cue": "tier one leads", "badge": "TIER 1", "to": "Sales team", "focal": true},
  {"cue": "tier two",       "badge": "TIER 2", "to": "Sequence", "tiles": ["...linkedin.png"]}
]}
```

A `<name>_cue` key on the graphic itself resolves the same way, to `_at_<name>`. That is
how the lead table's grades wait for "score them against their ICP" instead of firing on
the panel's own entrance four seconds earlier.

## A primitive's payload is not always 0.7s after its entrance

`LEAD`/`PAYLOAD` encode one choreography: the panel arrives, *then* the number lands on
the word. `logo` and `chips` have nothing that lands later — the mark appearing IS the
payload. `verify_motion.py` assumed the PAYLOAD model for every kind, so holding a logo to
"entrance + 0.7s == the word" pushed its *entrance* 0.7s ahead of the word. The Lovable
mark sat on screen most of a second before he said "Lovable", and every run reported `ok`.

> A verifier that models one primitive's choreography and applies it to all of them
> certifies the bug. `ENTRANCE_IS_PAYLOAD` in `verify_motion.py` is the per-kind offset;
> multi-lane boards skip the single-payload check and verify each lane's own cue instead.

New primitives must also be added to `brand_lint.py`'s render list. Three shipped outside
it once, which meant the one-green rule was enforced on the four oldest renderers and
silently not on the newest.

## The tier board (`tierboard.py`)

A different shape: **one persistent, cumulative board**, not eight panels flashing in and
out. The hook shows the finished board with the lane contents **blurred** (tease the payoff,
don't give it), then each channel drops onto its row as he says the grade. The viewer
watches it fill in. That *is* the tier-list format.

It occupies the lower ~40%, so the captions **lift to 60% height** for exactly those frames
rather than being hidden for 100 seconds.

## A panel and a caption cannot share a row

Captions sit at **0.78H (y≈499)**. A `stat` panel starts at **y=446**, a `steps` panel at
**y=422**. So a caption lands *inside* the panel, and white type on a white surface is
invisible at full opacity.

The tier board already lifted the captions to 0.60H. Nothing lifted them for the other
primitives, and it shipped — because a caption over a *half-faded* panel is still legible,
so it looks fine in exactly the frames you happen to spot-check.

> **Any frame carrying a `stat` or `steps` panel lifts the captions to 0.60H.**
> `label` is exempt: its chip sits at 0.86H, ~40px clear of the caption band.

`build.py` resolves the plan **before** `caption_frames()` and unions those windows into
`raise_frames`. Order matters: the captions have to know about the panels before they draw.

## `label()` accepts a `kicker` and does not draw it

The chip is one line by design; a kicker row would make it a panel. The argument stays in
the signature so every primitive takes the same plan shape — but it is **silently dropped**,
and that silence once cost a whole batch its step numbers. If you want the kicker seen, put
it in `text`: `"01 · Build in public"`.

## Brand — do not invent values

From `gtm-production/brand/BRAND.md`:
```
surface #ffffff · ink #0a0a0a · muted #71717a · line #e4e4e7 · accent #10b981 (ONE dot, sparingly)
font-sans Helvetica Neue (the same face as the captions) · radius 6/10/14/20
"everything is ink, surface, and line" — no shadows, no gradients.
```

---

## Retention: the 2026 five-second rule

> Any 5-second block with no cut, zoom, text or sound change is a **retention leak**.

The reference clip failed badly: **97 of 107 seconds (91%)** sat in a dead block, the worst a
16.8-second stretch. All the cuts and graphics clustered at beat boundaries, and beats run
11–17s.

**Fix: automatic pattern interrupts.** `plan_chunks()` splits long beats into ≤4.8s chunks
with alternating framing — a snap change of camera mid-sentence. It is *not* a cut; the
audio runs straight through. **18 interrupts, leak 91% → 0%.**

Two things this depends on:
- **Fades only at real cut edges.** A 30ms fade at a framing split dips the voice audibly.
  Verified: 0 discontinuities across all 18 internal joins.
- **Use `ceil` for the chunk count.** Floor-plus-fudge left 5.7s chunks — still a leak.

A 3px `drawbox` progress bar is available (`--progress`) but is **off by default** — it
reads as UI chrome bolted onto the frame. Cheap is not the same as good.

---

## THE RENDERING TRAP: PIL alpha does not composite

**`ImageDraw` with a partial-alpha fill OVERWRITES pixels.** A chip fading in therefore
punches a transparent **hole** straight through the white panel beneath it, and the video
shows through — the selected tier chip rendered as a **black box** instead of a green one.

> **Draw everything at full opacity on its own layer, then fade the layer.**
> Never draw with a variable alpha. To animate a colour, LERP the colour — not the alpha.

## Text behind the subject

The "he's standing in front of the word" look. `behind.py`. Composite order per frame:

    video  ->  big text  ->  the person, cut back out on top  ->  captions + board

Two things make it work:

1. **It stays inside ONE encode.** The naive way is a second pass (render, re-read, segment,
   re-encode) — and a second encode measurably softens the image. Instead the person is baked
   into the same per-frame RGBA overlay the captions use, cut from the **raw source** frames
   that ffmpeg is already decoding. The cut-out lands on top of itself: no seam.
2. **Any chunk carrying a behind-text is forced to `wide`.** A zoomed chunk is scaled by
   zoompan inside ffmpeg, and re-deriving that transform in PIL would never match
   pixel-for-pixel — you would get a soft double-edge around him.

**Layer order is the whole trick.** Compositing the person LAST put his shoulder on top of
the tier board and clipped the lanes. The person goes UNDER the UI: word, then him, then
captions and board.

Segmentation: `rembg` (u2netp), ~0.2s/frame. Use it on **2-4 hero moments**, not the clip.

```json
"behind": [{"cue": "for sure s tier", "text": "S TIER", "dur": 1.9}]
```

## Verify

```bash
python $S/verify_motion.py "<clip>"
```
Every graphic fires within 0.2s of its cue; no typo'd cue silently dropping a graphic; no
overlapping panels; verdicts in ascending order.
