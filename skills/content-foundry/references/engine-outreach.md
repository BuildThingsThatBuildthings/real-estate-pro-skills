# The Outreach Sample — canonical workflow + quality bar

This is the definitive recipe for a listing spec sample. Every run produces ALL of it; skipping
a step or gate is a defective run. (System pieces referenced here are the default behavior of
the engines — this doc is the checklist that proves they all fired.)

## The sequence

1. **Research the presenting agent** (`references/prospect-research.md`): identity, market,
   license, brokerage brand system from SERVED assets, voice evidence, **headshot**, design
   axes. Output: `agents/{slug}/` — research-drafted, provenance-cited, NOT a demo persona.
2. **Pull the listing**: facts + photos at the highest CDN resolution available. Facts on
   assets come from the listing only.
3. **scenes.json**: per-room `{photo, room, feature, vo, focal, pins}` + `address_chip`,
   hook, community line, brief_cards. `pins` are the key facts spoken in that room's narration
   — they will persist on screen.
4. **Narration + music**: agent-voiced lines (their register, their close: name + call to
   action), any TTS with WORD-LEVEL timestamps (`audio_meta.json` schema in
   `engine-remotion.md`). Word timings are not optional — they drive captions and pins.
5. **i2v parallax flights**: image-to-video on the real photos (balance check → cost → cap —
   abort-and-ask over budget). Fallback: upgraded ffmpeg flights. Never AI-fabricated rooms.
6. **Stills**: 4 channels, design-family layout, lint PASS each.
7. **Videos**: Walkthrough (flagship) + SalesBrief + Teaser.
8. **Interactive scroll tour** with the same flights.
9. **Outreach page** (`engines/outreach/build_page.py`): headshot header + closing scene,
   videos as the main event, stills, tour, real contact info, compliance footer, SAMPLE ribbon.
10. **Deploy** to an unlisted URL (Netlify/Vercel static) and send ONE link.

## The quality gates (all blocking)

- **Brand-first open**: the walkthrough's first 2.5s shows the agent's face + wordmark before
  the address. The agent IS the brand.
- **Kinetic captions at READING speed**: every narrated word appears on screen, popping on its
  spoken timestamp; groups hold up to ~10 words / 2 lines, break only on real pauses (>0.8s),
  linger until the next group speaks + 1.4s tail. Text never vanishes while readable.
- **Fact pins persist**: key facts (beds/baths/sqft, features) spring into the right rail when
  spoken and STAY for the scene. The address chip persists across all scenes.
- **Real parallax motion**: i2v flights inside the photo bands and the tour; doorway-portal
  connectors with frame-identical seams.
- **Design distinctness**: layout family, type system, motion energy, and accents from the
  agent's design tokens — a side-by-side against any other agent's sample must look
  structurally different. Palette matching a demo fixture FAILS lint.
- **Compliance everywhere**: license + disclosure + Fair Housing on every still, every video
  endcard, the tour footer, and the page footer. Verbatim, legible, worst-case contrast ≥ AA.
- **Watch-through + scroll-through** before delivery. Frames extracted at scene midpoints, not
  fade boundaries. A sample delivered unwatched is a defective run.
