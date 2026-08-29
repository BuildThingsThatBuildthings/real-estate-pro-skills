# Engine — Interactive Scroll Tour (scroll-world)

A listing **microsite** where scrolling flies room-to-room through the home. Built on the
scroll-world scrub engine (`oso95/scroll-world`, MIT — vendored with license at
`engines/scroll-tour/vendor/`): scroll position drives playback through pre-rendered
camera-flight clips, with connector clips crossfading between rooms on frame-identical seams.

## Build

```
python engines/scroll-tour/build_tour.py --agent agents/{slug} \
    --scenes runs/{run}/scenes.json --out output/{name}/
```

Produces `index.html + scrub-engine.js + assets/` (~6MB for 7 rooms). Serve any way
(`python3 -m http.server`), or hand the folder to the brokerage's web person — it is
framework-free vanilla JS.

## Doorway-portal transitions

Room-to-room connectors are **portals through the actual doorway**: each scene declares a
`focal` point in `scenes.json` (fraction x,y of where the door/opening sits in that photo).
The connector accelerates a dive into that focal with a subtle spiral, blooms through white,
then emerges deep inside the next room and settles onto the exact frame its flight starts on
— seam-frame-identical on both ends. The camera never cuts; it walks through the door.
Pick focals by looking at the photos during UNIFY (the front door, the slider, the pantry
door); default is center when a scene has no obvious opening.

## How flights are made — and the rule that governs them

Per-room camera flights are generated **from the listing's real photos** with ffmpeg
`zoompan` (slow dolly-in + lateral traverse inside each photograph, 4s @30fps, 1280×720).
Zero AI generation, zero credits, and it honors the pipeline's hard rule: **never fabricate
imagery of a real property.** Connectors dip through the brand primary, built from the actual
first/last frames of adjacent flights per the engine's seam rule.

**Optional upgrade path:** Higgsfield/Kling image-to-video flights from the same real photos
give true parallax. That path costs credits — check balance first, present the cost, and get
approval before generating (same credit-ceiling discipline as `engine-stills.md`). Motion is
AI-enhanced from real photography; disclose accordingly.

## Branding + compliance

`build_tour.py` reads the agent folder via `brandkit.py` (same source as every other engine):
brand colors land as `--sw-*` CSS variables, room callouts come from `scenes.json` (eyebrow =
room index + community line, title = room, body/tags = feature line), and the license /
disclosure / Fair-Housing strings render in a fixed footer. **Unfilled compliance strings
block the build**, same as stills and video.

## QC

Serve locally, open in a real browser, scroll end-to-end: every room reachable, scrub smooth,
callouts synced, footer legible. Screenshot the hero and one mid-flight state. A tour shipped
without a scroll-through is a defective run.
