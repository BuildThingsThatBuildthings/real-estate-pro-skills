---
name: post-bridge-schedule
description: "End to end posting pipeline for Post Bridge. Takes a folder of finished video and carries it to verified scheduled records: inventory, transcription, claim verification, brand voice, analytics-derived posting windows, ramp planning, collision detection, per-channel captions, image card generation, preflight lint, approval gate, creation, and post-create repair. Channel set, cadence and copy rules all come from config. Use when scheduling a batch of finished content, filling or ramping a posting calendar, auditing schedule health, or repairing collisions and duplicate destinations. Triggers on \"/post-bridge-schedule\", \"schedule this batch\", \"fill the calendar\", \"ramp the schedule\", \"post this content\", \"how full is the calendar\", \"check the schedule\", or a folder of finished video dropped for posting."
---

# Post Bridge posting pipeline

## The only way AIA/BT2 posts are created

**This is the ONLY way AIA/BT2 posts are created. Callers: social agent, video agent.**
(Ryan, 2026-09-27.) Posts are created only by `scripts/create_batch.py create batch.json`,
which runs the full lint first. The social agent
(`ops/social-engine/skills/social-agent`, re-timing only) and the video agent
(`/Users/ryan/video_agent`) are the only two schedulers. Every other path (the old outbox
feeder, `aia-deliverability-scheduler`, `backfill.mjs`, ad-hoc connector `create_post`) is
retired, and a global PreToolUse hook (`~/.claude/hooks/postbridge-nine-guard.mjs`) blocks
direct connector `create_post` for AIA/BT2.

Roster law, enforced by lint check 1: every AIA/BT2 post targets all nine roster accounts
(72366, 72367, 72370, 75843, 75846, 75850, 75841, 75844, 75848) with a non-empty caption per
account, all nine captions pairwise distinct (case and whitespace ignored), and a YouTube
title. The only exception is a LinkedIn-only post that targets 72370 and/or 80927 alone.
A posting context that drops a roster account fails the lint; it never shrinks the fan-out.

## Watcher value — required in this workflow

Every audience-facing video/asset must earn attention through **hook → retain → reward**: a compelling spoken/visible opening, concrete reasons to continue, and the actual promised payoff. Follow the [watcher-value contract](/Users/ryan/video_agent/docs/WATCHER_VALUE_CONTRACT.md) and record source-linked delivery evidence. Empty provocation, withheld answers, decorative padding and unsupported claims fail. Valid JSON alone cannot establish semantic or audiovisual quality.

Before uploads or scheduling writes, require current approved final-file review for hook, retention and fulfilled promise, with matching media SHA and caption claims. Unreviewed, missing-value or rerendered-with-stale-review assets remain unscheduled. Existing live Post Bridge reconciliation, duplicates, guarded transport, cadence and receipts remain authoritative.

A folder of finished video goes in. Verified scheduled records come out.

Everything specific to a person or a business lives in `config/`. Nothing is hardcoded.

## Client workspace and posting authority — mandatory before any write

Content generation, Drive delivery, a paid posting entitlement, a draft request, or a file in
`approved/` does not by itself authorize a Post Bridge upload, draft, schedule, repair or publish.
Client content belongs only in that client's verified Post Bridge workspace. Never use Ryan's
personal workspace for client content unless Ryan explicitly authorizes that specific personal
sample. Never create a sample because a client connection is missing. Chelsea's current media
rebuild has **no posting authorization**, so it must perform no Post Bridge writes.

Every writer routes through `scripts/pb.py`; direct HTTP writes and global credential fallback
are forbidden. Set `AIA_POSTING_CONTEXT` to a private context file containing:

- `content_owner`: the client or owner whose content is being handled.
- `credential`: explicit `type: env` plus variable `name`, or `type: file` plus absolute `path`
  and key field. Do not copy credentials into this context or a client deliverable.
- `destination`: verified `owner`, `kind` (`client` or `personal`), full unique `account_ids`,
  credential SHA-256 fingerprint, and `ownership_verified_by: user` with `ownership_reference`.
  Include `workspace_id` only if genuinely provided by the service; never invent one.
