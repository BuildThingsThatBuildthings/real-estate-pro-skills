# QC Gate

Stage 8. Two checks, **both blocking**. Derived from RyVibes, simplified for this pipeline.

The gate exists because the alternative — an agent publishing an off-brand or non-compliant asset
under their license — is the failure this product is sold to prevent.

---

## Check 1 — `brand_lint.py` (deterministic)

Runs first; it's cheap and catches the objective failures. See `engine-stills.md` §Step 4 for the
full check table. Any **fail** severity stops the run. Warns are reported and carried into Check 2
as context.

## Check 2 — Model QC pass

Read the exported asset and the brief. Answer each of these honestly. Any "no" is a failure with a
named root cause.

### Truth
- [ ] Every on-screen number traces to a Stage 3 citation or a dropped asset. No estimated prices,
      invented statistics, or unsourced market claims.
- [ ] Every stated fact about the property appears in the drop (MLS sheet, photos, agent input).
- [ ] Data has a stated period where relevant. A stale statistic presented as current is a failure.

### Compliance
- [ ] License number and brokerage disclosure present, verbatim, legible.
- [ ] Fair Housing language present where required.
- [ ] Copy describes the **property**, not the ideal buyer. No demographic proxies, school-quality
      claims, or safety characterization. (Full rules: `prompt-library.md` §Fair Housing.)
- [ ] No claim the agent can't substantiate.

### Brand
- [ ] Voice matches `brand-voice.md` — check tone attributes and the on/off-brand examples.
- [ ] No word from the banned lists (`brand-voice.md` stylistic, `brand-context-compliance.md` legal).
- [ ] Remove the logo — is it still recognizably this agent? If any competitor could run this asset
      unchanged, it fails.

### Craft
- [ ] **One idea per asset.** Two competing messages means neither lands.
- [ ] Hook works in feed — the first thing read creates a reason to keep reading.
- [ ] Legible at thumbnail (168px wide). Downscale and actually look.
- [ ] Type hierarchy is a decision, not a default. The most important element is the most prominent.
- [ ] Composition doesn't fight the composite — headline isn't sitting on visual noise.

### Slop taxonomy

Mechanical signatures of average output. `scripts/slop_check.py` catches the textual ones; you catch
the visual ones.

- [ ] No generic stock-agent language: "your dream home awaits," "let me help you find," "nestled in
      the heart of," "don't miss this opportunity."
- [ ] No em-dash-heavy AI cadence or "it's not just X, it's Y" constructions.
- [ ] No hedge stacking ("truly," "really," "very," "incredibly").
- [ ] Copy is specific to *this* listing/market — not swappable to any other.
- [ ] Visual isn't a default template: centered-everything, unmotivated gradient, three equal boxes.
- [ ] Emoji use matches `brand-voice.md`, not habit.

---

## Retry protocol

On failure, write a **root-cause note** naming the stage that produced the defect, then route back
to Stage 6:

```
FAIL: compliance text contrast 3.1:1 (need 4.5:1)
ROOT CAUSE: Stage 6 generated a light base under the bottom-edge disclosure zone
FIX: regenerate with darker lower third, or enable scrim under compliance block
```

**Max 2 retries.** Then stop and surface to the user in plain language: what failed, why, and the
one or two things that would fix it. Offer to proceed with a documented exception only for `warn`
severity — never for a compliance or truth failure.

## Anti-patterns in the gate itself

- **A gate that never fails is not wired up.** Verify by running a deliberately wrong hex through it.
- **Don't let the model grade its own homework loosely.** Check against the brief and the agent
  folder, not against what the asset appears to be trying to do.
- **Don't auto-fix a compliance failure by rewording.** The wording is the brokerage's. Fix
  placement, contrast, or size — never the words.
- **Don't average away a warn.** Two warns that both point at palette drift are one real problem.
