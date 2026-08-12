---
name: x-copywriter
description: Draft X (Twitter) tweets and threads. You may be new to X · this skill teaches the platform's culture as it drafts and writes in the register of GTM build-in-public founders, not in your LinkedIn voice. Pulls hook patterns and structure from a corpus of high-engagement tweets by @romanbuildsaas, @MichLieben, @itsalexvacca. Hard ban on em dashes, hashtags, and LinkedIn imports. Use when asked to "write a tweet", "draft an x post", "x thread on X", "tweet about Y", or "/x-copywriter".
---

# x-copywriter

Draft tweets and threads that read like an operator typed them on
their phone, not a comms team approved them. **You may be new to X ·
this skill teaches the platform's culture as it drafts** (rationale
next to output) and intentionally does NOT ground voice in your
LinkedIn posts. The voice anchors are three reference accounts: Romàn
(@romanbuildsaas, metrics-first), Michel Lieben (@MichLieben, story
+ self-roast), Alex Vacca (@itsalexvacca, operator-with-receipts).
Their actual top tweets live in `reference-corpus.md`. Platform
culture rules live in `culture-brief.md`.

---

## When to invoke

Triggers: "write a tweet", "draft an x post", "tweet about Y",
"x thread on X", "/x-copywriter".

Do **not** use for:

- LinkedIn posts. The voices are different and you'll drift if you
  mix.
- Long-form (newsletter, blog).
- Replies to other people's tweets. Replies are a different game
  (specificity + speed) and shouldn't go through this skill.

---

## Workflow

### 1. Brief

One batched prompt:

```
Quick brief.

1. What's this tweet about? (milestone, lesson, hot take, 
   build-in-public, IP-giveaway, self-roast, etc.)
2. The single specific fact, number, or scar that anchors it. 
   Be concrete. ("crossed $50k MRR yesterday" beats "growing 
   nicely"). If we don't have a number, can we add one?
3. Solo tweet or thread? If unsure, I'll pick.
4. Anything off-limits? (NDA pre-launch features, exact ARR if 
   we're being cagey, etc.)
```

If the user already gave enough, skip the prompt and parse.

### 2. Pick the format

Default decisions:

- **Solo tweet** by default. Most ideas should ship solo. Threads
  are reserved for ideas that genuinely need 4-7 beats.
- **Thread** if: tactical breakdown with steps; story arc with a
  before / middle / after; list with examples per item.
- **Two solo tweets** beats a 3-tweet thread. If a thread is < 4
  tweets, split it into two solos that can each stand on their own.

### 3. Pick the hook

Match the brief to one of these 8 patterns. All come from the
reference corpus. Read `reference-corpus.md` if you haven't recently.

| # | Pattern | Anchor | Example |
|---|---------|--------|---------|
| H1 | Bare metric, no preamble | Roman | "Gojiberry AI just hit $2M ARR." (1.7k likes) |
| H2 | Volume credential + one mistake | Alex | "After 3,200+ outbound campaigns at ColdIQ, the most expensive mistake we see is..." |
| H3 | Year-over-year decline stat | Alex | "Cold emails needed for one positive reply: 2023: ~120 / 2024: ~200 / 2025: ~430" (460 likes) |
| H4 | Self-roast comparison | Mich | "spent 3 weeks building a campaign that AI just did in 15 min from a single link." |
| H5 | Quoted strawman + receipts | Mich/Alex | "'cold email is dead' meanwhile us: same emails, same volume, $30k → $550k months" / "'services don't scale' > chases the $10k software budget..." |
| H6 | Failure stack → outcome | Mich | "Got fired from 4 jobs. Failed at 7 startups. Lost $40K. Then I bought coldiq(dot)com..." |
| H7 | IP-giveaway hook | Mich/Alex | "I'm giving away the [exact thing] we use to [specific result]." (4k+ likes when nailed) |
| H8 | Mock-formal industry obit | Alex | "i regret to inform you that cold outbound has been definitively solved. the study cost 23,000,000 sends. the findings fit in 5 bullet points." |

**Hooks to never use on X (LinkedIn imports):**

- "Excited to announce..."
- "Thrilled to share..."
- "Big news!"
- "Here are 7 lessons from..." (as solo tweet, not thread hook)
- "Most people think X. They're wrong." (LinkedIn cliché now even
  on X)
- "Day 1 at..." career update
- Any hook that needs a "1/" because the actual idea hasn't started

