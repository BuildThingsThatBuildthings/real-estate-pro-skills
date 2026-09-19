---
name: aia-neighborhood-story
description: Create a location-specific multimedia neighborhood story film anchored to a real listing, with verified local evidence, narrative treatment, script, storyboard, acquisition list, sound plan and finished vertical and horizontal films.
---

# Neighborhood story

Read the current listing campaign run contract and current source ledger. Resolve `../brand-voice/SKILL.md` from the same explicitly selected client context folder used by Content Foundry. Do not import another community's places, brand, rituals or narrative. Choose the narrative from the actual place; a home-to-outing-to-home day is one possible structure, not a mandatory template for every listing. In a fresh rebuild, repeat the source, rights and voice checks; previous AI research or generated footage cannot satisfy them.

Develop these inputs privately before rendering; they are production working material, not Drive deliverables:
1. `treatment.md`: audience question, opening moment, emotional progression, local discovery, visual payoff, ending and why this belongs to this location.
2. `script.json`: timed spoken lines and screen text with claim IDs, distinguishing imagined experience from facts.
3. `storyboard.json`: independent vertical and horizontal scenes with duration, source media IDs, framing, motion, transitions and map purpose.
4. `acquisition.csv`: exact assets needed, actual location, source URL, permissions, resolution, and approved substitute. Public web images with no rights basis remain excluded.
5. `sound-plan.md`: authorized voice, music provenance, speech pauses, levels, restrained SFX provenance, sound bridge and ending.
6. Prepare each requested orientation independently for the shared AIA listing campaign editor, with shot-level framing, licensed narration/music/SFX, embedded captions and the actual required duration. Use reviewed original or newly generated footage from this run. A still pan or repeated short move stretched to fill time cannot stand in for the film.

## Produce the films

Read `../aia-listing-campaign/references/source-camera-workflow.md` for original-photo camera generation and `../aia-listing-campaign/scripts/edit_camera_sequence.py` for its current composition contract. No outside `listing-worlds` installation is assumed. Use `scripts/validate_story.py` to check a private evidence plan before calling that shared editor:

```bash
python3 skills/aia-neighborhood-story/scripts/validate_story.py /absolute/private-working/story.json --render
```

The private plan contains `run_id`, `narrative` (opening, discovery, payoff, place_specificity, sound_direction), keyed `locations`, `claims`, `media`, and `films` mapping `vertical` and `horizontal` to separate editor configs. Claims need text, source, checked_at and location_id; development claims also need development_status, proximity_evidence and practical_relevance. Media need absolute path, SHA-256, source, rights_basis, location_id, origin, and current run_id for generated assets. Each editor shot adds media_id, location_id, claim_ids, framing_note and its narrative_beat (opening, development, discovery or payoff). Future projects require a claim screen_label actually present in the shot's screen text and an explicit spoken_status in its narration plan. Every factual spoken/on-screen statement must be mapped to its supporting claim during review.

The validator checks provenance, source identity, both compositions and evidence structure. The editor checks and renders actual media. Neither proves that the story is compelling or every sentence is true: inspect the complete films and original evidence afterward. A missing rights-cleared shot remains a production gap; never use unrelated location footage or a rendering of an existing park as documentary evidence.

## Deliver simply

Deliver finished `.mp4` films to Neighborhood Videos and finished cover images to Images/Covers. Captions are embedded in the video; `.srt` intermediates remain private. Keep JSON, acquisition CSV, render receipts, review logs, scripts used to operate tools and raw working files outside the entire Drive handoff. User-requested human-readable narration/recording scripts and useful PDFs are valid deliverables in the separate documents folder. Do not remove those requested documents under a media-only-folder rule.

Specificity must emerge from demonstrated details. Use a brief honest map to explain relationships; include attribution and distinguish diagrammatic positions from measured routes. Do not invent travel times. Separate subdivision amenities from public parks. A future project appears only with verified status, proximity and relevance; label it on screen and in narration. The story can use only existing places when future development evidence is weak.

QA adds three gates to the listing campaign checks: (a) coherent beginning, discovery and return/payoff, (b) every location and development claim supported, and (c) place-specific even without its title. A list of amenities over stock video fails. Do not mark this skill successful without the finished requested films; missing rights or footage is a named production gap.

## User-selected bundled basic editor

When the user selects the bundled basic editor, compose the complete neighborhood film with `mode: basic_photo_edit` in the shared AIA editor. Use separately authored source-pixel crop windows, varied shot lengths, real neighborhood photographs, honest maps, narration and licensed music; no paid provider or new sign-in is required. This permitted original-photo edit does not claim generated camera footage or a measured 3D tour. It must still deliver the full narrative, required duration and both orientations, with complete visual/audio review. A repeated tiny pan or static amenity slideshow does not satisfy that creative review.
