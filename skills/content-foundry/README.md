# content-foundry

Brand locked content production for real estate. A mixed asset dump goes in, a finished set for
client approval comes out.

`SKILL.md` is the operating manual Claude follows. This file is the human summary.

## What it does

Eleven stages: pull the client's brand and weekly context from Drive, inventory the dump, unify
it into one document, research, write a reviewable brief and stop, route by output type, generate
base imagery, composite brand elements deterministically, gate on compliance and slop, export per
channel, deliver for approval.

## Why it works this way

**The folder is the tenancy boundary.** Everything brand related comes from that client's folder.
Never read another client's folder in a run, never carry brand facts between runs from memory. A
missing brand fact is a question, not an inference.

**Composite, don't request.** The generative model never produces the logo, the exact brand hex,
the license number or the disclosure line. Those are placed from files on disk. Asking a model
for them is the failure this product exists to prevent.

**Brief before spend.** The brief is written to disk and the run stops for review before any
generation call. Regeneration is expensive, briefs are cheap.

**The gates must be able to fail.** If a lint has never failed on a run, it is not wired
correctly.

**Compliance is two separate problems.** Placement is whether required language is present and
legible. Wording is whether the copy makes a Fair Housing or claims violation. Both are gated,
neither substitutes for broker or legal review.

**This system does not publish.** Finished work is delivered to the client's `01 – Waiting`
folder. They approve, request changes, or ignore. Scheduling is a separate paid product and only
runs from approved work.

## Commands

```bash
python3 scripts/doctor.py                                        # dependency check
python3 scripts/drive_sync.py clients                            # configured clients
python3 scripts/drive_sync.py all --client <slug>                # brand + weekly context
python3 scripts/drive_sync.py agent-folder --client <slug>       # map Drive to Tier-1/Tier-2
python3 scripts/compliance.py rules --client <slug>              # active Fair Housing rules
python3 scripts/compliance.py check --batch captions.json --client <slug>
python3 scripts/drive_sync.py deliver --client <slug> --from output/   # dry run without --yes
```

## The Drive layout it expects

Per the client's own README, four folders:

| Folder | Who touches it |
|---|---|
| `00 – Weekly Context` | the client drops anything from their week |
| `01 – Waiting` | finished sets are delivered here |
| `02 – Approved` | the client drags things they approve |
| `03 – Revision Requested` | the client drags things to send back |

Brand context is a separate folder holding `my business/` (about-me, brand-voice, working-style,
GUARDRAILS), `my clients/` and `my deals/`. It is synced on **every** run, not just weekly ones,
because stale guardrails are the expensive kind of stale.

## Gotchas

- Uses `rclone`, not the Drive MCP. The MCP returns file bytes as base64 into the model context,
  which is wrong for a folder of photos and video.
- rclone's shared Google `client_id` is being retired during 2026. Configure your own OAuth
  client_id before then or every weekly run breaks at Stage 0.
- `brand-context-visual.md` has no Drive equivalent in the current template. Without it the
  composite stage has no hexes, logo or fonts and will stop at setup.
- Unclear rights on an asset means it does not get made. Unclear is missing, not pending.
