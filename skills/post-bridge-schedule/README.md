# post-bridge-schedule

Folder of finished video in. Verified scheduled social records out.

`SKILL.md` is the operating manual Claude follows. This file is the human summary.

## What it does

Fourteen steps: environment check, inventory, transcription, claim verification, brand voice,
analytics-derived posting windows, ramp planning, collision detection, media upload, image card
generation, per-channel captions, preflight lint, an approval gate, creation, and post-create
repair.

## Why it works this way

**One post is one record.** A post is a content concept. A content unit is one channel-specific
instance of it. Nine channels means nine units, carried by a single record through
`account_configurations[]`, each with its own caption and the right media for that platform.

The common failure is creating a separate record per brand. That triples your calendar, makes
rescheduling one creative an N step operation, and hides how much content you actually have. One
account had 422 records representing about 72 posts before this was fixed.

**Posting windows are derived, never hardcoded.** `windows.py` scores every hour from your own
analytics and re-derives the ladder each run. A hardcoded table drifts and quietly stops being
true. On a real account the derived ladder disagreed with a hand-written one on two of three
top slots.

**A rung is a count target, not a slot whitelist.** When the preferred slot is blocked, fall down
the ladder rather than skip the day.

**Never trust a write.** This API returns success without persisting `social_accounts`. Every
write goes through write, sleep, re-read, assert, retry. See
[docs/post-bridge-api-notes.md](../../docs/post-bridge-api-notes.md).

**Nothing publishes without a human.** The pipeline stops at a dated schedule table for approval.

## Commands

```bash
python3 scripts/doctor.py                        # 18 preflight checks, run this first
python3 scripts/pb.py accounts                   # your account ids
python3 scripts/windows.py ladder                # derived posting slots
python3 scripts/schedule_engine.py status        # ramp state and gaps
python3 scripts/repair.py scan                   # collisions, duplicates, empty destinations
python3 scripts/create_batch.py lint batch.json  # preflight, writes nothing
```

## Gotchas worth knowing before you extend it

- `ffmpeg` consumes stdin inside a `while read` loop and truncates filenames. Pass `-nostdin`
  and `</dev/null`.
- Never center crop a raw frame for an image card. The middle of a vertical talking-head frame
  is table and legs.
- If two brand cuts are byte identical, upload once and reference one media id. One library held
  roughly nine times more objects than posts because of this.
- Analytics only cover a subset of platforms. Anything outside `view_reliable_platforms` cannot
  inform timing.
