# Content Machine — Prompt Pack

Seven stations, seven prompts. Copy-paste ready.

These work in Claude Desktop or ChatGPT desktop. Both need the Google Drive connector turned on and pointed at your Content Machine folder.

**Before any of these:** no client names, no addresses, no phone numbers, no emails, no financials go into these tools. Placeholders work fine.

---

## Station 2 — The asset ledger

Run this after you have dropped things into `00 – Weekly Context`.

```
Read every file in my "00 – Weekly Context" folder.

For each one, write a row with:
- FILE: the filename as it actually is
- WHAT IT IS: photo, video, document, screenshot, voice memo, other
- WHAT IT SHOWS: one plain sentence
- RIGHTS: "mine" if it is obviously my own photo or document, "unclear" if
  you cannot tell. If unclear, mark the item UNUSABLE and say why.
- FACTS IT ESTABLISHES: anything specific and checkable. Numbers, dates,
  addresses, features. If there are none, say none.
- COULD BECOME: what kind of content this could support

Then write three lines at the bottom:
- STRONGEST ITEM and why
- ANY CLIENT QUESTIONS you found, quoted exactly
- WHAT IS MISSING that would make this week's batch better

RULES: Do not guess at rights. Do not infer a fact from a photograph. If a
file is unreadable, say so rather than describing what you assume is in it.
Save the result as asset-ledger.md in the Content Machine folder.
```

---

## Station 3 — The brand-compare pass

Run this once the four context cards are in the folder.

```
Read these four files from my Content Machine folder: self.md,
guardrails.md, channel.md, machine.md. Then read asset-ledger.md.

For the three strongest items in the ledger, write a short brief each:

- ITEM: which ledger row
- ANGLE: what this piece is actually about, in one sentence
- WHY IT WORKS: what makes it worth someone's attention
- CHANNEL: where it belongs and why, using channel.md
- VOICE NOTES: which parts of self.md matter most here. Name at least one
  signature phrase and one thing on my do-not-say list to avoid.
- GUARDRAIL CHECK: anything in guardrails.md this angle risks tripping
- FACTS NEEDED: what I have to confirm before this can go out

Do not write the content yet. Briefs only.
```

---

## Station 4a — The still

```
Using the brief for the strongest item, write one still-image post.

Give me:
1. ON-IMAGE TEXT. Short. The first thing a scrolling person reads.
2. CAPTION. Follow channel.md for length on the destination channel.
3. DESTINATION. One channel, and say why that one.

RULES:
- Use only facts from the ledger. Missing fact means write
  [verify: what is missing] inline. Never estimate, never round.
- Match self.md. No phrase from my do-not-say list.
- Run it against guardrails.md before showing me. If something trips,
  fix it and tell me what you fixed.
- No hashtag piles. Semantic keywords in the prose instead.
- End with a VERIFY block listing every fact I must confirm. If nothing
  needs confirming, write "verify: clear".
```

---

## Station 4b — The faceless video script

```
Using the brief for the second item, write one faceless video script.

Structure:
- FIRST FRAME: the literal text on screen at second zero. This must be
  the point: the stat, the question, or the promise. Never a logo. Never
  a screenshot of an app.
- BEATS: the body, written the way I would say it out loud
- CLOSE: one specific next step
- ON-SCREEN TEXT: the recipe or steps as text, not just narration

RULES:
- 25 to 75 seconds when read at a normal pace. Under 25 reads as a
  fragment. Cap at 90.
- Mute-safe. If it only works with sound on, rewrite it.
- One idea. If you have two, tell me and I will pick.
- Facts from the ledger only, [verify: ...] for anything missing.
- Check guardrails.md before showing me.
- I am not on camera. Do not write a piece to camera.
```

---

## Station 6 — The schedule

```
Read everything in my "02 – Approved" folder.

Write a schedule as a plain list I can read. For each item:
- WHAT: which asset
- WHERE: which channel and account
- WHEN: day and time, in my timezone
- WHY THAT TIME: one line

RULES THAT DO NOT BEND:
- No two posts on the same account within 45 minutes
- Nothing before 5:00 AM or after 10:00 PM my time
- Maximum 3 posts per account per day
- Nothing scheduled sooner than 36 hours from now

You are writing a list. You are not publishing anything and you are not
connecting to any social account. I will move these into my scheduler
myself.

After the list, tell me which times you were least confident about.
```

---

## Station 7 — The weekly learning pass

Run this after you have three weeks of posts behind you. Before that it has nothing to read.

```
Here is what happened to everything I posted in the last 7 days:
[paste your numbers: post, channel, views, and any engagement you have]

Write me a production brief with four sections:

DOUBLE DOWN — what earned attention and what specifically made it work.
Name the mechanism, not the topic. "The first frame was a number" is
useful. "People liked the market update" is not.

KILL — what did not work, with the numbers next to it. Be willing to kill
my own promotional content. Say so plainly if that is what the data says.

MAKE — the single strongest thing to produce next, with the angle, the
format, and the first frame already written.

FORBIDDEN — what not to remake this week. Anything I posted in the last
7 days, anything already sitting unposted in a folder, and any angle
that just got killed above.

RULES:
- If a number is missing, write MISSING. Never write 0 for a number you
  do not have. Those are different facts and confusing them will make
  you kill something that was actually working.
- Do not invent metrics. If I did not give you a number, you do not
  have it.
- Views alone are not a lesson. Say what the piece taught someone.

Save this as production-brief.md. Next week, read it before you make
anything.
```

---

## The one that fixes everything

When output is wrong, resist rewriting the prompt. Fix the card instead.

```
That draft used [phrase] and it does not sound like me.

Add it to the do-not-say list in self.md, and tell me what you would
have written instead. Then show me the corrected draft.
```

Prompt corrections die when the chat ends. Card corrections persist. This is the difference between a machine that gets better and one that resets every week.

---

*Innovation Lab · AI Acceleration · canonical copy: github.com/BuildThingsThatBuildthings/real-estate-pro-skills*
