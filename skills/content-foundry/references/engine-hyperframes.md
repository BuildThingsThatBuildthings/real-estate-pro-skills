# Engine — HyperFrames (Phase 2 — not yet built)

**Status: stub.** Routed here before Phase 2 lands? Degrade gracefully: offer the Remotion route
if installed, else a still/carousel from the same brief. Never fail the run because this engine is
absent.

## What lands here in Phase 2

AI-generated video scenes — cinematic/lifestyle content that Remotion's programmatic style can't
produce:

- Scene generation via the HyperFrames toolchain; brand palette steering in every scene prompt
  (steering is an optimization — brand truth still enters via the composite/overlay pass, never
  via the generation prompt).
- The same hard rule as stills, applied to motion: **never generate footage depicting a specific
  real property.** Generated scenes are conceptual/lifestyle only, and the brief must label them
  as such.
- Compliance overlay: license + disclosure composited onto rendered video deterministically
  (same placement rules as `engine-stills.md`), then verified.
- Credit ceiling: check remaining balance before generating; abort-and-ask rather than silently
  overspending. Cost-per-asset is logged like every other engine.

## Available source-photo motion route

For a specific real listing, use the source-preserving Remotion composition documented in `../../aia-listing-campaign/references/motion-edit.md`. It animates original photos through bounded 2D transforms and clearly cut scene changes. This is an implemented photo-animation route, not completion of this future generative engine. If an external service rejects a job for unavailable credits, record the rejection and use an approved existing engine; never silently buy credits or substitute unrelated footage. Do not call a photo montage a generated walkthrough.
