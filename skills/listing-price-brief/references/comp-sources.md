# Getting the comps

Three tiers. Reach for them in this order, and never let a lower tier fail
silently into a higher one.

## `export` — always available, always the fallback

The agent exports comps from their own MLS, or from RPR, and drops the file.
`comp_source.py` normalizes the headers.

RPR is included with NAR membership at no additional cost, which makes this tier
available to essentially every REALTOR without a new subscription or agreement.

This tier must never stop working. It is what every other tier degrades to.

**Do not hand-edit an export to make it load.** If a header is not recognized,
map it: `--map '{"Your Header": "close_price"}'`. A hand-edited export is a comp
set nobody can reproduce, which defeats the point of computing the range at all.

## `browser` — supervised session only

A browser agent drives the agent's own logged-in MLS session and runs the search
the agent would have run themselves.

Run `comp_source.py browser-plan` for the checklist. The constraints are not
preferences:

- The **agent** logs in. Credentials are never requested, stored, or replayed.
- The agent is **present** for the whole pull. If they step away, it stops.
- The search is the one they would have run — their subject, radius, date window,
  property type. Not a broader sweep because a broader sweep is available.
- One result set. No pagination beyond what a person would click, no background
  refresh, **no schedule**.
- The result goes straight into the `export` normalizer, so the audit trail is
  identical either way.
- Who pulled it, when, and from which MLS goes in the run directory.

**Why so tight.** MLS rules of use are per-MLS and enforced. Credential sharing
and unattended automated retrieval are violations at nearly every board, and the
suspension and the fine land on the sponsoring agent, not on the software. A tool
that quietly makes an agent non-compliant has cost them more than it saved.

If any constraint cannot be met, use `export`. That is not a downgrade.

## `reso` — RESO Web API 2.0

REST/OData with OAuth 2.0, the modern replacement for RETS and the right answer
for any new integration. This is the only tier that is legitimately unattended.

It requires the broker's signed IDX or VOW agreement with that MLS, and a
vendor-operated feed additionally needs an approved vendor agreement and a data
use agreement. Both are per-MLS. That is why this is configured per market in
`config/mls.json` or not at all — there is no national switch to flip.

Worth pursuing market by market once volume justifies the paperwork.

## What no tier does

None of them invent a comp. `comp_source.py` reads what it is given and
normalizes it. If a required field is missing it aborts and names the field,
because a comp set with holes produces a range with holes and the range is the
only thing the seller remembers.