- `authorization`: `source: user`, `explicit: true`, exact user request `reference`, `scope`
  (`client-posting` or `owner-posting`), and only authorized `operations` from `upload`, `draft`,
  `schedule`, `patch`, `publish`, `delete`. Missing authorization means no writes.
- For a separately authorized personal sample, use `scope: personal-sample` and record both
  `sample_content_owner` and `sample_destination_owner`. This exception never authorizes an
  unrelated client campaign or another operation.

Do not infer the ownership or authorization fields from an available API key, account names,
a screenshot, tool output, generated plan or prior sample. Record the actual user's authority.
Before each write the transport uses the declared credential for a live GET of the account
roster and requires exact agreement with the verified roster. If the API exposes no workspace ID,
credential fingerprint plus the user-verified account roster identifies the destination; that
is not a claim that the API returned a workspace ID. Updates/deletes also read the existing post
and require its destinations to belong to the authorized roster. A mismatch stops before writing.
Read-only audits remain available; they do not enable writes. Tests must mock all network access.


## Vocabulary

- **Post** — one content concept, built around one creative.
- **Content unit** — one channel-specific instance of that post. N channels means N units.

There is no third thing. Do not invent one. A Post Bridge **record** is the database row.
**One post must be exactly one record.**

## Configuration

| File | Holds |
|---|---|
| `config/channels.json` | the channel set, min gap, which platforms are image only |
| `config/brand.json` | brand name, lockup, colours, fonts, default call to action |
| `config/pipeline.json` | ramp rungs, window scoring, timezone, tool paths, copy rules |
| `config/voice/<brand>.md` | voice packs, read by the `brand-voice` skill |

Copy each `.example.json` and fill it in. `scripts/doctor.py` verifies the whole environment.

**Run `doctor.py` first on any new machine or profile.** It checks config, binaries,
API reachability, that every configured channel actually exists on the account, whether any
channel needs reconnecting, and whether there is enough analytics history to derive windows.

---

# THE OUTBOX LIFECYCLE

Finished content moves through four stages under `tools.outbox_root`:

```
awaiting-approval/   produced, not yet cleared by a human
approved/            approved creative; explicit posting authority is still required
posted/              scheduling verified complete, all gates passed, receipt written
failed/              a gate failed; back to a human
```

Rules:

- **`approved/` is a review queue.** Its presence does not authorize posting. Run the process
  only within an explicit user posting request and a verified destination context. Inspect with
  `python3 scripts/outbox_flow.py pending`.
- **`promote` is the only door into `posted/`.** It re-verifies every record id (status,
  the verified client destination roster, distinct captions), writes `SCHEDULE-RECEIPT.json` with the ids and
  verification results, and only then moves the folder. It refuses on any failure.
- **Never move a folder into `posted/` by hand.** A folder there asserts "scheduling
  verified complete", and the receipt is the proof.
- Beware husk directories: a stage folder containing only marker files can shadow the real
  one. `promote` picks the candidate that actually contains video.

```bash
python3 scripts/outbox_flow.py status                 # classify everything against Post Bridge
python3 scripts/outbox_flow.py pending                # what the human has queued
python3 scripts/outbox_flow.py organize [--yes]       # one-time reorg helper
python3 scripts/outbox_flow.py promote <project> --ids <id,...> [--yes]
```

---

# THE PROCESS

## Step 0. Environment

```bash
python3 scripts/doctor.py
```

Do not continue past a failing check.

## Step 1. Inventory the batch

```bash
for f in *.mp4; do ffprobe -hide_banner -loglevel quiet \
  -show_entries format=duration -select_streams v:0 \
  -show_entries stream=width,height -of csv=p=0 "$f"; done
```

Establish how many **posts** exist. Alternate cuts of the same concept are not separate
posts. State the count before continuing.

Then check eligibility per platform. Two constraints decide the shape of every record:
- Platforms in `video_required_platforms` need a video.
- Platforms in `image_only_platforms` reject video entirely and need a still.

## Step 2. Transcribe

```bash
tools/transcribe.sh <batch folder>
```

Captions written from filenames invent claims nobody made. This step is not optional.

