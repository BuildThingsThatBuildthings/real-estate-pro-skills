# Post Bridge API — observed behaviour

Measured against the live API, not inferred from documentation. Sample sizes are given so
you can judge how much weight to put on each claim.

## The write path lies

**A successful `POST /v1/posts` does not mean the record is complete.**

On one 25 post batch, 4 records were created with every `account_configurations` entry intact
and `social_accounts` set to `[]`. They would have published to nothing, silently. An
isolated single record test reproduced the same failure independently.

`PATCH /v1/posts/{id}` fails in three distinct ways:

| Symptom | Reality |
|---|---|
| `HTTP 500` | the change sometimes persisted anyway |
| `HTTP 200` | `social_accounts` sometimes dropped to `[]` |
| bare `{"social_accounts": [...]}` | reliably `HTTP 500` |

Sending `social_accounts` together with `account_configurations` is the only payload shape
that works with any consistency.

### The rule

Never trust a status code. **Write, sleep, re-read, assert on the actual field, retry.**
`pb.patch_verify` implements this and every write in this bundle goes through it.

## What does round-trip correctly

Validated by creating a record with a unique marker caption per channel, reading it back and
diffing field by field:

- per-account `caption`, landing on the correct account
- per-account `media`, so different brand cuts and a still for image-only platforms coexist
  in one record
- `platform_configurations` for youtube, twitter, instagram, tiktok and google_business

25 of 25 production records matched their source exactly on all of the above.

## Media constraints

- **Google Business rejects video.** Single image only, and it takes its own call to action.
- **YouTube requires exactly one video.** An image produces
  `Only videos are supported for YouTube posts`.
- **X strips URLs from the body.** Links belong in `twitter.first_comment`.
- **Instagram feed photos report 0 views.** Use likes as the Instagram signal.
- `video_cover_timestamp_ms` sets a cover frame without uploading a separate asset.

## Analytics coverage

Post Bridge syncs analytics for **TikTok, YouTube, Instagram and Facebook only**. X, LinkedIn
and Google Business return nothing. On a nine channel set that leaves a third of the
destinations unmeasurable, so timing can only ever be derived from the platforms that report.

Set `windows.view_reliable_platforms` in `pipeline.json` to match what your account actually
returns.

## Publish failures

Across 1,297 post results on one account, 3.9% failed. They were not evenly spread:

| Platform | Rate | Signature |
|---|---|---|
| google_business | 13.0% | Google Business API errors |
| facebook | 5 to 13% | `Object with ID does not exist, cannot be loaded due to missing permissions` |
| instagram | ~2.5% | transient server errors |
| everything else | under 1% | transient |

The Facebook and Google Business signatures are **auth and permission problems on the
platform side**. They are fixed by reconnecting the account in the Post Bridge dashboard, not
in code. Expect a few percent baseline failure and check `post-results` after every batch.

## Other traps

- `ffmpeg` consumes stdin inside a `while read` loop and truncates filenames. Always pass
  `-nostdin` and `</dev/null`.
- Media libraries accumulate duplicates fast when byte identical cuts are uploaded under
  separate ids. One observed account held roughly nine times more media objects than posts.
  Upload once, reference many.
- `os.path.normpath` collapses `..` textually and breaks when a skill is installed as a
  symlink. Use `realpath`.

## Media purge orphans scheduled records (found 2026-08-31)

Post Bridge deletes the underlying media FILE once every post referencing it has
published — but the media RECORD stays resolvable via `GET /media/{id}`. When the
old calendar shared media ids across many records, each publish made the shared
file eligible for purge, orphaning still-scheduled records that referenced it.
The orphaned record looks perfectly healthy in every API read and publishes to
nothing.

Detection: fetch the media's signed `object.url` and range-request it. `200/206`
is alive; anything else means the file is gone even though the id resolves.
The batch lint now does this per media id. Recovery: byte-size match against
local sources, re-upload, repoint the record with a verified PATCH.

Also: sweeping many media urls in parallel trips rate limits and reports false
deaths. Sweep sequentially with 429 retry, or the results are noise.
