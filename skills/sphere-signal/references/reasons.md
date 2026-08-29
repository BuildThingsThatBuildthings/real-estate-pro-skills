# Reasons

A touch needs a reason. Not a theme, not a campaign, not "it's been a while and
the calendar says Tuesday" — a specific dated fact from the agent's own records
that makes contacting this person today obviously appropriate.

`notice.py` computes them. It does not generate them, and it does not rank people.

## Why this is a script and not a prompt

Ask a model to "find who I should reach out to" and it returns a plausible list.
Plausible is the problem. The list looks right, so nobody checks it, and the
touches that follow are indistinguishable from a mail merge — which is how a
database learns to ignore an agent.

Every reason here traces to a date arithmetic step that a human can re-do on
paper. If the arithmetic is not there, the reason does not fire.

## The six

**`promise_due`** — the agent said they would do something by a date and has not.
Sorts above everything else, always. This is not a marketing touch. It is the
agent's own word, and the follow-up system's first job is to stop it from being
the thing that quietly erodes the relationship.

**`question_unanswered`** — they asked something and no later touchpoint answered
it. Requires an `id` on the asking touchpoint and `answers` pointing back at it on
a later one, which means the agent has to actually log the answer. That friction
is deliberate.

**`home_anniversary`** — a dated anniversary of a transaction the agent was part
of. Fires inside the configured lead window so there is time to do something with
it. Needs no pretext: it is a real date, about a real thing they did together.

**`holding_period`** — they have owned past the configured mark. This is the one
most easily abused. It licenses **asking**, never assuming. "You've been there
eight years, is a move anywhere on your mind" is a fair question. "I bet you're
ready to move up" is a guess about someone's life dressed as a service.

**`dormant`** — no contact in longer than the window. The weakest reason on the
list and the one to use last. Dormancy is a fact about the agent's behavior, not
about the contact's situation, so a dormancy touch has to bring something with it.

**`never_touched`** — in the database, never contacted at all. Usually means a
lead capture that went nowhere. Worth surfacing precisely because it is invisible
otherwise.

## What is refused outright

`notice.py` **aborts** — does not warn, does not skip — if the contacts file has a
column naming a protected class: race, religion, familial status, marital status,
age, disability, national origin, and the rest of the list in `FORBIDDEN_FIELDS`.

The reasoning is narrow and worth stating. Silently ignoring such a column leaves
it in the file, one edit away from being used, and leaves the agent believing the
system looked at it and decided it was fine. A refusal makes the agent remove it
from the export, which is the only outcome that actually helps them.

## Configuration

| Flag | Default | What moves it |
| --- | --- | --- |
| `--dormant-days` | 180 | How long is too long in this agent's practice |
| `--holding-period-years` | 7 | Local median tenure; 7 is a common national figure, not a law |
| `--anniversary-lead-days` | 21 | How far ahead the agent wants to see it coming |

Always pass `--today` explicitly. It makes a run reproducible, which means a
draft written on Monday still cites a reason that exists on Friday.

## Reasons are not a queue

A computed reason is permission to consider a touch, not an instruction to send
one. `touch_gate.py` reports reasons with no draft as a note, not a failure. An
agent who works four of six reasons well has done better than one who works all
six badly.