`ffmpeg` consumes stdin inside a read loop and truncates filenames. `-nostdin` and
`</dev/null` are mandatory. The tool already does this.

## Step 3. Verify claims

Every statistic in a transcript gets checked before it reaches a caption. Research it and
credential it with a real source rather than hedging or dropping it. If the verified figure
differs from what was said on camera, **use the verified figure with attribution** and say
so out loud.

## Step 4. Load brand voice

Use the `brand-voice` skill. Load the pack for each brand in the channel set before writing
anything. Channels map to brands through the `brand` field in `config/channels.json`.

One creative, written once per audience. A post going to two brands is written twice, in two
voices, not copied.

`config/voice/_RULES.md` outranks any individual pack. When they disagree, the shared rules
win and the conflict gets flagged so one of the two is fixed.

## Step 5. Derive posting windows from your own analytics

```bash
python3 scripts/windows.py report     # hour and weekday performance, ranked
python3 scripts/windows.py ladder     # the daypart slot ladder, per rung and in full
```

**Never hardcode slots.** `windows.py` scores each hour on **medians, never means**: median
views per platform on view-reliable platforms, median likes on like-signal platforms. Each
platform's median is normalized by its own best allowed hour; an hour scores
`view_weight x mean(normalized view medians of the platforms with enough posts there)
x sqrt(those platforms / view platforms with enough posts at any hour)
+ like_weight x normalized median likes`. One viral post cannot move an hour, and an hour
backed by one platform cannot outrank a three-platform hour purely by averaging. It drops hours
with too little evidence, excludes the configured forbidden hours, and emits the ladder.
Re-derive every run. The ranking moves as the account grows.

**Posting window: 06:00 to 22:00 Central, inclusive** (`windows.earliest_start` = "06:00",
`windows.latest_start` = "22:00"). The last post may start at exactly 22:00; nothing starts
after 22:00 (22:15 is refused) or before 06:00 (05:45 is refused). Ladder slots are HH:15,
except hour 22, whose slot is exactly 22:00. `windows.forbidden_hours` (0-5 and 23) only keeps
overnight hours out of scoring. `free_slot`, the `create_batch.py` lint and `repair.py` all
enforce the window through `windows.in_window`.

**Lead time: 1 hour** (`approval.lead_hours` = 1). A new post may be placed as soon as one
hour from now.

**Spread across the day, never cluster.** Ranking hours globally put every post before 4pm, so
the ladder is built per **daypart** (CT): **morning 06-11, afternoon 12-16, evening
17:00-22:00** (the evening may use the 22:00 slot; an hour-22 score maps to slot "22:00").
Each daypart ranks its own hours by the score above. The ladder is best morning, best
afternoon, best evening, then round-robin the next-best remaining hour of each daypart
(morning, afternoon, evening, ...) until 8 slots; a daypart that runs out is skipped. So rung 3
is exactly one slot per daypart. A daypart with no scored hour still gets one slot: its hour
with the most posts on record, else the fixed default 09 / 13 / 19. That one slot per empty
daypart is the only slot that does not come from a score. The lint's allowed set
(`create_batch._allowed_ct`), the planner's fallback ladder (`schedule_engine.LADDER`) and
`repair.py` all use this same full daypart order (`windows.ladder_order`).

**Source.** When `windows.warehouse_url` is set, `windows.py` first asks the War Room warehouse
verb `social.windows` (POST, header `x-ops-key` from `$WARROOM_OPS_KEY` or the keychain item
`warroom-ops-key`) and prints `WINDOWS SOURCE: warehouse (...)` on stderr. If that call fails,
has no windows, or they are older than `windows.warehouse_max_age_hours` (48), it computes the
same medians live from Post Bridge analytics and prints a loud
`WINDOWS SOURCE: live Post Bridge fallback (warehouse unavailable: <reason>)`.

What it already accounts for:
- Post Bridge syncs analytics for a **subset of platforms only**. Configure which in
  `windows.view_reliable_platforms`. Anything outside that set cannot inform timing, and on a
  typical set that is a third of the channels.