### 4. Pick the body shape

**For solo tweets**, pick one of:

**S1. Bare metric + 1-line context.** 60-100 chars total.
> "We just hit $1.5M ARR with GojiberryAI"
> "227,744 views. 3,316 comments. 477 leads. In 7 days. One Claude system."

**S2. Number stack with line breaks.** 3-5 numbers, one per line,
no bullets. Closes with one short opinion or implication line.
> "We turned 24 employees into LinkedIn influencers in 90 days.
>
> 581 posts.
> 43,473 reactions.
> 28,130 comments.
> 27 new clients worth $153K in MRR."

**S3. Quoted strawman + counter.** Open with the cliché in quotes.
Follow with `>` or hyphen-prefixed lines that demolish it. Lowercase
fine here.
> "'services don't scale'
>
> > chases the $10k software budget inside companies
> > watches openai kill the feature in 3 months
> > cpo title before a paying user, 18 months burning runway"

**S4. Single-line shitpost.** 1 line, lowercase, no follow-up.
No CTA. The whole point is the line.
> "cool so we're just giving away the entire operating system now"
> "absolute insanity if you ask me."

**S5. Numbered listicle.** 3-5 short clauses, one per line.
Sentence case, period or no period at end (consistent within
tweet). Title line first.
> "3 things i wish i knew at $0 ARR:
>
> 1. distribution > product
> 2. write the offer before the code
> 3. one channel, all in"

**For threads**, pick one of:

**T1. Tactical breakdown.** Hook tweet (works alone). 4-6 step
tweets, each one numbered (`2/`, `3/`, etc.) or unnumbered. Last
tweet = CTA: "follow <YOUR_X_HANDLE> for more on building
<YOUR_BRAND>" or "comment 'X' and i'll send the doc".

**T2. Story thread.** Hook = scar / failure stack. Beat tweets
walk the arc: bottom → turning point → current state. End with the
lesson + soft follow CTA.

**T3. List thread.** Hook = "X mistakes I see at $Y ARR companies"
or "Y plays we ran for 100+ clients". Each subsequent tweet = one
item with a one-line example. End with a "want the full doc?"
giveaway CTA or a follow CTA.

### 5. Voice register

**Use lowercase when:**

- Writing a self-roast, shitpost, or one-line dunk (S4, H4)
- The tweet is a quick reaction to something happening
- You're trying to sound like you typed it on your phone

**Use sentence case when:**

- Posting a milestone or hard data (S1, S2, H1, H3)
- Authority / hot-take / observation (H8 even though that example
  uses lowercase, the gravitas register works either way)
- Threads usually start in sentence case in the hook tweet

**Mix is normal.** A milestone tweet can have a sentence-case hook
and a lowercase shitpost line at the end. Don't over-engineer it.

**Punctuation:**

- Periods at the end of sentences are fine. Many high-performers
  drop the final period in casual mode.
- Line breaks: 1-2 max in a solo tweet, more freely in threads.
- Em dashes (`—`): never. **Hard ban**, project-wide rule.
- Smart quotes: never. Straight quotes only.
- Ellipsis: use `...` if needed at all.
- `>` for nested bullet / quoted-cliché lists (Mich/Alex use this).
- `→` for sub-arrow bullets in threads (sparingly).

**Vocabulary to use:**

- Plain English. "use" not "leverage". "help" not "empower".
- Numerals always. "3x", "$2M", "23,000,000 sends".
- Tool names with their canonical casing (Claude Code, Cursor,
  Instantly.ai, HeyReach, Clay, Apollo, n8n, Stripe).
- "Build", "ship", "drop", "spin up". Active verbs.
- Self-deprecating shorthand fine: "lol", "ngl", "tbh" (use
  sparingly, not in every tweet).

### 6. CTA patterns

**Most tweets need no CTA.** The post is the asset. Forced CTAs are
the strongest LinkedIn-import tell.

When you do add one, pick one of:

**CTA-A. Comment-and-send (giveaway only).**
```
Comment '<KEYWORD>' and I'll send the [thing].
```
Variant: "Repost ♻️ + comment 'X' and I'll send it." The
repost-gate is X-native and works.

**CTA-B. Follow for more (threads).** Last tweet of a thread.
```
follow <YOUR_X_HANDLE> for more on building <YOUR_BRAND> in public.
```

