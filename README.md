# Real Estate Professional Skill Bundle

Claude Code skills for real estate professionals and the operators who support them.
Each skill is self-contained, reads its configuration from `config/`, and is designed to be
installed into `~/.claude/skills/`.

## Skills

| Skill | What it does |
|---|---|
| [`post-bridge-schedule`](skills/post-bridge-schedule/) | End to end social posting pipeline via Post Bridge. Folder of finished video in, verified scheduled records out. |

More skills will be added to this repo.

## Install

```bash
./install.sh            # symlink every skill into ~/.claude/skills
./install.sh --copy     # copy instead of symlink
```

Symlinks are the default so edits in the repo take effect immediately.

## Configuration

`config/channels.json` defines the channel set a batch fans out to. It is the one file to
edit when onboarding a different professional. Scripts resolve it in this order:

1. `$RE_SKILLS_CHANNELS`
2. `<repo>/config/channels.json`
3. a built-in fallback

Nothing else in the scripts hardcodes an account id.

## Requirements

These are host dependencies, not vendored:

| Need | Used for | Current path |
|---|---|---|
| Post Bridge API key | all API calls | `~/.config/post-bridge/config.json` |
| `post-bridge` CLI | media upload | `~/.claude/skills/post-bridge/scripts/post-bridge.js` |
| `ffmpeg` / `ffprobe` | media probing, contact sheets | on PATH |
| `whisper-cli` + a ggml model | transcription | `ggml-medium.en.bin` |
| `make-gmb-card.mjs` | Google Business cards | `/Users/ryan/video-builds/aia/` |

`make-gmb-card.mjs` lives outside this repo today. Vendoring it is the next cleanup.

## Core model

- **Post** — one content concept, built around one creative.
- **Content unit** — one channel-specific instance. 9 channels means 9 units.
- **One post is exactly one Post Bridge record**, carrying a distinct caption and the right
  media per channel via `account_configurations[]`.

## Read this before trusting a write

The Post Bridge write path is unreliable in ways that are easy to miss. Measured, not
assumed. See [docs/post-bridge-api-notes.md](docs/post-bridge-api-notes.md).
