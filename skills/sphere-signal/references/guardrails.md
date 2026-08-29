# Guardrails

From the operating sequence this skill implements:

```
capture -> remember -> notice -> research -> draft -> human review -> communicate -> log -> learn
```

`notice.py` is *notice*. The model does *research* and *draft*. **Human review is a
person, every time.** This skill stops before *communicate* and always will.

## Never auto-send

`NO_SEND` refuses any draft not in status `draft`. There is no flag to turn this
off and no configuration that enables sending.

This is not caution for its own sake. An automated follow-up system with send
access will eventually send something wrong to someone who mattered, and the
agent's name is on it. Keeping a person between the draft and the recipient costs
minutes a week and is the entire reason the output can be trusted.

## Never infer who someone is

`NO_INFERENCE` blocks language that guesses at family status, age, religion,
marital status, or what kind of person a place suits. The blocked phrases read as
ordinary warm copy — "now that the kids are older", "great for families",
"perfect neighborhood for you" — which is exactly why a machine has to catch them.

A licensee writing to a consumer about housing is inside the Fair Housing Act. The
licensee is liable regardless of who or what drafted the sentence; "the AI wrote
it" is not a defense, and HUD confirmed in 2024 that the Act reaches AI-generated
content. A friendly tone is not a mitigating factor.

The upstream protection matters more than the gate: `notice.py` refuses to read
protected-class columns at all, so the drafting model never sees them.

## An ask has to be earned

`EARNED` refuses a referral, review or testimonial ask with no `earned_moment`.

The calendar is not permission. A quarterly "who do you know" is the fastest way
to teach a database that the agent contacts them when the agent needs something.
An ask follows a real positive moment — a closing that went well, a referral they
already sent, a problem the agent solved — and the moment goes in the field so a
reviewer can see it.

Corollary the gate cannot enforce, so it goes here: **never ask after an
unresolved problem.** If the same contact has an open `promise_due`, fix that
first and let the ask wait.

## Consent is per channel

`CONSENT` refuses opted-out contacts and channels the contact did not permit.
Someone who gave an email address did not thereby consent to texts. Opt-outs are
absolute and are honored at the scan, before drafting, so an opted-out person is
never even considered.

## Facts carry sources

`FACTS` refuses a price or percentage with no `[source: ...]`, `[verified]` or
`[VERIFY]` marker. Market numbers in a casual check-in are still market numbers,
and a wrong one in a text message is as wrong as a wrong one in a listing
presentation.

## Measure what the agent controls

Count inputs: records reviewed, reasons worked, drafts approved, promises kept by
the date given. Do not set a target for replies, appointments or listings and then
treat it as a dial — it is not one, and treating it as one produces volume, which
is the failure this whole design is built to avoid.

AI's job here is to lower the time cost of the inputs and raise their relevance.
It should never inflate activity by generating touches nobody needed.
