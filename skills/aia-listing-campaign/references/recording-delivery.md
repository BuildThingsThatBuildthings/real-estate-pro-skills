# Recording kit and delivery

For each 20–40-second agent reel deliver exact spoken copy, two alternative hooks, framing, movement, supporting shots, screen text, social caption and one natural next step. Group the shoot by physical room to minimize reset time. Include camera height, orientation, microphone/light guidance and a pick-up checklist. Never require unsafe movement while filming. The neighborhood introduction should naturally hand off to sourced local B-roll.

The useful handoff contains platform-specific captions, alt text, covers, posting notes and an ordered campaign calendar. Keep the technical deliverable manifest and SRT/VTT timing files private; burn readable captions into finished video exports. Dates may be relative Day 1–14 if launch date is unconfirmed. Mark platform music limitations and refresh-sensitive listing facts. Buyer emails and referral SMS are drafts, never sends. QR codes must resolve to the verified intended listing destination and be decoded from the finished flyer, not merely checked before placement.

Use subfolders for property videos, neighborhood media and graphics containing only finished MP4/PNG/JPG media. Put useful PDFs, the six recording scripts and copy/calendar documents in separate agent-recording-kit and copy/posting folders. Do not create a technical review folder in client Drive. Existing owner-supplied sources remain in Weekly Context; generated JSON, logs, SRT/VTT, research ledgers and editable projects stay in private working storage and never upload anywhere to client Drive. Record uploaded IDs, bytes and playback results privately. Delivery completion requires verified upload; upload completion is not playback proof. Record pending broker/client review without calling it published.

## Export details

Use `context/documents.json` for the Markdown paths to render, and `context/flyer.json` for the flyer ID and output folder. Client logo and font sources come from `context/brand.json`. Cover images must omit timed captions; a partial spoken sentence is not a useful thumbnail. Verify special numeric glyphs visually; use 2.5 when a font subset cannot display the half symbol. Never silently omit a fraction. Video files are rendered status until complete playback is recorded. If this environment cannot hear audio, record that limit and leave the sound gate pending.

The Content Foundry delivery gate validates every file before upload. Useful `.pdf`, `.md` and `.txt` documents must be both inside an explicit `--document-folder` and individually identified by `--document` relative path. Unknown files, technical sidecars, hidden files, unfinished renders and misleading extensions refuse the whole batch. Do not silently omit useful requested documents or convert them to screenshots. The document renderer remains available for the recording kit, copy/calendar and flyer PDFs; place every PDF in the declared document folders. Place the digital flyer image and QR image in graphics. Private document-rendering inputs and receipts are not deliverables.

## Exact handoff selection

Use `scripts/select_handoff.py` through the AIA workflow runner to build a fresh
handoff directory from the full canonical 60-item inventory. The private selection
manifest contains `root`, `run_id`, `destination_root`, and `items`; each item has
its canonical `id`, relative `source`, clean client `destination`, exact `sha256`,
and verified same-run `producer_task`. Declare the manifest and every source as
workflow inputs, with all producer dependencies. The helper refuses an incomplete
inventory, technical file types, path escapes, duplicate destinations, stale hashes
or sources without their actual producer. It validates the resulting media/PDFs
with Content Foundry's delivery gate. Only this selected folder is eligible for
Drive delivery; its manifests and receipts stay private.

PDF rendering accepts `--context-dir` and `--output-prefix` to produce corrected
client documents without overwriting or deleting an existing useful PDF. A supplied
contact block belongs in every document and, when `contact_instruction` is set on
the platform-caption target, it explicitly instructs inclusion on every public post.
Use only verified supplied contact details. Inspect punctuation in the actual client
font; a readable text extraction alone does not prove all glyphs rendered.

## Glyph coverage is a pixel check, never a string check

A missing glyph fails SILENTLY: Pillow reserves the character's advance and paints nothing, so
the compliance line ships with blank gaps where separators belong and every string-based gate
still passes. This is not hypothetical — it shipped on the 164 Southwind kiosk loops in 2026-09.

Before rendering anything that composites the compliance line, assert coverage over the whole
corpus: collect every unique character across all on-screen strings and end-card lines, and for
EACH one, at BOTH weights, require (a) presence in the font's cmap and (b) a rasterized glyph
mask with non-zero height. Presence in the cmap alone is not proof of ink — a codepoint can map
to an empty outline, which reserves advance and paints nothing. Hard-exit before rendering if any
character fails. Then raster at least one finished end card per film and LOOK at it.

Known-bad, and still the path most `context/brand.json` files point at: the Inter pair under
`ops/video/private-runs/chelsea-rebuild-20260907-recovery/dependencies/fonts`. They are subsets
with **no U+007C**, and no straight apostrophe, quote, bracket or bullet. Build a run-local full
Inter into `assets/fonts/` instead and point `brand.json` there.

Their name tables also lie — both report nameID4 "Inter Regular" — but do not infer from that that
the bold file is not bold. Measured, `inter-700.ttf` renders 52% more ink than `inter-400.ttf` and
its `usWeightClass` is correctly 700, so the weight is real and only the metadata is wrong. Judge a
font by rasterized ink, never by its name table, in both directions.

Note also that `validate_campaign.py` and `delivery_gate.py` do not import the compliance module,
so on-screen video type has no automated compliance check at all. Treat the raster review as the
only gate that exists for type burned into a frame.


Use `scripts/qa_documents.py MANIFEST PRIVATE_WORKING_DIR` to render every useful PDF page for visual inspection, extract its text, make uncropped image-review sheets and decode the exact listing QR destination. Review the resulting pages and images; the helper never certifies perceptual or broker approval. Keep all previews and records private.

For multi-caption PDFs, give each platform caption its own heading and a short standalone first line before the body. Preserve those breaks in the rendered PDF. Audit each actual caption separately with brand-voice; document labels, music attributions, source notes, and six separate Story captions must not be concatenated into a single supposed social caption. Check the final authored copy, not a reformatted lint-only surrogate. Keep source annotations private and bind them to the actual claim evidence.

Verify QR codes from the finished PDF at print resolution (300 dpi), not only from the standalone PNG or a 72 dpi contact sheet. An undecodable preview is not evidence of a wrong destination. Drive byte checks compare both directions so unexpected remote files fail alongside missing or altered files.
