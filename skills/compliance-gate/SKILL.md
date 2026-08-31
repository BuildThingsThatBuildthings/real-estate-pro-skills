---
name: compliance-gate
description: >
  Check any piece of real estate copy against the Fair Housing baseline, a client's own
  GUARDRAILS card, and an optional per-MLS profile — before it reaches a client or the public.
  Catches coded demographic language ("perfect for", "safe neighborhood", "great schools",
  "up-and-coming"), outcome promises ("guaranteed", "will appreciate"), and unsourced figures.
  This is also the canonical rules module the other skills' COMPLIANCE gates import. Triggers on
  "/compliance-gate", "is this copy compliant", "fair housing check", "can I say this in a
  listing", "check this ad", "review this caption for compliance", and any request to vet
  marketing or listing language before publication.
---

# compliance-gate — one copy of the rules, checked everywhere

Invocations:
- `/compliance-gate` on a pasted caption, listing description, email or ad
- `python3 scripts/fair_housing.py check --text "..."` / `--file <path>` / `--batch <batch.json>`
- `... --client {slug}` to merge that client's GUARDRAILS card
- `... --profile {mls}` to merge a local board's additional rules
- `python3 scripts/fair_housing.py rules` to print the active rule set with reasons

## Why this is a skill and not a suggestion

The licensee is liable for published content regardless of who or what wrote it. "The AI wrote
it" is not a defense, and HUD confirmed in 2024 that the Fair Housing Act reaches AI-generated
advertising. The phrases this gate blocks read as ordinary warm copy — that is exactly why a
machine has to catch them, every time, before a human gets attached to the sentence.

## Non-negotiable laws

1. **One copy of the rules in the bundle.** This skill is the canonical home. `content-foundry`,
   `chatgpt-said`, `sphere-signal` and `listing-price-brief` all import from here; none carries
   its own list. Add a rule here and every gate in the bundle picks it up at once. Never copy a
   rule table into another skill.
2. **Profiles add, never remove.** A per-MLS profile in `config/compliance/<name>.json` can add
   phrases a local board prohibits. It cannot remove a baseline rule — boards differ in what they
   additionally prohibit, not in whether Fair Housing applies. The tests assert this.
3. **The gate must be able to fail.** `tests/fixtures/fail/copy.txt` is a caption that trips
   every category, run on every test pass. A lint that has never failed is not wired correctly.
4. **Compliance is placement, not wording.** This gate refuses *prohibited* language. Required
   language (license lines, brokerage disclosures) is supplied by the brokerage and composited
   from disk by the skill producing the artifact — the model never invents or paraphrases a
   legal disclosure.
5. **A pass is not legal advice.** The gate catches known-bad patterns; it cannot certify a
   sentence as lawful. Say so when reporting a clean result.

## Rule categories

| Category | Refuses | Examples |
| --- | --- | --- |
| `BANNED` | coded demographic and proxy language | "perfect for", "safe neighborhood", "great schools", "family-friendly", "up-and-coming" |
| `PROMISE` | outcome guarantees | "guaranteed", "will appreciate", "will sell fast", "closing in 10 days" |
| `NEEDS_SOURCE` | figures with no source marker | square footage, room counts, percentages, HOA/tax amounts, year built |

Full list with the reason behind each rule: `python3 scripts/fair_housing.py rules`, and the
history of why each proxy is a proxy in `references/why-each-rule.md`.

## Rule precedence

client GUARDRAILS card (their brokerage wrote it for them) → MLS profile → Fair Housing baseline.
Later layers only ever ADD.

## Adding a rule

Edit `BANNED` / `PROMISE` / `NEEDS_SOURCE` in `scripts/fair_housing.py`, add the phrase to
`tests/fixtures/fail/copy.txt` or a spot-check in `tests/run_tests.sh`, run the suite. Every
skill's COMPLIANCE gate now enforces it — that is the point of one copy.

## Setup

```bash
python3 scripts/doctor.py    # import check, profile inventory, full self-test
```

No dependencies beyond Python. Optional: `config/compliance/<mls>.json` per local board (copy
`example-mls.example.json`), `config/clients.json` for client GUARDRAILS cards.
