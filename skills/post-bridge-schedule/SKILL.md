---
name: post-bridge-schedule
description: End to end productized posting pipeline for Ryan's AI Acceleration and Build Things That Build Things channels via Post Bridge. Takes a folder of finished video and carries it all the way to verified scheduled records: inventory, transcription, claim verification, brand voice, analytics-derived posting windows, ramp planning, collision detection, per-channel captions, GBP card generation, preflight lint, approval gate, creation, and post-create repair. Use when scheduling a batch of finished content, filling or ramping the calendar, auditing schedule health, or repairing collisions. Triggers on "/post-bridge-schedule", "schedule this batch", "fill the calendar", "ramp the schedule", "post this content", "how full is the calendar", "check the schedule", or a folder of finished video dropped for posting.
---

# Post Bridge — productized posting pipeline

Composes with the `post-bridge` skill, which owns auth, the CLI and raw API calls.
This skill owns the **process**: what a post is, where it goes, when it fires, and how
you prove it landed.

## Vocabulary — use these words, no others

- **Post** — one content concept, built around one creative.
- **Content unit** — one channel-specific instance of that post. 9 channels = 9 units.

There is no third thing. Never invent one. A Post Bridge **record** is the database row.
**One post must be exactly one record.**

## The 9 channels (locked)

| account_id | Channel | Brand |
|---|---|---|
| 72366 | `ig/AIA-RE` | AI Acceleration: Real Estate |
| 75846 | `fb/AIA-RE` | AI Acceleration: Real Estate |
| 75843 | `yt/AIA-RE` | AI Acceleration: Real Estate |
| 72367 | `x/AIA` | AI Acceleration |
| 72370 | `li/AIA` | AI Acceleration |
| 75850 | `gbp/AIA` | AI Acceleration |
| 75848 | `fb/BT2` | Build Things That Build Things |
| 75841 | `ig/BT2` | Build Things That Build Things |
| 75844 | `tt/BT2` | Build Things That Build Things |

**Out of scope unless explicitly named:** MetL (72371/72372/72369/72373/80485),
Human Creation Collective (75845/75840), `li/Ryan Wanner` (80927), `x/AIAcceleration0` (80505).

---

# THE PROCESS — run these steps in order

## Step 1. Inventory the batch

```bash
cd <batch folder>
ls -l *.mp4
for f in *.mp4; do ffprobe -hide_banner -loglevel quiet \
  -show_entries format=duration -select_streams v:0 \
  -show_entries stream=width,height -of csv=p=0 "$f"; done
```

Establish: how many **posts** (distinct concepts), and which files are alternate cuts of the
same concept rather than new posts. Loop or `-h` variants of the same numbered clip are
alternates, not posts. State the post count explicitly before going further.

Check channel eligibility from the specs:
- **YouTube** needs exactly 1 video. **Google Business rejects video entirely** and takes a
  single image. **TikTok** takes video or images. Vertical 1080x1920 is fine everywhere else.

## Step 2. Transcribe. Do not write captions from filenames.

```bash
ffmpeg -nostdin -v error -y -i "$f" -ar 16000 -ac 1 -c:a pcm_s16le /tmp/w.wav
whisper-cli -m /Users/ryan/brand_captions/remotion/whisper.cpp/ggml-medium.en.bin \
  -f /tmp/w.wav -nt -np
```

Write to `transcripts/<slug>.txt`. Captions written from filenames invent claims Ryan never
made. This step is not optional.

**ffmpeg eats stdin inside a read loop.** Always pass `-nostdin` and `</dev/null`, or
filenames get truncated mid-loop and files silently fail.

## Step 3. Verify every factual claim

Any statistic in the transcript gets a WebSearch before it reaches a caption. Ryan's own
rule: research the claim and credential it with a real source rather than hedging or
dropping it. If the verified figure differs from what he said on camera, **use the verified
figure with attribution** and tell him about the delta.

## Step 4. Load brand voice

```bash
node /Users/ryan/ryan_ops/scripts/load-entity-bundle.mjs bt2
node /Users/ryan/ryan_ops/scripts/load-entity-bundle.mjs aia
```

