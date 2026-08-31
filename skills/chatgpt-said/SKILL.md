---
name: chatgpt-said
description: >
  Reconcile what a client's AI told them with what the agent's own record says, and produce a
  client-ready document plus a talk track that never argues. Takes the chatbot output verbatim,
  splits it into individually checkable claims, classes each one as verified / contradicted /
  unknowable / stale / out-of-scope against the agent's comps and records, and gates the result:
  no dropped claim, no untraceable number, no adversarial framing, no Fair Housing problem, and
  legal or tax questions referred rather than answered. Triggers on "/chatgpt-said", "my seller
  brought ChatGPT comps", "the buyer says AI told them to offer less", "client is arguing about
  price using AI", "they ran a Zestimate and a chatbot", and any request to respond to a client's
  AI-generated valuation or advice.
---

# chatgpt-said — reconcile the client's AI with your file

Invocations:
- `/chatgpt-said --agent {slug} --property "{address}" --paste {file}` — full run
- `/chatgpt-said --agent {slug} --property "{address}"` — paste the client's output when prompted
- `/chatgpt-said resume {run-dir}` — resume at the first incomplete stage
- `/chatgpt-said classes` — print the taxonomy (`scripts/reconcile_gate.py classes`)

Sellers now arrive at listing appointments with chatbot comps, and buyers reopen agreed offers
after consulting one. The reflex is to argue. Arguing loses, because the assistant reads as
neutral and the agent reads as an interested party. This skill produces the other move: a written
account of what was checked, against what, and what is genuinely still open.

Read `references/conversation.md` before writing a word of the reconciliation. It is short, and
the order it prescribes matters more than the content.

## Non-negotiable laws

1. **The client's words are captured verbatim.** Never paraphrase, summarize or tidy the chatbot
   output before splitting it. Paraphrase is where the claim list quietly drifts toward the claims
   that are easy to rebut.
2. **Every claim gets a class, and every claim gets cited.** The splitter found it; the agent
   answers for it, even when the answer is "I can't speak to that one." The gate refuses a
   reconciliation with a claim missing. Silently dropping the inconvenient claim is the failure
   mode a human reviewer will not catch and the client will.
3. **The model never supplies a fact that must be exact.** Comps, closed prices, days on market,
   tax data and dates come from the agent's own record and are written into `claims.json` as
   `source` and `correct_value`. The model writes narrative over those numbers and nothing else.
   Every figure in the reconciliation must trace to a cited claim, or be marked `[verified]` or
   `[computed]` for a human to confirm.
4. **Never argue.** No "actually", no "that's incorrect", no "AI is unreliable", no credentials as
   evidence. `reconcile_gate.py` enforces this and the list of blocked phrasings is in
   `references/conversation.md` with the reason for each.
5. **The gate must be able to fail.** `tests/run_tests.sh` proves all seven gates still fire.
   Never reach for `--lenient` to turn a run green; it exists for drafts, not for delivery.
6. **Refer, do not answer.** Legal, tax, appraisal and lending questions are `out_of_scope` and get
   a referral section. "I'm not a CPA, but" is giving tax advice with a disclaimer attached.
7. **This is not a valuation or an appraisal** and must never be presented as one. It is a
   reconciliation of two documents.
8. **Nothing here sends, posts or files anything.** The finished set goes to the agent, who decides
   whether any of it reaches the client. Inherited from `content-foundry` law 5.
9. **One agent per run.** Brand, disclosure and license facts come from that agent's folder only.
   Never carry a fact between runs from memory.

## Stages

Write each stage to disk before starting the next, so `resume` works and so a review can see what
was known at each point.

```
runs/{agent}/{yyyy-mm-dd}-{property-slug}/
  chatbot.txt        1. the client's AI output, verbatim
  facts.md           2. the agent's record, with sources
  claims.json        3. split, then 4. classified
  reconciliation.md  5. client-facing
  talk-track.md      5. agent-facing
  deliver/          client-facing artifacts, and only these, go to Drive
  GATE.txt           6. the gate output that let it out
```

### 1. Capture

Get the client's AI output **verbatim** into `chatbot.txt`. A screenshot is fine as an input, but
transcribe it exactly — including hedges, bullets and the parts that agree with the agent.