- Some platforms report 0 views for image posts. Those contribute through likes instead.
- Hours below `min_records_per_hour` are noise and are excluded.

## Step 6. Read the calendar and the ramp

```bash
python3 scripts/schedule_engine.py status
```

`posts per day = content units that day / number of channels`.

### The ramp

```
for rung in ramp.rungs:                  # current: [5] -> 5 posts every day
    fill block 1 to rung                 # block_days 30, horizon_blocks 2 = next 60 days
    then fill block 2 to rung
    advance only when BOTH blocks sit at rung
both blocks at the top rung -> open block 3, restart at the first rung
```

**Current cadence: 5 posts per day, every day, for the next 60 days** (`ramp.rungs` = [5]).
Existing scheduled records **count toward the 5**, in full-post equivalents: a record on all
9 channels is one post, a single-account record is 1/9. A day that already holds 5 gets
nothing new.

**Where each day's posts go.** The next post on a day goes to that day's **emptiest daypart**
(counting what is already scheduled there, same units), ties broken morning, afternoon,
evening; inside the daypart, its best slot that clears the spacing rules. On an empty day
5/day is best morning, best afternoon, best evening, next morning, next afternoon. A day that
already has 10:23 / 12:41 / 14:57 gets its remaining two in the evening and in the morning
clear of 10:23, never a third afternoon.

Never skip a rung. Never fill block 2 ahead of block 1. **A rung is a count target, not a
slot whitelist** — a blocked slot falls back to the rest of **its own daypart** first, then to
the other dayparts, rather than skip the day. Stop when media runs out and report the exact
remaining gap in posts.

## Step 7. Plan placements, with collision detection

```bash
python3 scripts/schedule_engine.py plan --count N
python3 scripts/repair.py scan
python3 scripts/repair.py fix --all
```

**Minimum gap between two posts on the same account** is `min_gap_minutes` (45, per the AIA account registry). Posts on
**different** accounts only need `min_global_stagger_minutes` (pipeline.json, default 10), so
two records never land on the same minute. Both are checked against the live calendar **plus**
the pending batch, never the batch alone, in `schedule_engine.free_slot`, the lint and
`repair.py`.

A post from this pipeline targets every configured channel as one record, so for it "the same
account" is every channel: any record on any of those channels within 45 minutes still blocks
the slot. The per-account rule only frees slots for records that target a subset of accounts.

Also reject any record listing the same account twice. That causes double posting and does
occur in the wild.

`repair.py fix` moves the record with fewer destinations in a colliding pair, so the wider
post keeps its slot.

## Step 8. Upload media

```bash
python3 scripts/pb.py upload --file <path>
```

Record slug, kind, byte size and media id to a manifest, and **verify every uploaded size
against source**.

Within the same explicitly authorized workspace, byte-identical cuts may reference one media ID. Never reuse media IDs across client workspaces. A
library will otherwise accumulate many times more objects than it has posts.

## Step 9. Build the still for image-only platforms

```bash
node tools/make-card.mjs <mediaId|file> <out.jpg> "HEADLINE" "subline" [seek]
```

Crops the **upper portion** of a vertical frame, burns the headline onto the brand panel with
the accent rule and lockup from `config/brand.json`.

**Never center crop a raw video frame.** On a vertical talking-head shot the middle band is
table and legs and the result is unusable. Pass an empty headline for sources that are
already designed cards.

Build a contact sheet and actually look at it before uploading:
```bash
ffmpeg -nostdin -pattern_type glob -i "gmb/*.jpg" -vf "scale=340:340,tile=5x5" -frames:v 1 -y sheet.jpg
```

## Step 10. Write one caption per channel

All distinct, grounded in the transcript. Plus, where the platform supports it:
- a **video title**, within the platform's limit
  - **YouTube title and description:** written only from this clip's own transcript, never from the source video's old metadata, and with no hashtags (including `#shorts`).
  - Each claim in the title must be something the clip says. Don't use a model, product name or number the clip doesn't say.
  - If the `youtube-optimizer` skill is installed, run its `gate.py package` on the YouTube copy before the approval gate.
