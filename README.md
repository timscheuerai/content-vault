# content-vault

19 Claude Code skills + a pre-configured Obsidian vault. Same setup we use to run our content.

Free. MIT. Fork it.

```
researcher            repurpose             lead-magnet-creator
linkedin-copywriter   x-copywriter          long-form              newsletter-writer
youtube-script        youtube-description   youtube-thumbnail      youtube-publisher
graphics-designer     launch-video          video-use
shorts-edit           shorts-cut            shorts-audio           shorts-motion   shorts-qa
```

## Two ways to run this

**Oxygen (hosted).** Team setup, one-click import, integrations already wired up.
oxygen-agent.com

**Claude Code (local).** Clone the repo into your skills folder.

```bash
git clone https://github.com/timscheuerai/content-vault.git ~/.claude/skills/content-vault
```

Then **open that folder in Obsidian** — it ships a pre-configured vault (Kanban board, graph,
backlinks, search; no plugin setup). That's where your content lives and is tracked. See
[The Obsidian side](#the-obsidian-side).

Then in Claude Code:

```
/linkedin-copywriter   draft a post about my Q2 launch
/researcher            find 10 ideas for next week
/repurpose             turn yesterday's webinar into LinkedIn + X
```

## The setup that actually matters

Without this step the writer skills sound like generic AI. Run it once and you're done.

### Connect LinkedIn

Oxygen: already done.

Claude Code: plug in Unipile or whatever you use.

```bash
export UNIPILE_DSN=...
export UNIPILE_API_KEY=...
export UNIPILE_ACCOUNT_ID=...
```

### Tell Claude to fill your corpus

> Pull my last 20 LinkedIn posts via Unipile, sort by reactions, write them into skills/linkedin-copywriter/corpus.md using the format in corpus.md.example.

Claude pulls, sorts, writes the file. From the next draft, linkedin-copywriter writes in your voice.

### Same for X

```bash
export X_BEARER_TOKEN=...
```

> Pull my last 30 tweets, originals only, sort by engagement, write them into skills/x-copywriter/corpus.md.

Done. Skills are personalized.

### Video + YouTube skills (optional)

Only if you use them. Each has a `## SETUP` block in its `SKILL.md`.

```bash
export ELEVENLABS_API_KEY=...   # youtube-description (transcripts), video-use, shorts-*
pip install rembg               # youtube-thumbnail (face cutouts)
brew install ffmpeg             # shorts-*, video-use
pip install pillow numpy        # shorts-* (the graphics + caption renderers)
```

`youtube-publisher` talks to your own channel, so it needs your Google
Cloud project + a YouTube Data API OAuth client (`client_secrets.json`).
Walkthrough is in the skill.

## What's in the vault

**linkedin-copywriter.** Drafts LinkedIn posts in your voice. Hook frameworks, body shapes, CTA patterns, AI-slop blacklist.

**x-copywriter.** Drafts X tweets and threads. Different game than LinkedIn. The skill teaches you the platform as it drafts.

**youtube-script.** Spoken scripts for YouTube longs, shorts, talking-head clips. Timed beats with B-roll cues.

**youtube-description.** Transcribes a finished cut (ElevenLabs Scribe), writes a 2-sentence description, your fixed CTA, and chapter timestamps.

**youtube-thumbnail.** Two-face interview/podcast thumbnails. rembg cutouts, one highlight word, 1280×720 dark + light. Encodes verified 2026 CTR research.

**youtube-publisher.** Uploads a video or a whole numbered series via the YouTube Data API. Titles, descriptions, thumbnails, ordered playlist. Resumable, idempotent.

**long-form.** Newsletter issue, blog, Substack. Outline first, prose second.

**newsletter-writer.** Lifecycle + onboarding emails and broadcasts. Same voice as your posts, rendered to your email template, optional push to Resend.

**lead-magnet-creator.** Builds free assets in 10 formats. Notion, PDF, Sheet, GitHub starter, GPT, web tool, video. The skill that built this vault.

**repurpose.** One master piece (webinar, transcript, post) into N channel variants. Hub-and-spoke.

**researcher.** 3 modes. What's hot in your space. What's working for you. What customers said in interviews.

**graphics-designer.** On-brand graphics. HTML to PNG via headless Chrome.

**launch-video.** 30-60s motion graphics. Remotion + ElevenLabs.

**video-use.** Edit any video by chat. Cuts on word boundaries, grades, burns subtitles. Vendored from [browser-use/video-use](https://github.com/browser-use/video-use).

**shorts-edit** (+ `shorts-cut`, `shorts-audio`, `shorts-motion`, `shorts-qa`). Raw talking-head recordings → postable vertical shorts. Drops the retakes and the dead air, cleans the audio, burns word-by-word captions, adds cue-anchored motion graphics — in **one** video encode — then proves it with a 7-check QA gate. Built on 14 OBS recordings, 57 minutes of raw. Every rule in it exists because a defect got through review looking fine. See [Editing shorts](#editing-shorts).

## Editing shorts

The five `shorts-*` skills are one pipeline. Put your raw recordings in `raw/`, then:

```
/shorts-edit   cut these OBS takes into vertical shorts
```

```
<project>/
  raw/     source recordings (untouched)
  clips/   <name>_final.mp4   <- deliverables
  edit/    every decision, as a file you can inspect and re-run
```

`shorts-edit` orchestrates; `shorts-cut` picks the last complete attempt of each beat and
kills dead air; `shorts-audio` fixes the two audio traps that cost hours; `shorts-motion`
draws cue-anchored graphics; `shorts-qa` is the gate.

The gate is the point. Every bug in this pipeline's history was invisible to eyeballs and
obvious to a measurement — a caption verifier that sampled long words reported perfect
while short words were silently wrong; a tier grade was revealed 5.7s before it was
spoken and every frame looked fine in isolation. So nothing ships until `qa.py` passes.
Not "looks good" — passes.

Graphics render against `skills/shorts-edit/assets/BRAND.md`, which ships conformant with
a neutral palette. Edit it to your brand (or point `SHORTS_BRAND_MD` at the one you
already keep) and `brand_lint.py` fails until the renderers follow — including the rule
no type checker can catch: exactly one accent colour per graphic.

## The Obsidian side

Skills produce content. Your **Obsidian vault** tracks it — no external tool, no sync, every piece
a markdown file you own.

Open this folder in Obsidian (it ships pre-configured) and `content/Content.base` gives you a
**Kanban board** grouped by status (Idea → Drafting → Review → Published → Backlog), plus table and
card views. It's a native Obsidian [Base](https://help.obsidian.md/bases) — no community plugin
needed. Same schema the Notion DB had, now as frontmatter on files you own:

`title · status · pillar · format · channel · author · publish · drive`

New drafts land in `content/posts/`. Want fast semantic + keyword search over your whole back
catalogue (and for agents, via `mcp__qmd__*`)? Run `./scripts/qmd-setup.sh` once, then
`qmd query "..."`.

## The content graph (your ideas compound)

Tags and pillars slice your posts. They don't connect them. So the vault
also ships a **knowledge-graph layer** that mirrors the LLM-wiki pattern
onto your content:

```
content/concepts/   one note per durable idea (your thesis, in pieces)
content/entities/   recurring people, customers, competitors
content/mocs/        narrative arcs that thread posts into a story
```

Each concept note lists the posts that express it. Obsidian's backlinks
make that bidirectional automatically, so every post shows its concepts in
the backlinks pane without you editing the post. Open the graph view and
watch it thicken.

The point is the loop: the writer skills pull the relevant concept as
grounding **before** you draft (so you build on your sharpest prior
framing instead of a blank page) and deposit new ideas back **after** (so
the canon grows underneath you). `/researcher` gets a fourth mode that
mines the graph for the next unwritten beat. Start empty, publish, and in
a few weeks the graph *is* your content thesis.

How it works + templates: `content/CONTENT-WIKI.md`. The vault ships one
worked `example-*` note per type to copy.

## Need help?

Built by us at Oxygen. Stuck? hello@oxygen-agent.com

MIT. Use it however you want.
