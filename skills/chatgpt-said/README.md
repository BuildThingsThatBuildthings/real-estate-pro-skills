# chatgpt-said

Reconciles what a client's AI told them with what the agent's own record says, and produces a
client-ready document plus a talk track that never argues.

`SKILL.md` is the operating manual Claude follows. This file is the human summary.

## Why it exists

Sellers now show up to listing appointments with chatbot comps, and buyers reopen agreed offers
after consulting one. The agent's reflex is to correct: more comps, re-explain the pricing, push
back on what the client read.

That reflex loses, for a structural reason. Once it becomes the agent versus the algorithm, the
agent has already lost ground — the assistant reads as neutral and confident, and the agent reads
as an interested party defending a commission. You cannot win that frame. You can decline to
enter it.

So this skill does not write a rebuttal. It writes an account of what was checked, against what,
and what is genuinely still open.

## How it works

1. The client's AI output is captured **verbatim**.
2. `claim_split.py` cuts it into individually checkable claims — deterministically, so the same
   paste always yields the same claim ids and citations stay attached across re-splits.
3. The agent's own record goes into `facts.md` with sources. Nothing that is not in that file may
   be used to contradict anything.
4. Every claim gets one of five classes: `verified`, `contradicted`, `unknowable`, `stale`,
   `out_of_scope`. See `references/claim-classes.md`.
5. The reconciliation is written in a fixed order — agreement first, disagreement last. See
   `references/conversation.md`.
6. `reconcile_gate.py` refuses to let it out unless all seven gates pass.

## The gate

| Gate | Refuses |
| --- | --- |
| `CLASSIFIED` | a claim with no class, or a class outside the taxonomy |
| `SOURCED` | `verified`/`contradicted` with no source; `contradicted` with no correct value |
| `CITED` | a claim that never appears in the reconciliation |
| `GROUNDED` | a money or percentage figure that no cited claim carries and nothing marks |
| `NO_ARGUMENT` | adversarial framing |
| `REFERRALS` | out-of-scope claims with no referral section |
| `COMPLIANCE` | the Fair Housing baseline, imported from `content-foundry` |

`CITED` is the one that earns its keep. The tempting failure is to answer the eight easy claims and
quietly skip the ninth. A human reviewer will not catch that. The client will.

`GROUNDED` is the second. A rebuttal built on its own untraceable numbers loses harder than saying
nothing, because now there are two confident documents and only one of them has the agent's name
on it.

## The rule that matters most

The model never supplies a fact that must be exact. Comps, closed prices, days on market and tax
data come from the agent's record and are written into `claims.json`. The model writes narrative
over those numbers and nothing else.

## Dependencies

The sibling `content-foundry` skill. The Fair Housing baseline is **imported** from it, never
copied — a second copy of those rules would drift, and the copy that drifts is the one that
reaches a client.

```bash
python3 scripts/doctor.py     # checks the import and runs the full gate self-test
bash tests/run_tests.sh       # 14 assertions, including that all seven gates still fire
```

## What this is not

Not a valuation and not an appraisal, and it must never be described as one. Not a rebuttal
document. Not a listing presentation. And it sends nothing — the finished run goes to the agent,
who decides whether any of it reaches the client.
