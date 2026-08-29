# Post Bridge Automation (Phase 3 — bonus module)

Isolated on purpose: **the core skill has zero dependency on this file.** Everything through Stage 9
works without Post Bridge configured.

Post Bridge ships a public npm CLI, so a brokerage needs no MCP configuration — an API key is
enough. `npx postbridge-cli <command>` (Node 18+). Key via `POST_BRIDGE_API_KEY` in the workspace
`.env`.

Platforms: Instagram, TikTok, YouTube, X, LinkedIn, Facebook, Pinterest, Threads, Bluesky.

---

## The kill switch

**Posts are created as scheduled drafts. Never instant-published.** The only thing that changes this
is `auto_publish: true` in the agent's `brand-context-compliance.md`, set deliberately by someone
with authority to approve unattended publishing under that agent's license.

Default lead time before a scheduled post goes out is ≥ 36 hours — a real veto window, not a
formality. Never shorten it to make a demo look better.

## Flow

1. **Preflight.** Confirm `POST_BRIDGE_API_KEY` is set and the target channels have connected
   accounts. Abort **per-channel** if an account is missing — don't fail the whole run because
   LinkedIn isn't connected.
2. **Size guard.** Reject any variant over **300 MB** before upload. YouTube, LinkedIn, and X
   silently drop oversized media rather than returning an error, so an unguarded upload looks
   successful and produces nothing.
3. **Upload once per platform group.** Media is uploaded once and referenced by multiple posts —
   don't re-upload the same file per channel.
4. **Create posts.** One `create_post` per platform, each with that channel's caption variant from
   Stage 6 and its `scheduled_at`.
5. **Poll results.** The post is not done until per-platform results confirm. Write `posts.json`
   (post ids, per-platform status, scheduled times) into the run directory.
6. **Report.** Tell the user what's queued, when each goes out, where the dashboard is, and how to
   veto.

## Scheduling math

Compute `scheduled_at` from three inputs, in order:
1. The agent's preferred posting windows (Tier-2 config or `channel-specs.md` cadence guidance).
2. Cadence per week for that channel.
3. **Existing queue occupancy** — list already-scheduled posts first and don't stack two posts into
   the same window. This is the step most often skipped, and it produces double-posts.

Then apply the approval lead time. If the computed slot is sooner than the lead window, push to the
next valid slot rather than shortening the window.

## Caption variants

One brief, N channel-native captions — not one caption copy-pasted. Each honors that channel's rules
from `channel-specs.md`: LinkedIn's professional register and no in-body link; Instagram's
keyword-forward first 100 characters; X's 280-character limit.

Compliance language required by `brand-context-compliance.md` appears in **every** variant. If a
channel's character limit can't accommodate it, that channel is skipped with an explanation — the
disclosure is not optional and is not abbreviated.

## Batch and roster modes

- **Batch:** one drop → a multi-post calendar across channels, spaced per cadence rules.
- **Roster:** one prompt run across N agent folders, each output branded and licensed to its own
  agent, scheduled to that agent's own connected accounts. Tenancy isolation applies exactly as in a
  single run — verify no agent's disclosure or license leaks into another's post.

## Failure surfaces

| Condition | Response |
|---|---|
| `POST_BRIDGE_API_KEY` missing | Stop before upload; the run's exports are still valid on disk |
| Channel account not connected | Skip that channel, continue others, report it |
| Variant > 300 MB | Reject pre-upload, report the size, suggest re-export |
| Compliance text won't fit channel limit | Skip channel, explain — never truncate the disclosure |
| Post created but result never confirms | Report as unconfirmed, not as published |
