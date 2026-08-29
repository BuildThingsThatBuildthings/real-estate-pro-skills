# Engine — Still Images

The Phase 1 workhorse. Three steps: **generate base imagery → composite brand elements → lint.**

The split is the whole design. A generative model cannot reliably reproduce a hex code, a logo, or a
license number, so it is never asked to. It produces imagery; scripts place brand truth.

---

## Step 1 — Choose the base

Not every asset needs generated imagery. Check the drop first.

| Situation | Base |
|---|---|
| Drop has usable listing photos | **Use the real photo.** Never generate a fake interior for a real listing |
| Quote card, stat card, educational slide | Solid brand color or subtle generated texture |
| Lifestyle / conceptual (market update, neighborhood mood) | Generated imagery |
| Drop photo is close but wrong aspect | Real photo, reframed — not regenerated |

**Hard rule:** never generate imagery that depicts a specific real property. A generated "living
room" presented as the listing is a misrepresentation. Generated imagery is for conceptual and
lifestyle contexts only, and the brief must say which it is.

## Step 2 — Generate (base imagery only)

Bring your own image provider — the pipeline only needs a base image file on disk.

| Provider (examples) | Strength |
|---|---|
| GPT Image 2 | Typographic/graphic compositions, cleanest control |
| Higgsfield / Nano Banana | Photographic and lifestyle realism |
| Gemini | Fast iteration, good at scene variety |

Whatever generates the file, the contract is identical: base imagery only, saved into the
run's working dir, then composite → lint. The demo drop in this repo was generated this way
and is labeled fictional.

**Prompt construction:**
- Describe the scene, lighting, and composition. Pull style from `brand-context-visual.md`
  → Photography style (preferred / avoid).
- **Steer toward the brand palette** so the composite doesn't fight the base. Steering is an
  optimization, never a correctness mechanism — `brand_lint.py` still samples ΔE.
- **Leave compositional room** for the composite: request negative space where the logo, headline,
  and disclosure will land, per the channel's safe zones.
- **Never request:** logos, brand marks, text of any kind, license numbers, disclosures, watermarks,
  or real people's likenesses. Generated text is the most common source of a broken asset.

Generate at or above the target export dimensions — upscaling a composite degrades the type.

**Cost:** log tokens/credits per generation into `run.json`. Cost-per-exported-asset is a tracked
product metric, not an afterthought. Respect any per-run credit ceiling; abort and ask rather than
silently overspending.

## Step 3 — Composite (deterministic)

`python scripts/composite.py runs/{run} --agent {slug} --channel {ch}`

Layer order, bottom to top:

1. **Base image** — generated or real photo, cropped to channel dimensions.
2. **Scrim** (conditional) — brand-colored gradient or solid block where text will sit. Applied when
   the underlying region's contrast against the text color falls below WCAG AA (4.5:1). This is what
   makes headline type survive a busy photo.
3. **Headline / body type** — laid out by **Pretext**, positioned inside the channel safe zone.
4. **Logo** — the actual file bytes from `brand-context-visual.md`. Light or dark variant chosen by
   sampling background luminance. Respects declared minimum width and clear space; if the safe zone
   can't accommodate the minimum, `composite.py` fails rather than shrinking the logo below
   legibility.
5. **Compliance block** — license number, brokerage disclosure, Fair Housing language, equal-housing
   logo if required. Verbatim from `brand-context-compliance.md`. Minimum 14px effective, contrast
   ≥ 4.5:1, always inside the safe zone.

### Pretext

Cheng Lou's Pretext (npm, MIT, 15KB, zero-dependency) measures and lays out multiline text in
userland without DOM reflow. Its job here: given a string, a font, a max width, and a max line
count, return exact line breaks and metrics — so `composite.py` can place type into a safe zone
deterministically, without a browser and without guessing at wrap.

Use it for: headline wrapping into the safe zone, auto-fitting a variable-length address or price,
and caption layout. Where a headline can't fit within `max headline length`, fail back to the brief
for shorter copy rather than shrinking below legibility.

## Step 4 — Lint

`python scripts/brand_lint.py runs/{run} --agent {slug}`

| Check | Method | Severity |
|---|---|---|
| Logo present at declared position | Composite manifest + pixel diff vs source | **fail** |
| Logo ≥ minimum width | Manifest | **fail** |
| Exact brand hexes drawn | Sample known composite coordinates | **fail** |
| Compliance strings present verbatim | Composite manifest | **fail** |
| Compliance text contrast ≥ 4.5:1 | Sample text vs background | **fail** |
| All elements inside safe zone | Manifest vs channel-specs | **fail** |
| Generated region palette ΔE vs brand | Dominant color sample, ΔE2000 | **warn** |
| Thumbnail legibility | Downscale to 168px, headline contrast | **warn** |

Fails route back to Stage 6 with a root-cause note. Max 2 retries, then surface plainly.

## Carousels

Same pipeline per slide, one shared brief. Slide 1 carries the hook and must stand alone in feed.
Compliance block goes on **slide 1 and the final slide** — a viewer who never swipes still needs to
see it. Vary layout between slides; identical slides read as templated and get penalized.

## Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| Text baked into generated image | Prompt requested text | Regenerate; text belongs in composite only |
| Headline unreadable on busy photo | Scrim not applied | Lower the contrast threshold, or pick a calmer base |
| Logo lost against background | Wrong light/dark variant | Luminance sampling picks the variant — check it ran |
| Compliance text clipped by platform UI | Placed outside safe zone | Safe zones are hard constraints; re-composite |
| Colors drift from brand | Relied on prompt steering | Expected — that's what the composite and ΔE warn are for |
