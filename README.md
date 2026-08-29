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

Each skill has its own README explaining the practices behind it, and a `SKILL.md` that is the
operating manual Claude follows.

More skills will be added.

## Quick start

```bash
./install.sh
cd config && cp channels.example.json channels.json \
          && cp brand.example.json brand.json \
          && cp pipeline.example.json pipeline.json
python3 skills/post-bridge-schedule/scripts/pb.py accounts   # get your account ids
python3 skills/post-bridge-schedule/scripts/doctor.py        # 18 preflight checks
```

Full walkthrough: [docs/getting-started.md](docs/getting-started.md).

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

## How the two production skills relate

`content-foundry` **makes** things and delivers them for approval. It never publishes.
`post-bridge-schedule` **schedules** things, and only for clients who bought posting, and only
from work the client already approved. Keeping them separate is deliberate: the client agreement
says nothing publishes on its own.

## Before you trust a write

The Post Bridge write path returns success without reliably persisting fields. Every write in
this bundle goes through a verify and retry helper for that reason.

Read [docs/post-bridge-api-notes.md](docs/post-bridge-api-notes.md) before extending anything.

## License

MIT. See [LICENSE](LICENSE). Bundled fonts are SIL OFL.