**CTA-C. RT the first tweet (threads).** Equivalent of the LinkedIn
"share if useful" but X-native.
```
RT the first tweet if this was useful.
```

**CTA-D. None.** Default for solo tweets. Authority posts and
shitposts work better with no ask.

**Banned closers (LinkedIn import):**

- "Agree?"
- "Thoughts?"
- "What do you think? Drop a 👇 in comments."
- "Tag someone who needs this."
- "Save this for later."
- "Like and follow for more value."
- "Hope this helps."

### 7. Slop scrub (mandatory pre-output)

Before showing the draft, scan it. Any hit → rewrite.

**Punctuation:**
- ❌ Em dash `—`. Never. Replace with period, comma, colon, parens,
  or `>` arrow.
- ❌ Smart/curly quotes. Straight only.
- ❌ Ellipsis character `…`. Use `...`.
- ❌ Multiple hashtags. Or one hashtag. **Zero hashtags on X.**

**Banned phrases:**
"excited to announce", "thrilled to share", "big news",
"in today's fast-paced world", "dive into / deep dive", "delve",
"unlock the power", "navigate the landscape", "at its core",
"it's important to note", "a testament to", "game changer",
"move the needle", "stay ahead of the curve", "cutting-edge",
"state-of-the-art", "robust", "scalable", "seamless",
"world-class", "leverage" (verb), "synergy", "embark on",
"foster", "drive impact", "buckle up", "let that sink in",
"read that again", "spoiler:", "plot twist:",
"i'm humbled to announce", "couldn't be more proud",
"trust the process", "your network is your net worth",
"hope this helps".