Read the tier-1 `about-me.md` and `voice.md` for both. AIA channels speak to real estate
agents. BT2 channels speak to founders and operators at 25 to 500 employees. **The same
video gets a different frame on each brand.** That is the entire point of per-channel captions.

Universal rules that override canon voice files:
- **No hashtags. Ever.** Embed keywords in prose.
- **No dashes in post copy.** No em dashes, en dashes, or compound hyphens inside captions.
  Proper nouns like T-Mobile are the only exception.
- **No social proof credentials inside content.**
- **Movement CTAs.** "See the Real Estate track", never "book a call" or "learn more".
- Members and adapters, never students, users, or customers.

Known conflict: AIA `voice.md` still says "3-5 hashtags" for IG and TikTok. The feedback
rules win. Flag it each run until the canon file is fixed.

## Step 5. Derive posting windows from live analytics

```bash
python3 scripts/windows.py report     # hour and weekday performance, ranked
python3 scripts/windows.py ladder     # the slot ladder for rungs 3/5/7/8
```

**Do not hardcode slots.** `windows.py` pulls every analytics record, scores each hour with
a blend of mean views on the view-reliable platforms and mean Instagram likes, and emits the
ladder. Re-derive every run; the ranking moves.

Measurement caveats it already handles:
- Post Bridge syncs analytics for **TikTok, YouTube, Instagram, Facebook only**. X, LinkedIn
  and Google Business return nothing, so a third of the channel set cannot inform timing.
- Instagram feed photos report 0 views. Views come from yt/tt/fb; Instagram contributes likes.
- Hours with fewer than 8 records are excluded as noise.
- Overnight hours are excluded outright.

Weight strong creative toward the best weekdays from `windows.py report`.

## Step 6. Read the current calendar and the ramp

```bash
python3 scripts/schedule_engine.py status
```

Reports live records, content units, posts per day per 30-day block, and the gap to each rung.
`posts/day = content units that day / 9`.

### The ramp rule

```
RUNGS   = [3, 5, 7, 8]        posts per day
BLOCK   = 30 days
HORIZON = 2 blocks (60 days)

for rung in RUNGS:
    fill block 1 (days 0-29)   to rung posts/day
    then block 2 (days 30-59)  to rung posts/day
    advance only when BOTH blocks sit at rung
both blocks at 8/day -> open block 3 (days 60-89), restart at rung 3
```

Never skip a rung. Never fill block 2 ahead of block 1. **A rung is a count target, not a
slot whitelist** — if a preferred slot is blocked, fall down the ladder rather than skip the
day. Stop when media runs out and report the exact remaining gap in posts.

## Step 7. Plan placements with collision detection

```bash
python3 scripts/schedule_engine.py plan --count N
```

**Hard rule: 90 minutes minimum between any two posts on the same channel.** Checked against
the live calendar **plus** the pending batch, never the batch alone.

Also reject any record listing the same `account_id` twice. That is a real observed failure
that causes double posting.

```bash
python3 scripts/repair.py scan            # audit existing defects
python3 scripts/repair.py fix --all       # dedupe + reschedule collisions
```

## Step 8. Upload media, verify by byte size

```bash
node ~/.claude/skills/post-bridge/scripts/post-bridge.js upload --file <path>
```

Never MCP base64; it truncates around 22k chars. Record slug, kind, byte size and media_id
to `media-manifest.tsv` and verify every uploaded size against source.

If two brand cuts are byte-identical, **upload once** and reference one media_id for all
video channels. Do not create a `-bt2` duplicate. The library already holds 910 objects for
roughly 100 posts because of this.

## Step 9. Build the Google Business card

```bash
node /Users/ryan/video-builds/aia/make-gmb-card.mjs <mediaId> <out.jpg> "HEADLINE" "subline" 2
```

Crops the **upper third** of the vertical frame, burns the headline onto the brand panel with
the accent rule and AI ACCELERATION lockup, 1200x1200, roughly 100 to 130 KB.

**Never center-crop a raw video frame.** The middle band of a vertical talking-head frame is
table and legs, and the result is unusable. Verified the hard way.

