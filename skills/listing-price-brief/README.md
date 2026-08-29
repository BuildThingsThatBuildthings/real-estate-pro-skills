# listing-price-brief

Builds a seller-ready pricing brief from real comps: a supported range, a per-comp adjustment
ledger, named exclusions, and a written net-proceeds sheet at three prices.

`SKILL.md` is the operating manual Claude follows. This file is the human summary.

## Why it exists

Clean, accurate CMAs and better pricing narratives sit at the top of agents' stated AI wish list.
Pricing is also the thing they trust AI with least — under half are confident putting AI output in
front of a client at all, and accuracy is the most-cited reason.

Those two facts have one cause. A model that writes a confident price narrative using numbers it
made up is worse than no help: the seller keeps the number, the agent owns it in front of an
appraiser, and nothing behind it can be re-derived.

So this skill splits the work at the seam that actually matters. **Python computes. The model
explains.** Every price, adjustment, range and net figure comes out of a script, and the gate
refuses any money figure in the brief that appears in no computed output.

## How it works

```
comp_source.py  acquire and normalize   ->  comps.json
comps.py        adjust, arithmetically  ->  adjusted.json   (ledgers, exclusions, range)
net_sheet.py    three scenarios         ->  net_sheet.json
brief_gate.py   seven gates             ->  pass or nothing goes out
```

Every adjustment is a ledger line — feature, subject value, comp value, rate, dollars, formula —
so a seller can follow it on paper. The gate re-derives each one and refuses a ledger that does
not sum to its own net.

## Getting comps

Three tiers, in the order to reach for them:

| Tier | What it is | Needs |
| --- | --- | --- |
| `export` | agent exports from their own MLS or RPR | nothing; RPR comes with NAR membership |
| `browser` | supervised session, agent logged in and present | per-market config, and the constraints in `browser-plan` |
| `reso` | RESO Web API 2.0, fully unattended | the broker's signed IDX/VOW agreement with that MLS |

`export` always works and every other tier degrades to it. The browser tier is deliberately narrow:
MLS rules of use are per-MLS, and credential sharing or unattended retrieval is a violation at
nearly every board — with the suspension and the fine landing on the sponsoring agent, not on the
software. A tool that quietly makes an agent non-compliant has cost them more than it saved.

## The gates that earn their keep

**`GROUNDED`** — every money figure traces to a computed value. This is the whole product.

**`EXCLUSIONS`** — a comp dropped without a reason is refused, because an unexplained exclusion is
indistinguishable from cherry-picking. Named exclusions are also the most persuasive part of the
brief: the new-construction sale backing the golf course is exactly the comp an online estimate
finds first, and the seller has usually already seen it.

**`NOT_APPRAISAL`** — refuses appraisal and valuation language, and refuses a brief with no
disclosure line. Appraisal is a licensed act.

**`COMP_FLOOR`** — below three usable comps, `net_sheet.py` refuses to build at all. A net sheet on
an unsupported price is a number the seller will hold the agent to for the whole listing.

## One detail worth knowing

Round numbers in the brief are **computed**, not rounded in prose. A figure the model rounded is a
figure the model produced, and the gate cannot trace it. So `comps.py` emits
`supported_low_rounded` alongside the exact value, and the brief cites that.

## Dependencies

The sibling `content-foundry` skill, for the Fair Housing baseline — imported, never copied.

```bash
python3 scripts/doctor.py     # checks the import, reports the live comp tier, runs the self-test
bash tests/run_tests.sh       # 20 assertions, including that all seven gates still fire
```

## What this is not

Not an appraisal and not a valuation. Not a substitute for the agent walking the house — condition
is the input the scripts cannot supply and the one that moves the number most. And it sends
nothing.
