# sphere-signal

Finds the people in an agent's database who have a real, dated reason to hear from them this week,
drafts the touch, and refuses to let anything out that has no reason behind it.

`SKILL.md` is the operating manual Claude follows. This file is the human summary.

## Why it exists

Two thirds of closed seller business comes from an agent's sphere, and those contacts convert
several times better than bought leads. Almost half of agents never follow up past the first
attempt, and most of a typical database goes untouched for six months at a stretch.

That is not a motivation problem. Nobody can look at two thousand rows and see which ones have an
actual reason behind them today. So agents either send nothing, or send everyone the same thing —
and the second option is worse, because it teaches the database to ignore them.

It is also the missing half of `content-foundry`. Content answers *what to say*. This answers *who
has a reason to hear it, and why* — which is the difference between twenty assets a month and
twenty reasons to talk to someone.

## How it works

`notice.py` computes reasons from the agent's own records. Six types, most urgent first:

| Reason | Fires when |
| --- | --- |
| `promise_due` | the agent said they'd do something by a date and hasn't |
| `question_unanswered` | they asked something and no later touchpoint answered it |
| `home_anniversary` | a dated anniversary of a transaction, inside the lead window |
| `holding_period` | they've owned past the configured mark — licenses **asking**, never assuming |
| `dormant` | no contact in longer than the window |
| `never_touched` | in the database, never contacted at all |

Every reason carries the arithmetic that produced it. Nothing is scored, nobody is ranked, and no
one surfaces because of who they are — only because of a date they gave the agent or a promise the
agent made.

Then the model researches and drafts, and `touch_gate.py` decides whether any of it is allowed out.

## The two gates that matter

**`NO_SEND`** refuses any draft not in status `draft`. There is no flag to disable it. An automated
follow-up system with send access will eventually send something wrong to someone who mattered,
and the agent's name is on it.

**`NO_INFERENCE`** blocks language guessing at family status, age, religion, or what kind of person
a place suits. The blocked phrases read as ordinary warm copy — "now that the kids are older",
"great for families" — which is exactly why a machine has to catch them. A licensee writing to a
consumer about housing is inside the Fair Housing Act, and "the AI wrote it" is not a defense.

The upstream protection matters more: `notice.py` **aborts** if the contacts file has a column
naming a protected class. Not a warning, not a skip. Ignoring it silently would leave it in the
file one edit away from being used.

## The rule that matters most

Every touch gives something. A reason to reach out is not the same as something to say. A check-in
with nothing in it is worse than silence, because it spends the relationship to buy nothing.

## Dependencies

The sibling `content-foundry` skill. The Fair Housing baseline is **imported** from it, never
copied — one copy of those rules in the bundle.

```bash
python3 scripts/doctor.py     # checks the import and runs the full self-test
bash tests/run_tests.sh       # 16 assertions, including that all seven gates still fire
```

## What this is not

Not a CRM and not a replacement for one — it reads two CSVs any CRM can export. Not an autoresponder.
Not a lead scorer. And it sends nothing: the run goes to the agent, who sends from their own account.
