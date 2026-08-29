# Engine — Remotion (built, Phase 2 live)

Programmatic video for data/text/motion-graphics — the listing-teaser and market-update
workhorse. The engine lives at `engines/remotion/` inside the skill and is driven entirely by
brand tokens from the agent folder. **The comp never hardcodes a brand fact.**

## Three products, one props file

| Comp | What it is | Audio |
|---|---|---|
| `Walkthrough` | Flagship digital walkthrough: room-by-room, narrated, aspect-aware layouts, kinetic room callouts | music bed + per-room VO |
| `SalesBrief` | Typography-led digital sales brief: hook → feature cards → community line → CTA | music bed |
| `Teaser` | 10s hook cut: three strongest rooms | music bed |

A fourth product, the Interactive Scroll Tour, lives in `engine-scroll-tour.md`.

## Pipeline

1. **Scenes** — author `{run}/scenes.json` from the brief: per-room `{photo, room, feature, vo}`
   plus `hook`, `community`, `brief_cards`. The video talks about the HOUSE — every scene names
   the room and states a feature that traces to the drop.
2. **Audio** — bring your own TTS + music. The engine consumes a plain `audio_meta.json` in
   the run dir; produce it with any tool (ElevenLabs, OpenAI TTS, local Kokoro, Azure — or
   record a human) plus any licensed music track:

   ```json
   {
     "voices": [{"id": "arrival", "path": "assets/voice/arrival.wav", "duration_s": 5.2}],
     "bgm": {"path": "assets/bgm/track.mp3"}
   }
   ```

   `id` matches the scene's `vo` field in scenes.json; `duration_s` drives scene timing
   (measure with `ffprobe -show_entries format=duration`). Paths are relative to the run dir.
   Missing narration degrades to music-only, missing music to silent — each with an explicit
   warning in the props, never silently.
3. **Props** — `python scripts/video_props.py --agent agents/{slug} --scenes {run}/scenes.json
   --audio-meta {run}/audio_meta.json --out {run}/video-props.json`
   - Brand truth via the same `brandkit.py` as stills; compliance gate identical.
   - Measures each photo's real aspect ratio and each VO clip's duration — **narration drives
     scene timing** (floor 3.5s/scene).
4. **Render** — `bash scripts/render_video.sh {props} {out}.mp4 {Comp} [extra remotion flags]`
   - Aspect-aware layout: landscape photos are FITTED full-width in an editorial band (never
     cropped beyond the ~5%/side traversal margin) with the brand field carrying room
     typography; portrait photos run full-bleed with a scrim callout. No blind cover-crops.
   - 1080×1920 @ 30fps; h264, yuv420p, CRF 18 (`remotion.config.ts`).
   - Low-disk machines: append `--concurrency=2 --jpeg-quality=70`.
5. **QC** — extract frames (`ffmpeg -ss {t} -frames:v 1`) at intro, one mid-scene (scene
   midpoint, not a fade boundary), and the endcard; actually look at them. Verify the compliance
   endcard, room callouts, and audio levels (`volumedetect`). Then a real watch-through.
6. **Export** — copy into `output/` with the standard naming convention
   (`[AGENT]_[TYPE]_[descriptor]-video_[YYYY-MM-DD]_[channel].mp4`). Hard guard: any variant
   over 300MB is rejected before Post Bridge upload.

## Pretext's role (this is where it lives)

Cheng Lou's Pretext (`@chenglou/pretext`, MIT) computes the intro headline's line breaks in
userland — canvas-measured, no DOM reflow. Each line renders as its own non-wrapping element, so
breaks are deterministic data instead of CSS side effects. See `useHeadlineLines` in
`src/ListingVideo.tsx`. If canvas/font measurement is unavailable it falls back to CSS wrapping
— a degradation, not a failure.

## Dependencies + degradation

- Node 18+, npm. First use: `cd engines/remotion && npm install` (~1 min).
- Detect at setup with `node --version` / `npx remotion versions`, never mid-run.
- Remotion pins zod at `4.4.3` — do not float it (`npx remotion add zod` if versions drift).
- Chrome Headless Shell downloads automatically on first render.
- **Missing dependency → ROUTE degrades to a still/carousel from the same brief and offers the
  install walkthrough.** Never fail the run because the video engine is absent.

## Adding compositions

New comps (market-update data video, carousel-to-video) register in `src/Root.tsx`. Rules:
brand values only via props from `video_props.py`; compliance endcard is non-negotiable; safe
zones from channel-specs (`SAFE` in the comp); one idea per video; hook in the first 2 seconds.
