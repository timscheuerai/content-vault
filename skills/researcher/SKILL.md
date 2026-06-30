---
name: researcher
description: The single idea-generation pipeline for marketing content. Three input modes converging on Notion Status=Idea rows. Trend scan (X + LinkedIn creators + topic search) finds what's hot in the world. Performance scan (your own published rows + their engagement metrics) finds what's working for you so you can double down. Customer scan (HUMAN NOTES DB user-interview transcripts) finds the words, pains, and themes from real customer conversations. Hybrid mode runs all three, dedupes, and outputs a balanced backlog. Use when asked to "find content ideas", "what's working", "what's hot", "what are customers saying", "research", "scan trends", "give me ideas for the week", "/researcher", or proactively when the Notion Idea queue is empty.
---

# researcher

The single discovery pipeline. Three idea sources, one Notion output.
Use this instead of separate /performance-check or /listening skills ·
they're folded in as modes here.

## When to use

Trigger on:
- "Find me content ideas"
- "What's hot on X / LinkedIn"
- "What's working for me"
- "Pull from my user interviews"
- "What are customers saying"
- "Scan the GTM space"
- "Give me ten posts to write next week"
- User explicitly types `/researcher`
- Your Notion Content DB has < 5 rows in `Status = Idea` (proactive)

Skip for:
- Verbatim repurposing of one specific post (use `/repurpose`)
- Drafting a single post (use `/linkedin-copywriter` or `/x-copywriter`)
- Scraping arbitrary websites (this skill is X + LinkedIn + Notion only)

## Modes

### 1. Trend scan · "what's hot in the world"

Pull recent posts from a curated list of creators on X +
LinkedIn (account scan) or search by keyword (topic scan). Rank by
engagement. Surface the themes worth riffing on.

Best for: weekly idea injection, knowing what's resonating broadly.
Risk: noisy, off-niche topics if not filtered.

### 2. Performance scan · "what's working for me"

Pull your own published rows from the Notion Content DB. Fetch
engagement metrics from LinkedIn (Unipile) and X (X API). Rank by
engagement. For top performers, generate **double-down ideas**:
follow-ups, deeper dives, contrarian counter-takes, variations.

Best for: amplifying signal you already have. The most leveraged
mode because it's grounded in proof.

### 3. Customer scan · "what real customers say"

Query the HUMAN NOTES DB for recent user-interview / external-meeting
rows. Read the transcripts. Extract pain points, direct quotes (use
customer language verbatim), and recurring themes across multiple
interviews. Generate angles tied to those.

Best for: sharp pain-point posts, customer-quoted content, lead-
magnet topics that solve real problems. The most original mode
because it draws on private signal nobody else has.

### 4. Concept scan · "extend your own canon"

Read the content knowledge graph in `content/concepts/` and
`content/mocs/` (see `content/CONTENT-WIKI.md`). Two moves:
- **Extend a thread.** For a high-value concept or an open MOC arc,
  propose the next beat: the unwritten angle, the new proof point, the
  counter-take, the deeper dive. Ground it in the concept's existing
  canonical lines so the new post compounds the old ones.
- **Find the gaps.** Surface thin concepts (low `appears_in`) that
  deserve more, and recurring ideas in recent posts that have no concept
  note yet (candidates for a new node).

