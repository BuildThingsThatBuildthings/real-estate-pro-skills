---
name: sphere-signal
description: >
  Find the people in an agent's database who have a real, dated reason to hear from them this week,
  and draft the touch. Computes reasons from the agent's own records — a promise past its due date,
  a question never answered, a closing anniversary, a holding period, dormancy — then gates every
  draft: no touch without a computed reason, no opted-out contact, no channel they did not permit,
  no referral ask that was not earned, no inference about family, age or religion, no unsourced
  figure, and nothing ever sends. Triggers on "/sphere-signal", "who should I follow up with",
  "work my database", "sphere outreach", "reactivate my past clients", "who have I not talked to",
  "what should I send this week", and any request to plan follow-up across a contact list.
---

# sphere-signal — the next useful touch

Invocations:
- `/sphere-signal --agent {slug} --contacts {csv} --touchpoints {csv}` — full run
- `/sphere-signal reasons` — the reason types (`scripts/notice.py reasons`)
- `/sphere-signal gates` — what the gate refuses (`scripts/touch_gate.py gates`)
- `/sphere-signal resume {run-dir}` — resume at the first incomplete stage

Two thirds of closed seller business comes from an agent's sphere, and sphere
contacts convert several times better than bought leads. Almost half of agents never follow up
past the first attempt, and a typical database has most of its contacts untouched in six months.
The gap is not motivation. It is that nobody can look at two thousand rows and see who has an
actual reason behind them today.

This skill computes the reasons, drafts the touches, and refuses to let a touch out that has no
reason behind it.

Read `references/guardrails.md` before drafting anything. It is short and several of its rules are
not enforceable by the gate.

## Non-negotiable laws

1. **Never auto-send.** This skill produces drafts. A human decides what goes out. `NO_SEND`
   refuses any other status and there is no flag to disable it. This is the load-bearing law —
   everything else is trustworthy only because of it.
2. **A touch needs a computed reason.** Reasons come from `notice.py`, which derives them from
   dates in the agent's own records. A touch with no reason behind it is a mail merge, and a
   database learns to ignore those faster than it forgives them.
3. **Never infer who someone is.** No family status, age, religion, marital status, or judgments
   about what kind of person a place suits. `notice.py` refuses to read protected-class columns at
   all, so the drafting model never sees them, and `NO_INFERENCE` catches the phrasings that arise
   anyway. The licensee is liable regardless of who drafted the sentence.
4. **An ask is earned, never scheduled.** Referral, review and testimonial asks require an
   `earned_moment` naming the real thing that earned it. Never ask a contact who has an open
   `promise_due` — fix that first.
5. **Consent is per channel and opt-outs are absolute.** An email address is not permission to
   text. Opted-out contacts are dropped at the scan, before drafting.
6. **Figures carry sources.** Any price or percentage in a draft needs `[source: ...]`,
   `[verified]` or `[VERIFY]`. A wrong number in a text message is as wrong as one in a listing
   presentation.
7. **`holding_period` licenses asking, never assuming.** "You've been there eight years, is a move
   on your mind" is a question. "I bet you're ready to move up" is a guess about someone's life.
8. **Measure inputs, not outputs.** Records reviewed, reasons worked, drafts approved, promises
   kept by the date given. Never set a reply or appointment target and treat it as a dial.
9. **One agent per run.** Contacts, voice and disclosure facts come from that agent only.

## Stages

```
runs/{agent}/{yyyy-mm-dd}/
  contacts.csv       1. the agent's contacts, protected-class columns removed
  touchpoints.csv    1. append-only history
  reasons.json       2. computed, with the arithmetic behind each
  research.md        3. what was checked before drafting
  drafts.json        4. one draft per worked reason
  GATE.txt           5. the gate output that approved them
```

### 1. Load the records

Two CSVs the agent already has, or can export from any CRM.

`contacts.csv` — `id`, `name`, `closed_date`, `channels` (pipe-separated), `opted_out`, `notes`.
`touchpoints.csv` — `id`, `contact_id`, `date`, `summary`, `promise`, `promise_due`,
`promise_done`, `open_question`, `answers`.

If the export carries a column naming a protected class, the scan **aborts**. Remove the column
from the export rather than working around it — the point is that it is not in the file the
drafting model reads.

### 2. Notice

```bash
python3 scripts/notice.py scan --contacts contacts.csv --touchpoints touchpoints.csv \
  --today 2026-08-29 --out reasons.json
```

Always pass `--today`. It makes the run reproducible, so a draft written Monday still cites a
reason that exists Friday. Reason types and their tuning flags are in `references/reasons.md`.

Read the reasons before drafting. `promise_due` sorts first for a reason: it is the agent's own
unkept word, and it outranks anything the marketing calendar wants.

### 3. Research, then draft

For each reason the agent chooses to work, find something genuinely useful to bring — the answer
to the question they asked, the settlement statement that was promised, the number they wanted.
Then draft.

Every touch **gives** something. A reason to reach out is not the same as something to say. A
dormancy touch with nothing in it is worse than silence, because it spends the relationship to buy
nothing.

Write into `drafts.json`: `id`, `contact_id`, `reason_id`, `channel`, `status: "draft"`,
`asks` (`none`/`referral`/`testimonial`/`review`), `earned_moment`, `body`.

Not every reason needs a draft. Four worked well beats six worked badly, and the gate reports
unworked reasons as a note rather than a failure.

### 4. Gate

```bash
python3 scripts/touch_gate.py check --drafts drafts.json --reasons reasons.json \
  --contacts contacts.csv --client {slug} | tee GATE.txt
```

| Gate | Refuses |
| --- | --- |
| `REASON` | a draft with no computed reason, or one `notice.py` never produced |
| `CONSENT` | an opted-out contact, or a channel they did not permit |
| `EARNED` | a referral, review or testimonial ask with no earned moment |
| `NO_INFERENCE` | language inferring family, age, religion, or who a place suits |
| `FACTS` | a price or percentage with no source marker |
| `NO_SEND` | any draft not in status `draft` |
| `COMPLIANCE` | the Fair Housing baseline, imported from `content-foundry` |

Fix the drafts, not the gate. If a gate looks wrong, add the case to `tests/` before changing the
rule.

### 5. Hand off

Give the agent the run directory. They approve, edit or discard each draft and send it themselves
from their own account. Then log what happened back into `touchpoints.csv` — including the promise
made and its due date, because that is what next week's `promise_due` reads.

The loop only compounds if step 5 gets written down.

## Setup

```bash
python3 scripts/doctor.py    # python, the content-foundry import, and a full gate self-test
```

The only hard dependency is the sibling `content-foundry` skill: the Fair Housing baseline is
imported from it rather than copied, because a second copy would drift and the drifted copy is the
one that reaches a client.
