# compliance-gate

Checks real estate copy against the Fair Housing baseline, a client's GUARDRAILS card, and an
optional per-MLS profile. Also the canonical rules module every other skill's COMPLIANCE gate
imports.

`SKILL.md` is the operating manual Claude follows. This file is the human summary.

## Why it exists

49% of agents cite compliance risk — and 28% fair housing specifically — as the reason they will
not put AI output in front of a client. They are right to worry: the licensee is liable for
published content regardless of authorship, and the phrases that create the liability read as
ordinary warm copy. "Perfect for a growing family" is a sentence a model produces because that is
how marketing sounds; written by a licensee, about housing, it is familial-status targeting.

These rules lived inside `content-foundry` until four skills needed them. A second copy would
drift, and the copy that drifts is the one that reaches a client — so the rules moved to one
canonical home and everything imports from it. `content-foundry` keeps a shim at the old path.

## The layering

```
client GUARDRAILS card   (their brokerage wrote it; wins on conflicts)
  + MLS profile          (config/compliance/<board>.json — local additions)
  + Fair Housing baseline (always on, cannot be removed by any layer)
```

Profiles and cards only ever ADD rules. The test suite asserts a profile cannot remove a baseline
rule, because boards differ in what they additionally prohibit, not in whether Fair Housing
applies.

## What a pass means

The copy contains none of the known-bad patterns. That is all it means — the gate cannot certify
a sentence as lawful, and it says so. What a FAIL means is harder to argue with: a specific
phrase, a specific reason, and an exit code that stops the pipeline.

## Use it standalone

```bash
python3 scripts/fair_housing.py check --text "A hidden gem, perfect for young families!"
python3 scripts/fair_housing.py check --file listing.md --profile example-mls
python3 scripts/fair_housing.py rules
```

Exit 1 on any finding. This is a gate, not advice.
