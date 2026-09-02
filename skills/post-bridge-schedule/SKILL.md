---
name: post-bridge-schedule
description: End to end posting pipeline for Post Bridge. Takes a folder of finished video and carries it to verified scheduled records: inventory, transcription, claim verification, brand voice, analytics-derived posting windows, ramp planning, collision detection, per-channel captions, image card generation, preflight lint, approval gate, creation, and post-create repair. Channel set, cadence and copy rules all come from config. Use when scheduling a batch of finished content, filling or ramping a posting calendar, auditing schedule health, or repairing collisions and duplicate destinations. Triggers on "/post-bridge-schedule", "schedule this batch", "fill the calendar", "ramp the schedule", "post this content", "how full is the calendar", "check the schedule", or a folder of finished video dropped for posting.
---

# Post Bridge posting pipeline

A folder of finished video goes in. Verified scheduled records come out.

Everything specific to a person or a business lives in `config/`. Nothing is hardcoded.

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
approved/            the human moved it here — that IS the scheduling trigger
posted/              scheduling verified complete, all gates passed, receipt written
failed/              a gate failed; back to a human
```

Rules:

- **`approved/` is a queue, not a folder.** When anything appears there, run THE PROCESS
  below on it. Check it at the start of any session with
  `python3 scripts/outbox_flow.py pending`.
- **`promote` is the only door into `posted/`.** It re-verifies every record id (status,
  nine destinations, distinct captions), writes `SCHEDULE-RECEIPT.json` with the ids and
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
python3 scripts/windows.py ladder     # the slot ladder per rung
```

**Never hardcode slots.** `windows.py` reads every analytics record, scores each hour by a
weighted blend of views on view-reliable platforms and likes on like-signal platforms, drops
hours with too little evidence, excludes the configured forbidden hours, and emits the
ladder. Re-derive every run. The ranking moves as the account grows.

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
for rung in ramp.rungs:                  # default 3, 5, 7, 8 posts per day
    fill block 1 to rung
    then fill block 2 to rung
    advance only when BOTH blocks sit at rung
both blocks at the top rung -> open block 3, restart at the first rung
```

Never skip a rung. Never fill block 2 ahead of block 1. **A rung is a count target, not a
slot whitelist** — when a preferred slot is blocked, fall down the ladder rather than skip
the day. Stop when media runs out and report the exact remaining gap in posts.

## Step 7. Plan placements, with collision detection

```bash
python3 scripts/schedule_engine.py plan --count N
python3 scripts/repair.py scan
python3 scripts/repair.py fix --all
```

**Minimum gap between two posts on the same channel** is `min_gap_minutes`. Checked against
the live calendar **plus** the pending batch, never the batch alone.

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

If two brand cuts are byte identical, upload once and reference one media id everywhere. A
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
same channel** (Step 7, `min_gap_minutes`).

If a batch is given a window and a count, every post lands inside that window. Do not
reduce the count and do not push posts outside the window for editorial reasons. Placement
is scheduling arithmetic, not an editorial opinion.

## Step 11. Preflight lint

```bash
python3 scripts/create_batch.py lint batch.json
```

All must pass:
1. every configured channel present as a destination
2. no duplicate account id in the record
3. every caption distinct and non empty
4. video title set and within limit
5. image-only channel carries an image, not video
6. slot is in the derived allowed set
7. minimum gap honoured against every existing and pending post
8. every media id resolves and byte size matches source

Also lint the copy against `pipeline.captions`: hashtags, dashes, banned words.

## Step 12. Approval gate

Emit the dated table and **stop**.

| # | Date | Day | Local | UTC | Post | Headline |

Show at least one post's full caption set so the voice can be judged. Nothing is written
until a human has seen this.

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
| `scripts/windows.py` | derive posting windows from live analytics |
| `scripts/schedule_engine.py` | ramp state, collision audit, placement planning |
| `scripts/repair.py` | dedupe destinations, reschedule collisions, verified writes |
| `scripts/create_batch.py` | preflight lint, creation, post-create verification and repair |
| `tools/transcribe.sh` | batch transcription |
| `tools/make-card.mjs` | brand image card for image-only platforms |

## Companion skill

`brand-voice` loads the voice pack for each brand before any caption is written. This skill
depends on it.