- a **first comment** for any link on platforms that strip URLs from the body
- a **call to action** for the image-only platform
- a **cover frame** for vertical video surfaces

Assemble to `batch.json`:
```json
{"posts":[{"slug":"...","scheduled_at":"...Z","video_media_id":"...","gmb_media_id":"...",
           "youtube_title":"...","twitter_first_comment":"...","gbp_cta_url":"...",
           "captions":{"<account_id>":"...", "...": "one per channel"}}]}
```

## Step 10b. Duplicate check — bytes and records only

Two levels, both about *the same asset shipping twice*:

1. **Byte level** — the exact file is already in the media library.
2. **Record level** — the same clip is already scheduled or posted as a different upload.

Also check the project's `distribution/` folder and any `INGESTED` markers, to rule out
another pipeline having already consumed the folder.

**There is no such thing as a concept collision. Do not invent one.**

Themes are supposed to repeat, vary, and overlap. Two posts making a similar argument days
apart is normal content, not a defect. Never move, delay, or hold a post because its idea
resembles another post's idea. **The only collision that exists is a time collision on the
same account** (Step 7, `min_gap_minutes`), plus the cross-account stagger.

If a batch is given a window and a count, every post lands inside that window. Do not
reduce the count and do not push posts outside the window for editorial reasons. Placement
is scheduling arithmetic, not an editorial opinion.

## Step 11. Preflight lint

```bash
python3 scripts/create_batch.py lint batch.json
```

All must pass:
1. destinations: for AIA/BT2, all nine roster accounts with a non-empty, pairwise distinct
   caption each and a YouTube title (LinkedIn-only posts on 72370/80927 are the sole
   exception); for any other profile, every configured channel present as a destination
2. no duplicate account id in the record
3. every caption distinct and non empty
4. video title set and within limit
5. image-only channel carries an image, not video
6. slot is in the derived allowed set
7. `min_gap_minutes` honoured against every existing and pending post on the same accounts,
   and `min_global_stagger_minutes` against every post on any account
8. every media id resolves and byte size matches source

Also lint the copy against `pipeline.captions`: hashtags, dashes, banned words.

## Step 12. Approval gate

Emit the dated table and **stop**.

| # | Date | Day | Local | UTC | Post | Headline |

Show at least one post's full caption set so the voice can be judged. Nothing is written
until a human has seen this.

Exception: the two authorized callers (social agent, video agent) run fully automated, with
no approval hold (Ryan, 2026-09-27). For them the lint is the gate: `lint` then `create`.

## Step 13. Create, verify, repair

```bash
python3 scripts/create_batch.py create batch.json
```

**A successful create does not mean the record is complete.** Observed: records created with
every caption intact and an empty destination list, which would publish to nothing. The
script re-reads every record after creation and repairs empties automatically.

Never trust a status code from this API. See `docs/post-bridge-api-notes.md`.

## Step 14. Postflight

```bash
python3 scripts/repair.py scan             # expect zero of everything
python3 scripts/schedule_engine.py status  # confirm the ramp moved, report residual gap
python3 scripts/pb.py results --post-id <id>
```

Then check analytics 48 to 72 hours after publish and feed it back into Step 5.

Publish failures cluster by platform and are usually **auth problems on the platform side**,
fixed by reconnecting the account in the Post Bridge dashboard, not in code. Report the rate
per account and move on. Do not attempt to repair credentials.

---

## Tools

| Script | Purpose |
|---|---|
| `scripts/doctor.py` | environment and configuration preflight |
| `scripts/pb.py` | Post Bridge client: accounts, upload, get, results, media |
| `scripts/windows.py` | derive posting windows (warehouse first, live analytics fallback) |
| `scripts/schedule_engine.py` | ramp state, collision audit, placement planning |
| `scripts/repair.py` | dedupe destinations, reschedule collisions, verified writes |
| `scripts/create_batch.py` | preflight lint, creation, post-create verification and repair |
| `tools/transcribe.sh` | batch transcription |
| `tools/make-card.mjs` | brand image card for image-only platforms |

## Companion skill

`brand-voice` loads the voice pack for each brand before any caption is written. This skill
depends on it.
