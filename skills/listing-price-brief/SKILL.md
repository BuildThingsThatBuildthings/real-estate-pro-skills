---
name: listing-price-brief
description: >
  Build a seller-ready pricing brief from real comps: a supported price range, a per-comp
  adjustment ledger, named exclusions, and a written net-proceeds sheet at three prices. Python
  does every calculation and the model writes only narrative over computed numbers — the gate
  refuses any figure in the brief that appears in no computed output, any ledger that does not sum
  to its own net, any comp excluded without a reason, and any appraisal or valuation language.
  Comps are acquired, never invented, through an export, a supervised browser session, or a RESO
  feed. Triggers on "/listing-price-brief", "build a CMA", "price this listing", "listing
  appointment prep", "what should we list at", "net sheet for the seller", "pricing presentation",
  and any request to produce comps, a price range, or seller net proceeds.
---

# listing-price-brief — the pricing conversation, on paper

Invocations:
- `/listing-price-brief --agent {slug} --subject subject.json --comps {file}` — full run
- `/listing-price-brief tiers` — which comp sources are available (`comp_source.py tiers`)
- `/listing-price-brief browser-plan --market {slug}` — the supervised pull checklist
- `/listing-price-brief rates` — the default adjustment rates and why to replace them
- `/listing-price-brief gates` — what the gate refuses

Clean, accurate CMAs and better pricing narratives are the top item on agents' stated AI wish
list, and pricing is simultaneously the thing they trust AI with least. Both facts have the same
cause: a model that writes a confident price narrative using numbers it produced itself is worse
than no help at all. The seller keeps the number, the agent owns it, and nothing behind it can be
re-derived.

This skill inverts that. Python computes; the model explains.

Read `references/comp-adjustments.md` before writing narrative, and
`references/comp-sources.md` before acquiring anything.

## Non-negotiable laws

1. **Python owns arithmetic. The model owns sentences.** Every price, adjustment, range and net
   figure comes from `comps.py` or `net_sheet.py`. `GROUNDED` refuses any money figure in the
   brief that appears in no computed output. This is the entire product.
2. **Comps are acquired, never invented.** `comp_source.py` reads what it is given. If a required
   field is missing it aborts and names the field rather than producing a comp set with holes.
3. **Never hand-edit an export to make it load.** Map the header instead. A hand-edited export is
   a comp set nobody can reproduce.
4. **Every adjustment shows its formula, and every ledger re-derives.** `ADJUSTED` re-computes
   each ledger and refuses one that does not sum to its own net.
5. **Every exclusion carries a reason, and the brief names them.** An unexplained exclusion is
   indistinguishable from cherry-picking. The excluded comps are the most persuasive section in
   the document — the seller has usually already seen the high one.
6. **Below the comp floor, nothing is published.** `min_comps` defaults to 3. `net_sheet.py`
   refuses outright, because a net sheet on an unsupported price is a number the seller will hold
   the agent to for the whole listing.
7. **This is not an appraisal or a valuation, and never says it is.** `NOT_APPRAISAL` refuses
   appraisal language and refuses a brief with no disclosure line. Appraisal is a licensed act.
8. **Round numbers are computed, not rounded in prose.** A figure the model rounded is a figure
   the model produced.
9. **Never guess the market trend.** `market_trend_pct_per_month` is 0 until measured locally,
   because a guessed trend compounds across every comp and silently moves the whole range.
10. **One agent per run.** Disclosure and license facts come from that agent's folder only.

## Stages

```
runs/{agent}/{yyyy-mm-dd}-{property-slug}/
  subject.json     1. the subject property
  comps-raw.csv    2. as acquired, unedited
  comps.json       2. normalized
  rates.json       3. local adjustment rates
  adjusted.json    3. ledgers, exclusions, supported range
  costs.json       4. this seller's closing costs and payoff
  net_sheet.json   4. three scenarios
  brief.md         5. seller-facing
  GATE.txt         6. the gate output that let it out
```

### 1. The subject

`subject.json`: `address`, `sqft`, `beds`, `baths`, `garage`, `lot_sqft`, `year_built`,
`condition` (poor/fair/average/good/excellent). Condition comes from the agent having seen the
house, or it is left out — never inferred from photos or from the listing.

### 2. Acquire comps

```bash
python3 scripts/comp_source.py tiers
python3 scripts/comp_source.py load --tier export --in comps-raw.csv --out comps.json --as-of 2026-08-29
```

Three tiers — `export`, `browser`, `reso` — covered in `references/comp-sources.md`. Start with
`export`; it always works and every other tier degrades to it. For a supervised pull, run
`browser-plan` first and follow it exactly: MLS rules of use are per-MLS, and the penalty for
unattended retrieval lands on the sponsoring agent, not on the software.

Mark exclusions in the source file with a reason. Marking them there rather than deleting rows
keeps the full set auditable.

### 3. Adjust

```bash
python3 scripts/comps.py adjust --comps comps.json --subject subject.json \
  --rates rates.json --as-of 2026-08-29 --out adjusted.json
```

Supply local `rates.json` from paired-sales analysis. The built-in defaults are a starting point,
and the brief records which set was used.

Read the output before continuing. Which comp needed the largest adjustment (it carries the least
weight) and which needed almost none (it anchors the range) are the two facts the narrative turns
on.

### 4. Net sheet

```bash
python3 scripts/net_sheet.py example-costs > costs.json   # then fill it in with the agent
python3 scripts/net_sheet.py build --adjusted adjusted.json --costs costs.json --out net_sheet.json
```

Confirm every cost line with the agent and their title company. Set buyer-side compensation to
what **this seller** has agreed to offer, or zero — post-settlement it is negotiated separately
and is not published on the MLS.

### 5. Write the brief

Seller-facing. Structure that works:

1. The disclosure line — this is a marketing pricing brief, not an appraisal.
2. The supported range, and what it is (where adjusted sales land, not an opinion of the house).
3. The comps, each with what it was adjusted for and in plain language why.
4. **The exclusions, named, with reasons.**
5. The net sheet — what they actually keep at three prices.
6. What moves it: condition, and the compensation decision.
7. A dated next step.

Every figure must already exist in `adjusted.json` or `net_sheet.json`. If a number is genuinely
derived — the spread between two computed nets, say — mark that paragraph `[computed]` and a human
confirms it.

### 6. Gate

```bash
python3 scripts/brief_gate.py check --adjusted adjusted.json --net-sheet net_sheet.json \
  --brief brief.md --client {slug} | tee GATE.txt
```

| Gate | Refuses |
| --- | --- |
| `COMP_FLOOR` | a range built on fewer usable comps than the minimum |
| `ADJUSTED` | a ledger line with no arithmetic, or a ledger that does not sum to its own net |
| `EXCLUSIONS` | a comp dropped with no reason |
| `NET_SHEET` | a net sheet whose lines do not re-derive its totals |
| `GROUNDED` | any money figure in the brief that appears in no computed output |
| `NOT_APPRAISAL` | appraisal or valuation language, or a missing disclosure line |
| `COMPLIANCE` | the Fair Housing baseline, imported from `content-foundry` |

Fix the brief or the inputs, never the gate.

### 7. Hand off

The agent walks the house and sets the number from what they find. If the seller has already
consulted a chatbot — increasingly they have — run `/chatgpt-said` against the computed comp set
and fold the reconciliation in as a section.

## Setup

```bash
python3 scripts/doctor.py    # python, the content-foundry import, the live comp tier, full self-test
```
