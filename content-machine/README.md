# The Content Machine — desktop lane

The weekly content production loop from AI Acceleration's Innovation Lab class *"Elmer: The Machine That Makes the Week's Content"* — packaged so a non-technical real estate professional can run it entirely inside the desktop app of Claude, ChatGPT, or Gemini. No terminal, no code, no install beyond one pasted prompt.

## Install

Copy the prompt in [INSTALL-PROMPT.md](INSTALL-PROMPT.md) and paste it into your AI. It fetches these files, installs the skill into your app's persistent layer (a Claude Project, a ChatGPT Project, or a Gemini Gem), connects Google Drive, builds the folder system, and interviews you to fill your four context cards. Ten to fifteen minutes, all questions in plain English.

## What is in here

| File | What it is |
|---|---|
| [INSTALL-PROMPT.md](INSTALL-PROMPT.md) | The one-paste installer. Start here. |
| [SKILL.md](SKILL.md) | The operating manual the AI follows every week — the seven stations. |
| [cards/](cards/) | The four context cards as editable starting points: `self.md` (your voice), `guardrails.md` (Fair Housing + what it must never say), `channel.md` (how each platform behaves), `machine.md` (how the pipeline runs). |
| [PROMPT-PACK.md](PROMPT-PACK.md) | The seven station prompts, copy-paste ready, for running any station by hand. |
| [FOLDER-README.md](FOLDER-README.md) | The one-page explanation of the four-folder system. Short enough to hand to an assistant. |
| [POWER-UPS.md](POWER-UPS.md) | Optional upgrades: agent browser, video lane, generation accounts. All optional, all degrade gracefully. |

## The seven stations

```
1 Intake → 2 Log → 3 Brand compare → 4 Generate → 5 Approve → 6 Schedule → 7 Learn ↺
```

You feed one Drive folder as a byproduct of your week. The machine logs what came in (and settles rights at intake), compares it against your cards, produces a batch, waits for your approval (a folder drag is the entire UI), writes the week's schedule, and reads last week's numbers to decide what gets made next. Nothing ever publishes itself.

## Relationship to the advanced lane

This folder is the self-contained desktop lane. The rest of this repository is the **advanced lane** — the same philosophy as full Claude Code skills for operators, assistants, and teams:

| Station | Desktop lane (this folder) | Advanced lane (Claude Code) |
|---|---|---|
| 1–3 · Intake, Log, Brand compare | SKILL.md | [`skills/content-foundry`](../skills/content-foundry/) intake + brief |
| 4 · Generate | Scripts, stills copy, shot lists | [`skills/content-foundry`](../skills/content-foundry/) full render + compositing |
| 5 · Approve | Drive folder drag | Same folder contract |
| 6 · Schedule | A written schedule you carry out | [`skills/post-bridge-schedule`](../skills/post-bridge-schedule/) verified scheduling |
| 7 · Learn | You paste numbers (or an agent browser reads them) | Analytics-derived windows in `post-bridge-schedule` |
| Voice | `cards/self.md` | [`skills/brand-voice`](../skills/brand-voice/) voice packs |
| Compliance | `cards/guardrails.md` | [`skills/compliance-gate`](../skills/compliance-gate/) |

Start on the desktop lane. Graduate to the advanced lane when someone on your team is comfortable in Claude Code — the vocabulary, folders, and rules carry over unchanged.
