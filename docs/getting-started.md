# Getting started

## 1. Install

```bash
git clone <this repo> ~/real-estate-pro-skills
cd ~/real-estate-pro-skills
./install.sh
```

Skills are symlinked into `~/.claude/skills` so edits take effect immediately. Use
`--copy` if you would rather they be independent.

## 2. Authenticate

Either export a key:

```bash
export POST_BRIDGE_API_KEY=pb_live_xxxxx
```

or create `~/.config/post-bridge/config.json`:

```json
{ "apiKey": "pb_live_xxxxx" }
```

## 3. Configure

```bash
cd config
cp channels.example.json channels.json
cp brand.example.json    brand.json
cp pipeline.example.json pipeline.json
```

Get your real account ids:

```bash
python3 skills/post-bridge-schedule/scripts/pb.py accounts
```

Put the ones you want to post to into `channels.json`. Everything else about your setup
follows from that file. Local config files are gitignored, so your account ids never end up
in version control.

Then write a voice pack per brand:

```bash
cp config/voice/_TEMPLATE.md config/voice/my-brand.md
```

## 4. Check the environment

```bash
python3 skills/post-bridge-schedule/scripts/doctor.py
```

Eighteen checks covering config, binaries, API reachability, whether every configured channel
exists on your account, whether any needs reconnecting, and whether you have enough analytics
history to derive posting windows. Fix anything failing before continuing.

## 5. See where you stand

```bash
python3 skills/post-bridge-schedule/scripts/windows.py ladder
python3 skills/post-bridge-schedule/scripts/schedule_engine.py status
python3 skills/post-bridge-schedule/scripts/repair.py scan
```

With little history the ladder falls back to sensible defaults and sharpens as you publish.

## 6. Schedule a batch

Point Claude Code at a folder of finished video and say **"schedule this batch"**. The skill
runs the fourteen steps in `skills/post-bridge-schedule/SKILL.md` and stops at the approval
gate before writing anything.

## Onboarding a second person

Copy `config/` to a second directory, edit `channels.json` and the voice packs, and point at
it:

```bash
RE_SKILLS_CONFIG_DIR=~/clients/acme/config \
  python3 skills/post-bridge-schedule/scripts/doctor.py
```

Nothing in the scripts is tied to one account.
