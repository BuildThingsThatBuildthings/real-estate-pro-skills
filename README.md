# Real Estate Professional Skill Bundle

Claude Code skills for real estate professionals and the operators who support them.

Each skill is self contained, reads everything specific to you from `config/`, and installs
into `~/.claude/skills`. No account ids, brand names or machine paths are hardcoded anywhere.

## Skills

| Skill | What it does |
|---|---|
| [`post-bridge-schedule`](skills/post-bridge-schedule/) | Folder of finished video in, verified scheduled social records out. Derives posting windows from your own analytics, enforces a cadence ramp, detects same-channel collisions, writes one caption per channel, and verifies every write. |
| [`content-foundry`](skills/content-foundry/) | Brand locked content production. Pulls a client's brand and weekly context from Google Drive, unifies a mixed asset dump, researches, writes a reviewable brief, generates and composites on brand assets, gates on Fair Housing and slop, and delivers a finished set to the client's `01 – Waiting` folder. |
| [`brand-voice`](skills/brand-voice/) | Loads a brand's voice pack before any public facing copy is written, and audits the draft against it. |
| [`chatgpt-said`](skills/chatgpt-said/) | Your client brought their own AI. Splits what the chatbot told them into individually checkable claims, classes each one against your record, and gates the reply: no dropped claim, no untraceable number, no arguing with the client, legal and tax questions referred not answered. |
| [`sphere-signal`](skills/sphere-signal/) | Who in your database has a real, dated reason to hear from you this week. Computes reasons from your own records — an unkept promise, an unanswered question, an anniversary, a holding period, dormancy — drafts the touch, and refuses any touch with no reason, no consent, an unearned ask, or an inference about who someone is. Never sends. |
| [`listing-price-brief`](skills/listing-price-brief/) | A seller-ready pricing brief from real comps: supported range, per-comp adjustment ledger, named exclusions, and a net sheet at three prices. Python computes every number; the model only writes narrative over them, and the gate refuses any figure it cannot trace. |

Each skill has its own README explaining the practices behind it, and a `SKILL.md` that is the
operating manual Claude follows.

More skills will be added.

## Install

In Claude Code, two lines:

```
/plugin marketplace add BuildThingsThatBuildthings/real-estate-pro-skills
```

```
/plugin install real-estate-skills@real-estate-pro-skills
```

That is the whole install. All six skills are available immediately — just ask for one
by name, or say what you want ("price this listing", "who should I follow up with").

Nothing here needs configuring to try. Three of the six — `chatgpt-said`, `sphere-signal`,
`listing-price-brief` — run with no setup at all: no API keys, no network, no accounts.
`content-foundry` and `post-bridge-schedule` need config before they can reach your Drive
or your social accounts, and they will tell you exactly what is missing when you run them.

Prefer not to use plugins, or not in Claude Code? `./install.sh` symlinks the same six
skills into `~/.claude/skills`.

### Then, if you want the content pipeline

```bash
cd config && cp channels.example.json channels.json \
          && cp brand.example.json brand.json \
          && cp pipeline.example.json pipeline.json \
          && cp clients.example.json clients.json
python3 skills/post-bridge-schedule/scripts/pb.py accounts   # get your account ids
python3 skills/post-bridge-schedule/scripts/doctor.py        # 18 preflight checks
```

Full walkthrough: [docs/getting-started.md](docs/getting-started.md).
Where finished work goes: [docs/drive-delivery.md](docs/drive-delivery.md).

## Core model

- **Post** — one content concept, built around one creative.
- **Content unit** — one channel-specific instance. Nine channels means nine units.
- **One post is exactly one record**, carrying a distinct caption and the correct media per
  channel through `account_configurations[]`.

The most common way to get this wrong is to create a separate record per brand. That
multiplies your calendar, makes rescheduling a creative an N step operation, and hides how
much content you actually have.

## Configuration

| File | Holds |
|---|---|
| `config/channels.json` | channel set, minimum gap, which platforms are image only |
| `config/brand.json` | brand name, lockup, colours, fonts, default call to action |
| `config/pipeline.json` | ramp rungs, window scoring, timezone, tool paths, copy rules |
| `config/clients.json` | per client Drive folder ids, weekly floor and cap, posting on or off |
| `config/voice/*.md` | one voice pack per brand |

Copy each `.example.json`. Local copies are gitignored.

`RE_SKILLS_CONFIG_DIR` points the whole bundle at a different config directory, which is how
you run it for more than one person.

## Requirements

| Need | Used for |
|---|---|
| Post Bridge API key | all API calls |
| `ffmpeg` and `ffprobe` | media probing, card rendering, contact sheets |
| `node` 18+ | card generator |
| `python3` 3.9+ | pipeline scripts |
| `whisper-cli` and a ggml model | transcription (optional but strongly recommended) |
| `rclone` with a Drive remote | pulling client brand and weekly context |
| Pillow | image compositing in content-foundry |

`doctor.py` checks all of it.

## How the skills relate

`content-foundry` **makes** things and delivers them for approval. It never publishes.
`post-bridge-schedule` **schedules** things, and only for clients who bought posting, and only
from work the client already approved. Keeping them separate is deliberate: the client agreement
says nothing publishes on its own.

`chatgpt-said` **answers** — it produces a document for the agent to use in a conversation, and
sends nothing. `sphere-signal` **notices** — it decides who has a reason to hear from you and drafts
the touch, and also sends nothing.

`listing-price-brief` **computes** — Python owns every number in a pricing brief and the model only
writes narrative over them.

All three import `content-foundry`'s Fair Housing gate rather than copying it, so there is exactly
one copy of those rules in the bundle. Together they close a loop:

```
sphere-signal      who has a reason to hear from you this week
content-foundry    make the thing that is worth sending
post-bridge-schedule   schedule it, if the client bought posting
listing-price-brief    the appointment: supported range, ledger, net sheet
chatgpt-said       the client who showed up with their own AI
```

None of them send anything on their own. `post-bridge-schedule` is the only skill that writes
outward, and only for a client who bought posting, and only from work already approved.

## Before you trust a write

The Post Bridge write path returns success without reliably persisting fields. Every write in
this bundle goes through a verify and retry helper for that reason.

Read [docs/post-bridge-api-notes.md](docs/post-bridge-api-notes.md) before extending anything.

## License

MIT. See [LICENSE](LICENSE). Bundled fonts are SIL OFL.
