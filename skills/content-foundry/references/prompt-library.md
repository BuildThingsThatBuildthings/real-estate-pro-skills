# Prompt Library

Organized by **realtor job-to-be-done**, not by format. Each entry sets the default engine, default
channels, and research depth. Freehand prompting bypasses this file entirely and runs the identical
pipeline — the library is a shortcut, not a gate.

**Research depth:** `skip` (no web search) · `light` (verify facts present in the drop) ·
`deep` (source and cite market statistics).

---

## 1. New listing announcement

- **Engine:** stills (carousel or single) · **Channels:** ig, fb, li · **Research:** light
- **Needs from drop:** listing photos, address or MLS sheet
- **Prompt:** Announce {address} — {beds}bd/{baths}ba, {sqft} sqft, {price}. Lead with the single
  most distinctive feature visible in the photos, not the price. One idea per asset.
- **Composite:** logo bottom-{placement}, license + disclosure bottom edge, price as accent-color type.
- **Watch:** Fair Housing — describe the *property*, never the buyer who'd suit it. No "perfect for
  families," "safe neighborhood," or school-quality claims.

## 2. Just sold / market proof

- **Engine:** stills · **Channels:** ig, fb, li · **Research:** light
- **Needs from drop:** property photo, sale outcome
- **Prompt:** Sold proof for {address}. Lead with the outcome that proves competence
  ({days-on-market}, {over-ask}, {multiple offers}) — the number is the hook.
- **Watch:** every number must trace to a dropped asset. Never estimate a sale figure. If the agent
  can't substantiate "12 offers," it doesn't ship.

## 3. Open house promo

- **Engine:** stills · **Channels:** ig, fb · **Research:** skip
- **Needs from drop:** property photos, date, time, address
- **Prompt:** Open house at {address}, {date}, {time-range}. Date and time are the most legible
  elements in the composition — thumbnail readability is the whole job.
- **Composite:** date/time block gets the highest contrast pairing available.
- **Watch:** wrong date is the single most costly failure here. Echo date and time back for
  confirmation before generating.

## 4. Market update

- **Engine:** stills (Phase 1) → Remotion data video (Phase 2) · **Channels:** li, ig, fb
- **Research:** **deep**
- **Prompt:** {month} market update for {market-area}. Median price, days on market, inventory,
  and the year-over-year direction. Lead with the one statistic that changes a decision.
- **Watch:** every statistic needs a cited source URL from Stage 3 and must survive the Stage 8
  truth check. Uncited numbers do not ship. Include the data period — a stale statistic presented
  as current is the failure mode that damages an agent's credibility most.

## 5. Agent intro / personal brand

- **Engine:** stills · **Channels:** ig, li · **Research:** skip
- **Needs from drop:** agent headshot
- **Prompt:** Introduce {agent} to someone who has never heard of them. Use `about-me.md`
  positioning and `brand-voice.md` register. One claim, one proof, one invitation.
- **Watch:** this is where generic slop is most likely. If the copy could describe any agent in the
  state, it fails the QC gate. Pull something specific from `about-me.md` or send it back.

## 6. Testimonial spotlight

- **Engine:** stills (quote card) · **Channels:** ig, fb, li · **Research:** skip
- **Needs from drop:** the testimonial text
- **Prompt:** Quote card from {client}'s testimonial. Pull the single strongest sentence — do not
  paraphrase, compress, or improve the client's words.
- **Watch:** `brand-context-compliance.md` governs whether testimonials are permitted and what
  attribution or disclaimer is required. Check before generating, not after.

## 7. Neighborhood guide

- **Engine:** stills carousel · **Channels:** ig, fb, li · **Research:** **deep**
- **Prompt:** Guide to {neighborhood}. What it's actually like to live there — amenities,
  character, what's walkable. Specifics over adjectives.
- **Watch:** the highest Fair Housing risk in the library. Describe *places and amenities*, never
  the people who live there. No demographic characterization, no "family-friendly," no school
  ratings as a selling point, no safety claims.

## 8. Educational carousel

- **Engine:** stills carousel (5–8 slides) · **Channels:** ig, li · **Research:** light
- **Prompt:** Explain {topic — escrow, earnest money, contingencies, closing costs} to a first-time
  buyer. One idea per slide. Plain language, no jargon without a definition.
- **Watch:** accuracy over polish. Process details vary by state — scope claims to the agent's
  state from `brand-context-compliance.md`, or keep them general.

---

## Video jobs (Phase 2 engines — route per SKILL.md)

- **Digital walkthrough** — narrated room-by-room video (`Walkthrough` comp). Needs: full room
  photo set + scenes.json + VO/music via the audio engine. The flagship listing deliverable.
- **Digital sales brief** — typography-led 20s brief (`SalesBrief` comp). Needs: 4 strongest
  photos + one claim per photo, each traceable to the drop.
- **Listing teaser** — 10s hook cut (`Teaser` comp) for Reels/Stories.
- **Interactive scroll tour** — scroll-driven listing microsite (`engine-scroll-tour.md`).
  Flights generated from the real photos; zero credits by default.

All video jobs: compliance endcard/footer is non-negotiable; every on-screen and narrated fact
traces to the drop; audio degrades music-only → silent with explicit warnings, never silently.

---

## Fair Housing — applies to every entry

Non-negotiable, and the reason a generic tool can't do this job:

- Describe the **property**, never the ideal **buyer**.
- No reference to race, color, religion, sex, disability, familial status, or national origin —
  including proxies ("great for young professionals," "quiet neighborhood," "walking distance to
  church," "perfect for a growing family").
- No school-quality claims as a selling point.
- No safety or crime characterization.
- Accessibility features are describable as *features* ("single-level, no-step entry"), never as
  suitability for a group of people.

`brand-context-compliance.md` supplies the required affirmative language and the brokerage's own
banned list. Content Foundry enforces that the language is present and legible; the brokerage owns
the wording. **This is assistive, not legal advice.**

---

## Adding a library entry

Each entry needs: default engine, default channels, research depth, required drop assets, the
fill-in-the-blank prompt, composite notes, and a `Watch` line naming the failure mode most likely
for that job. If you can't name the failure mode, the entry isn't ready.