Best for: making content compound instead of restart. The most on-brand
mode because it builds on your own canon, not the feed. (If the graph is
still empty, skip this mode until you've published a few posts.)

### 5. Hybrid (recommended for weekly runs)

Run all four. Dedupe. Output a balanced backlog: 3 trend ideas, 3
performance double-downs, 2 customer-pain ideas, 2 concept extensions
(or whatever ratio makes sense given recency). When you create an idea
that extends a concept, note `Extends: [[concept-slug]]` on it so the
link exists from the Idea stage. See `content/CONTENT-WIKI.md`.

## Workflow

### 1. Decide mode + scope

Ask the user (skip if already specified):
- Mode: trend / performance / customer / hybrid (default: hybrid)
- Time window: default 7 days for trends, 30 days for performance,
  60 days for customer
- How many idea cards to create: default 10, max 25

### 2. Fetch from each active source

#### Trend scan · X

```bash
source ./.env
mkdir -p /tmp/researcher

# Account scan: per cached user ID in seed-accounts.md
for uid in 1893653481858433024 512156315 859850213015597056; do
  curl -s "https://api.twitter.com/2/users/${uid}/tweets?max_results=100&tweet.fields=public_metrics,created_at,entities&exclude=retweets,replies" \
    -H "Authorization: Bearer ${X_BEARER_TOKEN}" \
    -o /tmp/researcher/x_${uid}.json
done

# Topic scan: keyword search (last 7d, English, exclude retweets)
TOPIC="AI GTM agent"
curl -s --get "https://api.twitter.com/2/tweets/search/recent" \
  --data-urlencode "query=${TOPIC} -is:retweet lang:en" \
  --data-urlencode "max_results=50" \
  --data-urlencode "tweet.fields=public_metrics,created_at,author_id,entities" \
  -H "Authorization: Bearer ${X_BEARER_TOKEN}" \
  -o /tmp/researcher/x_topic.json
```

X engagement score:
```
score = like_count + 3*retweet_count + 2*reply_count + 3*quote_count
```

If the workspace runs OpenClaw, you can also collect an approval-gated
X source packet with TweetClaw before clustering:

```
Use @xquik/tweetclaw to search recent X posts for "<topic>".
Return only public post URLs, author handles, timestamps, text, and
visible engagement metrics. Save the packet to /tmp/researcher/x_sources.md.
Do not draft, schedule, publish, reply, or follow anyone.
```

Use this packet as additional trend evidence. Keep only sources inside
the chosen time window, dedupe against X API results by post URL, and
carry the source URL into the Notion idea body.

#### Trend scan · LinkedIn

```bash
source ./.env

for pid in <YOUR_LINKEDIN_PROFILE_ID>; do
  curl -s "https://${UNIPILE_DSN}/api/v1/users/${pid}/posts?account_id=${UNIPILE_ACCOUNT_ID}&limit=20" \
    -H "X-API-KEY: ${UNIPILE_API_KEY}" \
    -H "accept: application/json" \
    -o /tmp/researcher/li_${pid}.json
done
```

LinkedIn engagement score:
```
score = reaction_counter + 3*comment_counter + 5*share_counter
```

If a seed account in `seed-accounts.md` has profile ID `TBD`, resolve
it on first use:

```bash
curl -s "https://${UNIPILE_DSN}/api/v1/users?account_id=${UNIPILE_ACCOUNT_ID}&keyword=<name>&limit=5" \
  -H "X-API-KEY: ${UNIPILE_API_KEY}"
```

Pick the right profile, copy the ID into `seed-accounts.md` (commit),
continue.

#### Performance scan · your own content

Step 1: query the Notion Content DB for your recent Published rows.

```
Use mcp__claude_ai_Notion__notion-search with:
  data_source_url: collection://<YOUR_NOTION_CONTENT_DB_ID>
  query: ""
  page_size: 25
  filters: { created_date_range: { start_date: "<30d ago>" } }
```

Filter to rows where `Status = Published` and `Live URL` is non-empty.

Step 2: fetch metrics per Live URL.

For LinkedIn URLs (pattern `linkedin.com/posts/...`):

```bash
# Fetch your own posts (your profile ID is cached)
curl -s "https://${UNIPILE_DSN}/api/v1/users/<YOUR_LINKEDIN_PROFILE_ID>/posts?account_id=${UNIPILE_ACCOUNT_ID}&limit=50" \
  -H "X-API-KEY: ${UNIPILE_API_KEY}" \
  -H "accept: application/json" \
  -o /tmp/researcher/li_self.json
```

Match each Notion row's Live URL against the response · use the
post's `reaction_counter`, `comment_counter`, `share_counter`.

For X URLs (pattern `x.com/<handle>/status/<id>`):

```bash
# Extract tweet IDs from URLs
TWEET_IDS="1234567890,2345678901,..."  # comma-separated
curl -s --get "https://api.twitter.com/2/tweets" \
  --data-urlencode "ids=${TWEET_IDS}" \
  --data-urlencode "tweet.fields=public_metrics,created_at" \
  -H "Authorization: Bearer ${X_BEARER_TOKEN}"
```

If your X user ID is not yet cached in `seed-accounts.md`, the tweet
lookup-by-ID still works without it · we just can't filter to your
own without the ID. Note as soft-blocker if it limits the run.

Step 3: rank and pick.

Sort by engagement score (X formula above for tweets, LinkedIn
formula for LI posts). Top 5 are double-down candidates. Bottom 3
are flop diagnostics (what didn't work · note for avoidance, not for
ideation).

Step 4: generate double-down angles.

For each top-5 row:
- **Follow-up**: a continuation post answering "and then what
  happened?" or "the next step after X"
- **Deeper dive**: pick one bullet from the original and make it the
  whole post
- **Counter-take**: argue the opposite of the original (works if
  the original was a popular take · creates contrast)
- **Format flip**: original was text → carousel; original was post → thread; etc.

Pick whichever fits the source. Multi-angle per row is fine if rich
material exists.

#### Customer scan · HUMAN NOTES DB

Query the user-interview rows.

```
Use mcp__claude_ai_Notion__notion-search with:
  data_source_url: collection://<YOUR_NOTION_HUMAN_NOTES_DB_ID>
  query: ""
  page_size: 25
  filters: { created_date_range: { start_date: "<60d ago>" } }
```

Filter the response to `Category in ("User Interview Meeting",
"External Meeting")`. Skip Co-Founder Meeting, Dev Notes, Reading
List, Application categories · those aren't customer signal.

For each surviving row, fetch the page body via
`mcp__claude_ai_Notion__notion-fetch` with the row ID. The body
contains the transcript / notes.

For each interview, extract:
- **Pain points**: 2-4 bullets describing what's broken in the
  customer's world (in their words, not yours)
- **Direct quotes**: 1-3 quotable lines (verbatim · with attribution
  to interview date and customer if not under NDA)
- **Recurring themes**: themes that show up across multiple
  interviews (note which · a theme in 1 interview is anecdote, in
  3+ it's signal)

For each recurring theme (3+ occurrences), generate an angle:
- The pain stated as a question you have the answer to
- A framework that resolves the pain
- A contrarian take on common-but-wrong solutions in that space
- A customer-quote post (the verbatim line as the hook)

### 3. Filter (all modes)

- Drop posts older than the time window
- Drop banned-signal posts (see `seed-accounts.md` § "Banned signals")
- Drop URL-only / image-only posts with no text body
- Drop posts under the engagement floor (trend mode only · 50 likes
  on X · 100 reactions on LinkedIn)
- For customer scan: drop interviews under 5 minutes (likely no-shows
  or aborted) and skip the ones marked "private · do not use"

### 4. Cluster + angle (all modes)

Read all surviving inputs. Group by theme · expect 5-10. For each
theme, pick the strongest representative (highest engagement for
trends, top performer for performance, most-quoted for customer)
and write:

- **Angle**: a one-sentence hook you could use, in your voice (terse,
  contrarian, concrete, direct, no hype)
- **Why it's hot / working / real**: one sentence on why this matters
- **Suggested Pillar**: pick one of the six (`Building in Public`,
  `Educational / Tactical`, `Personal`, `Memes`, `Promotional`,
  `Trend Insights`)
- **Suggested Format + Channel**: usually `Text` on `LinkedIn` or `X`
  · sometimes `Long-form Article` for richer themes · sometimes
  `Lead Magnet` for customer-pain frameworks

### 5. Create Notion rows

For each idea card, call
`mcp__claude_ai_Notion__notion-create-pages` with data source
`<YOUR_NOTION_CONTENT_DB_ID>`. Properties:

- **Title**: the one-sentence angle (max ~80 chars)
- **Status**: `Idea`
- **Pillar**: suggested multi-select (single value usually)
- **Format**: suggested
- **Channel**: suggested

Page body, branched by mode:

#### Trend mode body
```
Source: <original post URL>
Mode: trend
Author: <handle / name>
Engagement: <metrics line>
Window: <date range>

— Original post —
> <quoted post text>

— Why this is hot —
<one sentence>

— Your angle —
<one to three sentences in your voice>
```

#### Performance mode body
```
Source: <your published Notion row URL>
Mode: performance · double-down
Original metrics: <metrics line>
Pillar of original: <pillar>

— Original post —
> <quoted post text>

— Why this performed —
<one sentence on what worked>

— Double-down angle —
<one to three sentences · what to write next that builds on the win>
```

#### Customer mode body
```
Source: <interview Notion row URL · plural if theme spans rows>
Mode: customer · pain-point
Interview date(s): <date(s)>
Customer(s): <names if not under NDA, "Customer A / B / C" otherwise>
Theme recurrence: <count> interviews

— Customer quote(s) —
> "<verbatim line>"
> "<verbatim line>"

— The pain —
<one to two sentences in the customer's framing>

— Your angle —
<one to three sentences in your voice · what to say about this pain>
```

### 6. Report back

One-line summary by mode plus the Notion URLs of created rows.
Example:

```
Created 10 ideas (4 trend, 3 performance double-down, 3 customer-pain).
Pipeline view: <link>

Trend
  - <title> → notion.so/...
  - <title> → notion.so/...
  ...
Performance double-down
  - <title> (riff on "<original>" · 47 reactions) → notion.so/...
  ...
Customer pain
  - <title> (3 interviews · A, B, C) → notion.so/...
  ...
```

If any mode soft-blocked (e.g. X user ID missing), mention it in the
report.

## Defaults

| Knob                        | Default            |
| --------------------------- | ------------------ |
| Mode                        | Hybrid             |
| Time window (trend)         | 7 days             |
| Time window (performance)   | 30 days            |
| Time window (customer)      | 60 days            |
| Cards to create             | 10                 |
| Trend / performance / customer ratio (hybrid) | 4 / 3 / 3 |
| X account scan              | 3 cached creators  |
| LinkedIn account scan       | Your profile + curated list as IDs are resolved |
| Topic seeds                 | from `seed-accounts.md` |
| Engagement floor (X trend)  | 50 likes           |
| Engagement floor (LI trend) | 100 reactions      |
| Customer category filter    | `User Interview Meeting` OR `External Meeting` |

## Don'ts

- **Don't paraphrase the original post into your voice as the Title.**
  The Title is the angle you would write · derived from the post, not
  copied. The original post text goes in the page body.
- **Don't surface 30 ideas.** Cap at 10-15 default. More creates
  fatigue, not optionality.
- **Don't skip the engagement floor on trend mode.** Low-engagement
  posts on these topics are usually slop, even from good accounts.
- **Don't auto-spawn drafts.** Status=Idea means just-an-idea.
  Drafting is a separate step.
- **Don't pollute the DB with duplicates.** Before creating, do a
  quick search of recent Idea rows for the same theme. If a similar
  idea exists, append the new source as another bullet in the
  existing row's body instead of creating a duplicate.
- **Don't fabricate engagement numbers.** If the API call fails or
  returns empty, say so · don't fill in plausible-looking metrics.
- **Don't quote customers under NDA verbatim.** If the interview
  notes mark a section private / off-record, paraphrase it in the
  pain framing and skip the direct quote. When in doubt, ask.
- **Don't crawl outside X + LinkedIn + Notion.** This skill stays
  scoped. For blog / podcast / YouTube discovery, use `WebSearch`
  separately.
- **Don't over-double-down on one performance winner.** If the same
  post drives 5 angles, you'll oversaturate one theme. Cap at 2
  double-downs per source row.

## See also

- Notion Content DB data source: `<YOUR_NOTION_CONTENT_DB_ID>`
- Notion HUMAN NOTES DB data source: `<YOUR_NOTION_HUMAN_NOTES_DB_ID>`
- Seed accounts + topic list: copy
  [`seed-accounts.md.example`](./seed-accounts.md.example) to
  `seed-accounts.md`
- API auth env: `./.env` · `<YOUR_X_BEARER_TOKEN>` (X) · `<YOUR_UNIPILE_DSN>`,
  `<YOUR_UNIPILE_API_KEY>`, `<YOUR_UNIPILE_ACCOUNT_ID>` (LinkedIn)
- Downstream skills: `/linkedin-copywriter`, `/x-copywriter`,
  `/repurpose`, `/lead-magnet-creator`, `/long-form`,
  `/youtube-script`
