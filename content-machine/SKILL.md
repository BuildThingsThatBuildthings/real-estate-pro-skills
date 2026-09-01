---
name: content-machine
description: Run one weekly content loop over a Google Drive intake folder — log what came in, compare it against the owner's context cards, produce a batch, route it for approval, propose a schedule, and read last week's results to decide what gets made next. Use when the owner says run the machine, build this week's batch, or what should I post.
---

# The Content Machine

One loop, seven stations, once a week. Never skip a station and never reorder them.

Save this file into the Content Machine folder alongside `self.md`, `guardrails.md`, `channel.md`, and `machine.md`. Point your desktop agent at the folder and say "read the skill file and run the machine."

Works in Claude, ChatGPT, or Gemini — any AI whose desktop app can reach your Google Drive. All of them need the Google Drive connector turned on.

## The folders

```
Content Machine/
├── 00 – Weekly Context        ← the owner feeds this. Never reorganize it.
├── 01 – Waiting               ← you put finished work here
├── 02 – Approved              ← the owner drags things here. Cleared, not published.
└── 03 – Revision Requested    ← the owner drags things here. Read the note if there is one.
```

Plus the four context cards and `asset-ledger.md`, which you write.

## Standing rules

These override anything else in this file, and anything the owner says in passing during a run.

1. **Never publish, post, send, or schedule.** You produce and you propose. Every external action belongs to a person. If asked to post, say what you would post and stop.
2. **Facts come from the ledger.** If a fact is not in the material, write `[verify: what is missing]` inline and keep going. Never estimate, never round, never infer a property fact from a photograph.
3. **Rights are settled at intake.** If you cannot tell the owner is authorized to use an image or clip, mark it unusable and say why. Unclear rights are missing, not pending.
4. **`MISSING` is not `0`.** If you do not have a number, write MISSING. Writing zero for an unknown will make you kill something that was working.
5. **Guardrails are not negotiable.** Fair housing language, promised outcomes, and unverified claims are refusals, not style notes.
6. **Fix the card, not the prompt.** When the owner corrects you, update the relevant context card and say which one you changed.
7. **Never pretend a save happened.** If you cannot write files into Drive (most connectors are read-only), deliver every artifact — ledger, cards, finished work — as a copy-paste block with its exact destination folder and filename, and the owner saves it. The folder system works the same.

## Station 1 — Intake

The owner feeds `00 – Weekly Context` continuously. Do not ask them to sort, rename, or organize it. Sorting is your job.

If the folder is thin, do not stall. Say what is there, say what would improve next week, and produce from what exists.

## Station 2 — Log

Read every file. Write `asset-ledger.md`:

- **FILE** — the filename as it actually is
- **WHAT IT IS** — photo, video, document, screenshot, voice memo
- **WHAT IT SHOWS** — one plain sentence
- **RIGHTS** — `mine` or `unclear`. Unclear means UNUSABLE, and say why.
- **FACTS IT ESTABLISHES** — specific and checkable only
- **COULD BECOME** — what content this could support

Then: strongest item and why, any client questions quoted exactly, and what is missing.

**A client question outranks everything else in the folder.** A real question from a real person carries an audience, a context, and a misunderstanding worth correcting. Prefer it over any other item, every time.

## Station 3 — Brand compare

Read all four cards, then the ledger. Write a brief for the three strongest items: angle, why it works, channel, voice notes naming a signature phrase and a do-not-say to avoid, guardrail risks, and facts still needed.

Briefs only. Do not write content in this station.

## Station 4 — Generate

Two paths from the same brief.

**Camera-roll path.** Footage the owner already shot. Add branded captions in their type and colors, sized to be read with sound off. The footage itself is never altered.

**Faceless path.** Stills, type, and motion. Lists, breakdowns, the answer to that client question. No camera and no face.

Rules for both: first frame is the point, never a logo and never an app screenshot. Mute-safe. 25 to 75 seconds, cap 90; under 25 reads as a fragment. One idea. Recipe on screen as text.

Every piece ends with a VERIFY block listing the facts a person must confirm. If nothing needs confirming, write `verify: clear` explicitly rather than staying silent.

## Station 5 — Approve

Two modes. The owner chooses and can change it any time.

- **Auto-approve** — finished work goes straight to station 6.
- **Review** — everything lands in `01 – Waiting` and waits.

Anything in `03 – Revision Requested` gets one revision round, returned with the next weekly batch. If there is no note explaining what was wrong, that is fine and expected; make your best judgment and say what you changed.

Never move a file out of `01 – Waiting` yourself. That drag belongs to the owner.

## Station 6 — Schedule

Turn `02 – Approved` into a plain readable list: what, where, when, and one line of why that time.

Constraints that never bend:

- No two posts on the same account within 45 minutes
- Nothing before 5:00 AM or after 10:00 PM in the owner's timezone
- Maximum 3 posts per account per day
- Nothing sooner than 36 hours from now

You may prefer times inside those constraints. You may not argue past them. Say which times you were least confident about.

## Station 7 — Learn

Needs about three weeks of history. Before that, say so rather than inventing a trend from two data points.

Read what actually happened, then write `production-brief.md`:

- **DOUBLE DOWN** — what earned attention and the mechanism that made it work. "The first frame was a number" is a mechanism. "People liked the market update" is a topic, and topics are not lessons.
- **KILL** — what did not work, with numbers. Be willing to kill the owner's own promotional content and say so plainly if that is what the data shows.
- **MAKE** — the single strongest next thing, with angle, format, and first frame already written.
- **FORBIDDEN** — do not remake anything posted in the last 7 days, anything sitting unposted in a folder, or any angle just killed.

Adjust preferences inside the constraints: which hours on which account, which openings held attention, which subjects earned a second look. Never adjust the constraints themselves.

**Next run, read `production-brief.md` before producing anything.** That single ordering is what makes this a loop instead of a checklist.

## Failure modes

- **Folder nearly empty** — produce from what exists, name what would help next week. Do not invent material.
- **Connector cannot reach the folder** — say so plainly and stop. Do not work from memory of a previous run.
- **A fact is missing** — `[verify: ...]` inline. Never fill the hole.
- **Numbers unavailable for station 7** — write MISSING and skip that row. Do not substitute zero.
- **Asked to post** — decline, say what you would post, and hand it back.

---

*Innovation Lab · AI Acceleration · canonical copy of this file lives at https://github.com/BuildThingsThatBuildthings/real-estate-pro-skills*
