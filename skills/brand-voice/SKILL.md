---
name: brand-voice
description: Load a brand's voice pack before writing any public facing copy, so captions, emails and scripts sound like the brand instead of like a default model. Resolves the explicitly selected client voice pack, or config/voice/brand-slug.md for standalone work, and enforces the shared copy rules. Use before drafting social captions, ad copy, email, landing page copy, or video scripts for a named brand, and whenever a piece of copy needs to be checked against a brand's rules. Triggers on "/brand-voice", "load brand voice", "write in the selected brand voice", "check this against the brand rules", or any request to draft brand facing copy.
---

# Brand voice

Copy written without a voice pack reads like a default model wrote it. This skill loads the
pack first and audits the draft after. It is a dependency of `post-bridge-schedule`, which
writes one caption per channel and needs to know which voice each channel speaks in.

## Resolve the current client's pack

In a Content Foundry or Content Machine campaign, use the **explicitly selected client context folder** and its manifest load order. Its `brand-voice.md` (including a manifest-declared `brand/brand-voice.md`) is the voice pack. Pass that resolved absolute path to the linter; do not copy a stale global pack over it. The folder name is not permission to search other client folders. Record the selected path and source samples privately with the current run.

For standalone invocations without a selected client folder, the pack convention is:

```
config/voice/<brand-slug>.md
```

One file per brand. `config/voice/_TEMPLATE.md` is the starting point. A brand with two
audiences that share a voice still gets one file; a brand that speaks differently to two
audiences gets two files and two slugs.

Map channels to voice packs in `config/channels.json` via the `brand` field on each channel.

## Load order

1. Resolve and read the current client's pack end to end. Never default to AIA, a demo persona, another realtor, or remembered voice facts.
2. Read `config/voice/_RULES.md` for rules that apply to every brand.
3. For a fresh campaign or user-directed rebuild, revisit the client's actual writing sources. Collect three short authored samples where accessible; label the evidence count and limitations when fewer exist. Separate the client's own words from agency-written website copy and previous AI drafts. An earlier generated script is not evidence of the client's voice.
4. Extract sentence rhythm, contractions, enthusiasm, recurring invitations, and concrete vocabulary. Draft only after this check. Brand refresh does not authorize silently rewriting the source pack.

If a pack is missing, inspect the selected client folder and already authorized sources first. Build a clearly labeled provisional voice brief from attributable writing when available; ask only for evidence that cannot be found there. Do not invent a voice or claim limited evidence fully validates one.

## What a pack must contain

| Section | Why |
|---|---|
| Voice essence | one paragraph a stranger could write from |
| Tone attributes | 3 to 5, each with a concrete example |
| Mechanical rules | sentence length, contractions, point of view, punctuation |
| Banned words | the specific words this brand never uses |
| Audience | who is on the other side, in their own vocabulary |
| On brand example | a real passage |
| Off brand example | the same idea written badly |
| Quality test | one sentence that settles arguments |

The off brand example matters as much as the on brand one. It is the fastest way to catch
drift.

## Shared rules

`config/voice/_RULES.md` holds rules that outrank any individual pack, because they usually
come from a correction made after a pack was written. When a pack and the shared rules
disagree, report the conflict and resolve it against the current user's instructions and selected client's guardrails. A generic rule cannot import another brand's identity, CTA, vocabulary or audience into this client.

## Per channel voice

The same idea is written once per channel, never copied. A pack should say how the brand
sounds on each surface it uses. Typical differences:

- **LinkedIn** long, evidence led, ends on a question that invites a reply
- **X** compressed to its sharpest form, one idea, provokes a response
- **Instagram and TikTok** spoken voice, first line is the hook
- **Facebook** warmer and more narrative, built to be forwarded
- **YouTube** needs its own title, separate from the caption
- **Google Business** plain, local, factual, carries a call to action

## Audit before returning

The mechanical half is enforced, not requested:

```bash
python3 skills/brand-voice/scripts/voice_lint.py check --pack /absolute/selected-client/brand-voice.md --draft /private/working/draft.json
```

`draft.json` is `{"captions": {"<channel>": "<text>"}}`. Exit 1 refuses: banned words from
the pack, hashtag piles, a caption copied across channels, links in an X body, first lines
too long to be hooks, unsourced figures. Fix the draft, not the linter.

The other half stays with you, judged against the pack's examples:

- [ ] pack loaded for the right brand, and the draft matches it
- [ ] first line works as a standalone hook
- [ ] no banned words from the pack or the shared rules
- [ ] claims carry a source, or they are cut
- [ ] one caption per channel, all genuinely different
- [ ] the call to action matches how this brand asks

Keep the pack path, evidence, lint input and results in private working records. Review narration, on-screen hooks, captions and recording scripts against the same pack; mechanical lint does not establish that a line sounds like the client. Deliver requested scripts and useful copy in the campaign's documents folder. Do not upload JSON, lint output or technical source markers with public media.
