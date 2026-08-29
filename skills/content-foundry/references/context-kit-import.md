# Context Kit Import + Tier-2 Authoring

How Content Foundry gets an agent's brand truth. Read this during `setup` mode and whenever a run
reports a missing brand fact.

## The agent folder

```
agents/{agent-slug}/
├── _MANIFEST.md                    # Load order + tier rules — IMPORTED, do not rewrite
├── about-me.md                     # Tier 1 — IMPORTED
├── brand-voice.md                  # Tier 1 — IMPORTED
├── working-style.md                # Tier 1 — IMPORTED
├── brand-context-visual.md         # Tier 2 — AUTHORED BY CONTENT FOUNDRY
├── brand-context-compliance.md     # Tier 2 — AUTHORED BY CONTENT FOUNDRY
└── assets/
    ├── logo-light.png              # declared in brand-context-visual.md
    ├── logo-dark.png
    └── logo-mark.png
```

**Content Foundry does not define its own brand schema.** Tier 1 is a standard Context Kit
(a portable three-file persona format), imported verbatim. We add exactly two Tier-2 files, using the convention `_MANIFEST.md` already documents
(`brand-context-[name].md`, loaded when relevant, never overriding Tier 1).

### Rules inherited from `_MANIFEST.md`

- Read Tier 1 in the manifest's stated order: `about-me.md` → `brand-voice.md` → `working-style.md`.
- **Tier 1 overrides Tier 2 in all cases.** If `brand-voice.md` bans a word that a Tier-2 file uses,
  Tier 1 wins.
- If a verbal instruction contradicts these files, ask for confirmation.
- If unsure which agent applies, ask — never assume.

### The blank-template test

A freshly distributed Context Kit ships with HTML-comment placeholders (`<!-- One paragraph... -->`)
and bracket tokens (`[Business/Project Name]`, `[Priority 1]`). A file containing these is **blank**,
not filled. Detect and interview; never treat a placeholder as content, and never invent voice or
identity to fill a gap.

The manifest's own verification test is the bar. After loading, you must be able to answer:
1. Who is this person and what do they do?
2. How do they sound when they write?
3. What are the rules for how we work together?

If any answer is vague, say so and keep interviewing.

---

## Tier-2 template: `brand-context-visual.md`

```markdown
# Brand Context — Visual

## Colors
<!-- Exact hex codes. These are composited by script, not described to a model.
     If the agent only knows "navy and gold", get the actual hex from their logo file. -->
- primary:   #______    <!-- dominant brand color -->
- secondary: #______
- accent:    #______    <!-- used sparingly: CTAs, underlines, rules -->
- text-on-light: #______
- text-on-dark:  #______

## Logo files
<!-- Real paths, relative to the agent folder. Setup MUST verify these resolve. -->
- light background: assets/logo-light.png
- dark background:  assets/logo-dark.png
- mark only:        assets/logo-mark.png
- minimum width:    ___ px      <!-- below this the logo is illegible; composite refuses -->
- clear space:      ___ px      <!-- padding that must stay empty around the logo -->
- default placement: bottom-left | bottom-right | top-left | top-right

## Headshot
<!-- Optional but strongly recommended: the agent IS the brand. Used on video
     endcards and outreach pages when present. -->
- headshot: assets/headshot.jpg

## Typography
- headline font: ______        <!-- file path or system/Google font name -->
- body font:     ______
- headline case: title | sentence | upper
- max headline length: ___ characters   <!-- Pretext enforces the wrap; this caps the copy -->

## Photography style
<!-- Steers image-API prompts. Does NOT substitute for the composite. -->
- Preferred: <!-- e.g. warm natural light, wide interiors, lifestyle over empty rooms -->
- Avoid:     <!-- e.g. HDR halos, fisheye, empty twilight exteriors, stock-looking people -->

## Brokerage co-branding
- brokerage logo required on every asset? yes | no
- brokerage logo path: ______
- relative size vs agent logo: ______
```

## Tier-2 template: `brand-context-compliance.md`

```markdown
# Brand Context — Compliance

> Content Foundry enforces that this language is PRESENT and LEGIBLE.
> The brokerage supplies the WORDING. This is assistive, not legal advice.
> Never draft, paraphrase, shorten, or "improve" anything in this file.

## License
- agent license number: ______
- state: ______
- required placement: <!-- e.g. every public-facing asset, bottom edge, min 14px -->

## Brokerage disclosure
<!-- Paste the EXACT string the brokerage requires. Verbatim. -->
- disclosure text: "______"
- required on: all assets | listing assets only | ______

## Fair Housing
- required language: "______"     <!-- exact text, supplied by brokerage/state -->
- equal housing logo required? yes | no
- logo path: ______

## Banned claims and words
<!-- Beyond brand-voice.md's stylistic bans — these are compliance bans.
     Fair Housing steering language, unverifiable superlatives, guarantees. -->
- ______
- ______

## Testimonial rules
- testimonials permitted? yes | no
- required attribution / disclaimer: "______"

## Auto-publish
<!-- Kill switch. Leave false unless the brokerage has explicitly approved
     unattended publishing for this agent. -->
- auto_publish: false
```

---

## Interview guidance

Run the interview in the agent's own working style once `working-style.md` is loaded — if they've
asked for short outputs and no preamble, honor that here too.

**Order:** visual before compliance. Visual answers are fast and build momentum; compliance requires
the agent to go find exact strings from their brokerage, which is the step most likely to stall.

**Getting real hex codes.** Agents rarely know them. Ask for the logo file or brand guide PDF and
extract. If you only have a rasterized logo, sample the dominant colors and **confirm each one**
before writing it — a wrong hex silently poisons every future asset.

**Missing compliance wording.** Do not proceed with a guess and do not draft placeholder legal text.
Write the field as `[PENDING — request from brokerage]`, tell the agent exactly who to ask, and let
brand lint block production assets until it's filled. A blocked run is recoverable; a non-compliant
published post is not.

**Thin brands.** An agent with one color and a low-res logo is the common case, not the exception.
Build a working foundation from what exists, flag what's weak, and note that the composite will lean
on type and layout rather than color range. Don't invent a secondary palette without saying so.

## Adding an agent to a brokerage roster

1. Create `agents/{new-slug}/`, copy the blank Context Kit into it.
2. Run `setup --agent {new-slug}`.
3. Verify isolation: nothing in the new folder references another agent's paths, colors, or license.

Tenancy is enforced by the folder boundary, so the only real failure mode is a Tier-2 file pointing
at a shared asset path. Check that logo paths are inside the agent's own folder.