Build a contact sheet and actually look at it before uploading:
```bash
ffmpeg -nostdin -pattern_type glob -i "gmb/*.jpg" -vf "scale=340:340,tile=5x5" -frames:v 1 -y sheet.jpg
```

## Step 10. Write 9 captions per post

One per channel, all distinct, grounded in the transcript. Plus:
- **YouTube** `title`, 100 chars max.
- **X** `first_comment` for any link. X strips URLs from the body.
- **Google Business** gets a CTA and an image.
- **Instagram** gets a `cover_image`.

Match each channel's register: LinkedIn long and evidence led ending in a question, X
compressed and provoking, TikTok and IG spoken voice, Facebook warmer and shareable, GBP
local and plain.

Assemble to `batch.json`:
```json
{"posts":[{"slug":"...","scheduled_at":"...Z","video_media_id":"...","gmb_media_id":"...",
           "youtube_title":"...","twitter_first_comment":"...","gbp_cta_url":"...",
           "captions":{"72366":"...", ... all 9 ...}}]}
```

## Step 11. Preflight lint

```bash
python3 scripts/create_batch.py lint batch.json
```

All must pass:
1. 9 destinations present
2. no duplicate `account_id` in the record
3. 9 distinct captions
4. YouTube title set and under 100 chars
5. GBP entry carries an image, not video
6. slot is in the derived allowed set
7. 90 minute same-channel gap vs every existing and pending post
8. every media_id resolves and byte size matches source

Also lint the copy: no hashtags, no dashes, no banned words from either brand list.

## Step 12. Approval gate

Emit the dated table and stop.

| # | Date | Day | CT | UTC | Post | Headline |

Show at least one post's full 9 captions so the voice can be judged. **Nothing reaches Post
Bridge until Ryan has seen this.**

## Step 13. Create, then verify, then repair

```bash
python3 scripts/create_batch.py create batch.json
```

**The API returns a created id without reliably persisting `social_accounts`.** On a 25 post
batch, 4 records were created with 9 captions and **0 destinations** — they would have
published to nothing. `create_batch.py` now re-reads every record after creation and repairs
empties automatically. Never trust the create response.

The same flakiness affects PATCH:
- A bare `social_accounts` PATCH returns **HTTP 500**. Always send
  `account_configurations` alongside it.
- PATCH sometimes returns **200 and drops `social_accounts` to 0**.
- PATCH sometimes returns **500 but persists anyway**.

So: **always PATCH, sleep, re-read, and check the actual field.** Never the status code.
Retry up to 5 times. This is what `patch_verify` in `repair.py` does.

## Step 14. Postflight

```bash
python3 scripts/repair.py scan            # confirm 0 collisions, 0 dupes, 0 empties
python3 scripts/schedule_engine.py status # confirm the ramp moved, report residual gap
```

Then after publish:
- `list_post_results post_id=<id>` — confirm all 9 landed.
- `list_analytics` at 48 to 72 hours.

### Known publish failure rates (measured over 1,297 results)

| Account | Rate | Cause |
|---|---|---|
| `gbp/AIA` | 13.0% | Google Business API errors |
| `fb/AIA-RE` | 12.8% | `Object with ID does not exist / missing permissions` |
| `fb/BT2` | 5.3% | same |
| everything else | under 2.5% | transient |

The Facebook and Google Business failures are **auth and permission problems on the platform
side**. They need Ryan to reconnect those accounts in the Post Bridge dashboard. Do not
attempt to fix credentials. Report and move on.

---

## Scripts

| Script | Purpose |
|---|---|
| `windows.py report\|ladder` | derive posting windows from live analytics |
| `schedule_engine.py status\|collisions\|plan` | ramp state, collision audit, placement planning |
| `repair.py scan\|fix` | dedupe destinations, reschedule collisions, verified writes |
| `create_batch.py lint\|create` | preflight lint, creation, post-create verification and repair |

## Standing account facts (verified 2026-08-29)

- 18 accounts connected, 0 needing reconnect.
- The media library holds ~910 objects for ~100 posts. Check `list_media` for an existing
  identical asset before uploading.
- 60 MetL drafts sit untouched in the account. They are out of scope.
