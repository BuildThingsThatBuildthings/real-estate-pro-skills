---
name: aia-listing-campaign
description: Produce a researched, brand-specific multi-format real estate listing campaign, including cinematic source-photo films, neighborhood storytelling, graphics, agent recording scripts, and a verified Drive handoff. Use for complete listing media suites and reusable campaign production.
---

# Listing campaign

Use this extension with `content-foundry`, `brand-voice`, `aia-listing-photos`, and `aia-neighborhood-story`. Private client facts and media belong in the run folder, never this skill. An approved user campaign plan authorizes its production; record that approval in BRIEF.md without repeating the approval request. New purchases or materially expanded scope require a concrete estimate.

For rejected creative, cinematic walkthroughs, or feedback that video feels like slides, first apply [creative recovery](references/creative-recovery.md). Prove the motion and voice direction before multiplying deliverables. Source-led supporting dollhouses follow [spatial diagrams](references/spatial-diagrams.md); they never count as measured scans or finished photographic walkthroughs.

## Run contract

Create `run.json` with client_slug, brand, approval, sources, claims, media, deliverables, and stages. Each claim has id, text, source_ids, verified_at, status (verified, conflicting, historical, unresolved). Each source has id, url, retrieved_at, and supporting excerpt or artifact. Each medium has id, path/url, source_id, rights (authorized, licensed, original, unresolved), rights_basis, commercial_use, license_evidence, location, and fidelity_review. Each deliverable has id, kind, required, status (planned, rendering, awaiting_footage, failed, review, complete), path, claim_ids, media_ids, and review evidence. Never substitute a storyboard or preview for a required finished film.

1. **Context and identity.** Sync the current client context. Read the agent's own professional writing before agency-written website copy. Verify name, brokerage, contact, logo, color and font against the current client sources. Run Content Foundry dependency checks. Do not import the operator's branding.
2. **Research.** Follow [research and voice](references/research-voice.md). Keep historical facts separate from current listing facts. Build claim and media ledgers before writing copy.
3. **Creative direction.** Write BRIEF.md: central premise, distinct angles, emotional progression, coordinated visual/spoken/written hooks, precise output list, palette, typography, music direction, costs, evidence boundaries. Lock before generation. Use the existing user approval when it covers this brief.
4. **Production.** Follow [motion and edit](references/motion-edit.md). Delegate the neighborhood narrative to `aia-neighborhood-story`. Compose horizontal and vertical separately. Use real source photos and verified local imagery; maps may be original diagrams clearly labeled with their limitations.
   For photograph-led static designs, `scripts/render_photo_designs.py` consumes explicit private layer/crop/type decisions and records source hashes, rights and actual text boxes. Inspect a representative design before rendering its siblings. Its receipt proves rendering, not brand or creative approval.
5. **Agent kit.** Follow [recording and delivery](references/recording-delivery.md). Future recordings are awaiting_footage. Scripts do not count toward finished video totals.
6. **QA.** Run `python scripts/validate_campaign.py run.json`. Run Content Foundry compliance, brand and slop gates. Fully review every export with audio, then muted; document reviewer, time, issues and fixes. Technical probes and frame samples support but never replace full viewing. Verify actual footage against originals. No assumed or self-certified full-playback pass.
7. **Delivery.** Use copy/upload, never destructive sync, into the authorized client's listing subfolder under Weekly Context and Waiting. Read back filenames, sizes, hashes where available, downloadable bytes, subtitle pairing, video playback and QR target. Store delivery evidence. Never publish or schedule from this skill.
   After upload, run `scripts/verify_drive_delivery.py` with the local folder, remote, parent folder ID, destination and a receipt outside the checked folder. It downloads and compares every delivered file; a mismatch or missing file fails. This checks transfer integrity only. Playback, captions, QR destination and creative acceptance remain separate checks.

## Continue independent production

Track dependencies per required deliverable. A provider login, generation quota or destination-media license blocks only assets that depend on it. Continue all ready graphics, copy, agent scripts, editing and evidence work. Keep the entire requested output inventory in `run.json`; do not reduce scope to a proof clip, count tests as finished films, or end the run merely because one provider failed. Resume at the first unfinished dependency-ready item. The campaign is incomplete while any required asset is unfinished, even if all currently executable work is done.

Use `scripts/run_workflow.py workflow.json` for local production tasks. Each task names its governing AIA skill, explicit dependencies, argv command, expected files and status. The runner logs actual execution and hashes outputs, continues independent branches after failures, and leaves manual review/access tasks open. Only tasks in `executed` satisfy dependencies; this state does not mean the deliverable passed creative QA. Keep provider submissions and account approvals out of automatic retry loops.

## Portability evidence

Run validator tests and a second clearly fictional fixture with different brand, geography, home type and narrative. It must refuse unresolved sources/rights and an incomplete required film. Never place fixture facts in client media. Report behavioral evidence and remaining limits; a schema-only test is not full creative portability proof.

## Available local narration

`local_narration.py` supports an Apache-licensed Kokoro ONNX model with a built-in synthetic voice. Record model/voice source, license, runtime version and file hashes in the private run. Install its runtime in an isolated environment and keep weights outside git. A short successful audition precedes a batch. Scene-level time fitting must stay within the specified speed ceiling; caption timing and pronunciation still need full playback review. Use `final_mix.py` to map only source video and approved sound, excluding all rejected evaluation audio.

## Runtime dependencies

Production is optional and isolated from the lightweight evidence gate. Use Python 3.11 or newer for production scripts, FFmpeg/FFprobe, the existing Remotion engine Node dependencies, Pillow, fonttools with Brotli, qrcode, and ReportLab. Local narration additionally needs kokoro-onnx and its supported ONNX runtime. Record the tested versions in each run; do not install model weights or client media in the skill repository. The evidence validator and its test suite remain dependency-light and run in CI.