Record what produced it and when in `--source` (for example `"seller's ChatGPT, 2026-08-28"`). A
claim from an assistant with browsing and a claim from one without are different claims, and the
date decides what counts as stale.

### 2. Gather the agent's record — before classifying anything

Write `facts.md`: the comp set with its pull date, tax record, market stats, and anything the agent
knows that is not in public data. Every entry carries a source.

**If a fact is not in `facts.md`, it cannot be used to contradict anything.** Do not go find a
number that supports a rebuttal. Ask the agent for their record and work from it. If the agent's
own file cannot settle a claim, that claim is not `contradicted` — it is unclassified until it is.

### 3. Split

```bash
python3 scripts/claim_split.py split --in chatbot.txt --out claims.json --source "seller's ChatGPT, 2026-08-28"
python3 scripts/claim_split.py show --claims claims.json
```

Deterministic: the same paste yields the same claim ids, so citations written earlier stay attached
after a re-split. Read every claim. If one starts mid-clause or fuses two assertions, fix
`chatbot.txt` and split again rather than working around it.

### 4. Classify

Fill `class`, and where required `source`, `correct_value` and `note`, for **every** claim. The
taxonomy and how to apply it is `references/claim-classes.md`. Do this with the agent, not for
them — several classes turn on things only they know.

`unknowable` is not a parking space for claims nobody checked. If it is checkable and it was not
checked, it is not classified yet.

### 5. Write

`reconciliation.md`, client-facing, in the order set out in `references/conversation.md`: credit
the research, agreement first, what has moved, what it could not see, where the files differ, not
my lane, next concrete step.

Cite as you go. `[C-xxxxxx]` for anything a claim carries, `[verified]` for a figure from the
agent's own record, `[computed]` for one derived from figures already cited. Citations govern the
paragraph they appear in.

`talk-track.md`, agent-facing: the same material as things to say out loud, plus the two or three
questions the client is most likely to ask back.

### 6. Gate

```bash
python3 scripts/reconcile_gate.py check \
  --claims claims.json --reconciliation reconciliation.md --client {slug} | tee GATE.txt
```

Seven gates, all of which must pass:

| Gate | Refuses |
| --- | --- |
| `CLASSIFIED` | any claim with no class, or a class outside the taxonomy |
| `SOURCED` | `verified`/`contradicted` with no source; `contradicted` with no `correct_value` |
| `CITED` | any claim that never appears in the reconciliation |
| `GROUNDED` | any money or percentage figure that no cited claim carries and nothing marks |
| `NO_ARGUMENT` | adversarial framing |
| `REFERRALS` | `out_of_scope` claims with no referral section |
| `COMPLIANCE` | Fair Housing baseline and the client's GUARDRAILS card, via `content-foundry` |

Fix the document, not the gate. If a gate looks wrong, it is a bug worth a test — add the case to
`tests/` before changing the rule.

### 7. Hand off

Deliver the run directory to the agent. Say plainly which claims stayed `unknowable` and which
figures rest on `[verified]` rather than a claim, because those are the two places a human still
has to look.

### 8. Deliver to `01 Waiting`

Everything this run produced goes to the client's Waiting folder, in its own
dated folder, and stops there. The client moves it to Approved. Nothing here
publishes.

Put the client-facing artifacts in `deliver/` inside the run directory — `reconciliation.md` for the client, and `talk-track.md` if the agent wants it in the same place.
Working files stay behind — a review queue full of JSON is a review queue nobody reads.

Using the Drive connector (default, no setup):

```
create_file  title: "2026-08-29 — Client AI Reconciliation — 412 Maple Ridge Dr"
             mimeType: "application/vnd.google-apps.folder"
             parentId: "<the client's 01 Waiting folder id>"
```

then one `create_file` per artifact into that folder, with
`disableConversionToGoogleType: true` to keep markdown as markdown.

Full detail, including how to find the Waiting folder id once and how to clear a
processed drop folder: [`docs/drive-delivery.md`](../../docs/drive-delivery.md).

## Setup

```bash
python3 scripts/doctor.py    # python, the content-foundry import, and a full gate self-test
```

The only hard dependency is the sibling `content-foundry` skill: the Fair Housing baseline is
imported from it rather than copied, because a second copy would drift and the drifted copy is the
one that reaches a client. `--client {slug}` additionally merges that client's GUARDRAILS card
when `config/clients.json` is configured; without it the baseline still runs.
