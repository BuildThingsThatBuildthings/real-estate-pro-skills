# brand-voice

Loads a brand's voice pack before any public facing copy is written, and audits the draft against
it afterwards.

`SKILL.md` is the operating manual Claude follows. This file is the human summary.

## Why it exists

Copy written without a voice pack reads like a default model wrote it. `content-foundry` and
`post-bridge-schedule` both depend on this skill, because both write one caption per channel and
need to know which voice each channel speaks in.

## How it works

Voice packs live in `config/voice/<brand-slug>.md`, one per brand. Channels map to brands through
the `brand` field in `config/channels.json`.

`config/voice/_RULES.md` holds rules that apply to every brand and **outrank any individual
pack**, because they usually come from a correction made after a pack was written. When a pack and
the shared rules disagree, the shared rules win and the conflict is flagged so one of the two gets
fixed.

## Writing a pack

Start from `config/voice/_TEMPLATE.md`. A pack needs voice essence, audience, tone attributes,
mechanical rules, banned words, per channel guidance, an on brand example, an **off brand
example**, and a one sentence quality test.

The off brand example matters as much as the on brand one. It is the fastest way to catch drift.

## The rule that matters most

One idea, written once per channel, never copied. Copying one caption across surfaces throws away
the only real advantage of per channel publishing.