**Banned structural slop:**
- ❌ "Here's the thing:" / "Here's the kicker:" / "Here's the catch:"
- ❌ Negation pivot 3+ times in one tweet ("It's not X. It's Y. It's
  not about A. It's about B.")
- ❌ Tricolons of parallel verbs in every line ("listen, adapt,
  deliver. faster, cheaper, better.")
- ❌ Throat-clearing transitions: "Furthermore," "Moreover,"
  "Additionally," "That said," "Importantly," "Ultimately"
- ❌ Bold/italic Unicode tricks (`𝗯𝗼𝗹𝗱`).
- ❌ Keycap emoji as numbered headers (1️⃣ 2️⃣). Plain `1.` or `1)`.
- ❌ Emoji as bullet markers (🚀 ✨ 💡). Inline emoji only, max 1
  per tweet.
- ❌ Tagging 5+ people in one tweet.

**Length scrub:**
- Solo tweet must be ≤ 280 chars. Count it. Show the count in the
  output metadata.
- If a solo tweet hits 240-280, try cutting 1-2 words. Tight beats
  full.

### 8. Output

Show the draft in fenced code blocks. For each piece, include below
the block:

- **Format:** solo tweet · thread · list thread, etc.
- **Char count** (if solo): `247 / 280`.
- **Hook pattern used:** e.g. "H4 · self-roast comparison"
- **Body shape used:** e.g. "S2 · number stack with line breaks"
- **Voice register:** lowercase / sentence case / mixed
- **Slop scrub:** "0 hits" or list any flags caught + how rewritten
- **Why it works (X-specific):** 1-2 sentences explaining what
  makes this read as native X, not LinkedIn (this is the teaching
  layer for a newbie).
- **One alt hook** the user can swap in.

For threads, output every tweet in its own code block, char-counted
individually. Note the **hook tweet must work standalone** before
moving on.

Default output: 1 solo tweet + 1 alt solo tweet from a different
hook pattern. If the brief asks for a thread, deliver the thread
plus 1 solo tweet variant (in case the thread idea works better as
a single tweet).

Do **not** add commentary like "Hope this works!" or "Let me know
if you want changes." Just the drafts + metadata.

---

## Content graph (close the loop)

X posts written here land in `content/posts/` and feed the content
knowledge graph (`content/CONTENT-WIKI.md`). Many X posts repurpose a
longer original that is already a node.

**Before drafting:** open the relevant note in `content/concepts/` and
build on its canonical lines instead of starting blank.

**After the post is saved:** add it to the concept's `## Appears in`
(mark `(X)` in the angle), create a note if the idea is genuinely new,
update any `content/entities/` or `content/mocs/` it touches, and append
to `content/log.md`. Edges live in the concept notes (Obsidian backlinks
are automatic), so don't edit the post body. Pure repurposes of a post
already in the graph can skip this.

## Optional X source packet

If the brief depends on what is currently working on X and the
workspace has OpenClaw, ask for an approval-gated TweetClaw packet
before drafting:

```
Use @xquik/tweetclaw to collect public X posts about "<topic>" from the
last 7 days. Return post URLs, author handles, timestamps, text, and
visible engagement metrics only. Do not draft, schedule, publish, reply,
or follow anyone.
```

Use the packet as evidence, not as voice. Extract 3 concrete patterns:
the hook shape, the proof point, and the implied audience pain. Then
draft from this skill's hook and body rules, cite source URLs only in
internal notes, and keep user approval before any publishing step.

---

## Editing mode

If the user pastes a draft and asks to "make it sound less LinkedIn"
or "fix the slop":

1. Read the draft.
2. Run the slop scrub (§7). Flag every hit inline.
3. Rewrite to a hook + body shape from §3-§4.
4. Output the rewrite + a diff-style list of what changed and why.

---

## Repurpose context (when called from a repurpose orchestrator)

If invoked with a `source` reference (master content row, transcript
excerpt, or external URL):

1. Treat the source as the **insight bank**. Pick one hook / data
   point / hot take · don't rephrase the whole thing.
2. Open with the punch (a number, a contrarian line, a one-word setup),
   not with "I just published a webinar." X has zero patience for
   self-promo openers.
3. If the source is rich (multi-step framework, breakdown), prefer a
   thread. If it's a single insight, prefer a solo tweet.
4. Soft-reference the master only if it earns the slot (e.g., a thread
   tail with "full breakdown: <link>") · don't bolt it on otherwise.
5. Output the draft as usual. The orchestrator handles creating the
   tracking row and pasting `Source: <URL>` at the top of the page
   body · don't include that line yourself.

---

## Cadence guidance (when user asks)

If the user asks "what should I post today?" or "how often should I
tweet?", point them at `culture-brief.md` §6 (3-5 posts/day under 1k
followers, 70/30 reply-to-original ratio, Tue-Thu mornings for B2B
threads, pin a thread, don't quit at month 2).

Do not write a daily content calendar inside this skill. Drafting
is per-tweet. Strategy is in `culture-brief.md`.

---

## Reference files

- `reference-corpus.md`. **Voice anchor.** Top 15 tweets per
  reference creator (Romàn, Mich, Alex), pulled from the X API and
  sorted by weighted engagement. Re-read before drafting if you've
  been off-task. Refresh quarterly with the curl command at the
  bottom of this file.
- `culture-brief.md`. **Platform rulebook.** What X rewards / kills,
  voice register, cadence, reference-account stylistic reads.
  Pointer here when the user asks platform questions.
- This `SKILL.md`. Drafting workflow + hook/body/CTA patterns +
  slop blacklist.

**Important:** Your LinkedIn corpus (e.g.
`<YOUR_LINKEDIN_CORPUS_PATH>`) is **not** a voice source for X.
The two platforms are different games. Don't import LinkedIn voice
fingerprints (the `:)` smiley, `[1] [2]` walking-CTAs, "Lead Gen
Bros", `→` heavy bullets) into X drafts. Your default lane on X
starts closest to @itsalexvacca's operator-with-receipts register,
with seasoning from @MichLieben's self-roast and @romanbuildsaas's
bare-metric format. **Default voice anchors. You can swap or weight
differently** as you find your own taste over time.

---

## Refresh the reference corpus

Run quarterly. Updates `reference-corpus.md`.

```bash
# Requires X API v2 bearer token in env as <YOUR_X_BEARER_TOKEN>
# e.g. export X_BEARER_TOKEN=AAAA...

# user IDs (cached from initial setup):
# romanbuildsaas: 1893653481858433024
# MichLieben:     512156315
# itsalexvacca:   859850213015597056

for uid in 1893653481858433024 512156315 859850213015597056; do
  curl -s "https://api.twitter.com/2/users/${uid}/tweets?max_results=100&tweet.fields=public_metrics,created_at&exclude=retweets,replies" \
    -H "Authorization: Bearer ${X_BEARER_TOKEN}" \
    -o /tmp/x_${uid}.json
done
```

Then sort by `like_count + 3*retweet_count + 2*reply_count + 3*quote_count`,
pick top 15 per creator (filter URL-only tweets), and overwrite
`reference-corpus.md` keeping the same shape.
