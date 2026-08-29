# Post Bridge API — observed behaviour

Everything here was measured against the live API on 2026-08-29, not inferred from docs.

## The write path lies

**A successful `POST /v1/posts` does not mean the record is complete.**

On a 25 post batch, 4 records were created with all 9 `account_configurations` intact and
`social_accounts` set to `[]`. They would have published to nothing, silently. An isolated
single record test reproduced the same failure.

`PATCH /v1/posts/{id}` is worse, and fails three different ways:

| Symptom | Reality |
|---|---|
| `HTTP 500` | the change sometimes persisted anyway |
| `HTTP 200` | `social_accounts` sometimes dropped to `[]` |
| bare `{"social_accounts": [...]}` | reliably `HTTP 500` |

Sending `social_accounts` together with `account_configurations` is the only payload shape
that works with any consistency.

### The rule

Never trust a status code. **Write, sleep, re-read, assert on the actual field, retry.**
`repair.py:patch_verify` and the post-create pass in `create_batch.py` both implement this.

## What does round-trip correctly

Validated by creating a record with a unique marker caption per channel, reading it back,
and diffing field by field:

- per-account `caption` — exact, correct account
- per-account `media` — video to the 8 video channels, the card to Google Business
- `platform_configurations` for youtube, twitter, instagram, tiktok, google_business

25 of 25 production records matched their source exactly on all of the above.

## Media constraints

- **Google Business rejects video.** Single image only. It also needs its own CTA.
- **YouTube requires exactly one video.** Sending an image produces
  `Only videos are supported for YouTube posts`.
- **X strips URLs from the body.** Links belong in `twitter.first_comment`.
- **Instagram feed photos report 0 views.** Use likes as the Instagram signal.
- `video_cover_timestamp_ms` sets a cover without uploading a separate asset.

## Analytics coverage

Post Bridge syncs analytics for **TikTok, YouTube, Instagram and Facebook only**.
X, LinkedIn and Google Business return nothing. A third of a 9 channel set is unmeasurable,
so timing decisions can only be derived from the other six.

## Publish failure rates

Measured across 1,297 post results:

| Account | Rate | Cause |
|---|---|---|
| `gbp/AIA` | 13.0% | Google Business API errors |
| `fb/AIA-RE` | 12.8% | `Object with ID does not exist / missing permissions` |
| `fb/BT2` | 5.3% | same |
| everything else | under 2.5% | transient |

The Facebook and Google Business failures are platform-side auth problems. They are fixed by
reconnecting the account in the Post Bridge dashboard, not in code.

## Other traps

- `ffmpeg` consumes stdin inside a `while read` loop and truncates filenames. Always pass
  `-nostdin` and `</dev/null`.
- The media library accumulates duplicates fast: ~910 objects for ~100 posts, because
  byte-identical brand cuts were uploaded under separate ids. Upload once, reference many.
