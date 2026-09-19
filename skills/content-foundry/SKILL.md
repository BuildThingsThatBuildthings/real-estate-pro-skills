---
name: content-foundry
description: >
  Brand-locked social content engine for real estate agents and brokerages. Point it at one agent's
  context folder, drop mixed assets (listing photos, walkthrough video, MLS PDF, links) into a drop
  folder, then pick a prompt-library job or freehand prompt — it unifies the assets, researches the
  local market, writes a reviewable creative brief, generates imagery, composites the agent's real
  logo/colors/license/disclosure deterministically, gates the result against brand lint and a slop
  check, and exports channel-sized assets. Optional draft-first scheduling via Post Bridge.
  Triggers on "/content-foundry", "new listing post", "just sold post", "open house promo",
  "market update graphic", "make a post for {agent}", and drops into a drop folder.
---

# Content Foundry — brand-locked content production for real estate

Invocations:
- `/content-foundry --agent {slug} --drop {path} "{prompt or library job}"`
- `/content-foundry setup --agent {slug}` — build or complete an agent's foundation folder
- `/content-foundry setup --from-research {urls}` — research-drafted foundation for outreach (see `references/prospect-research.md`)
- `/content-foundry outreach --listing {url} --agent-profile {url}` — the full spec-sample suite, end to end (see `references/engine-outreach.md`)
- `/content-foundry resume {run-dir}` — resume at the first non-done stage
- `/content-foundry roster --agents a,b,c "{prompt}"` — same job across N agents (Phase 3)

## Complete listing campaigns

For a multi-format listing launch, use `../aia-listing-campaign/SKILL.md` after the context pull and route the location narrative through `../aia-neighborhood-story/SKILL.md`. These extend this pipeline with current/historical research, a claim and rights ledger, separately composed films, agent recording scripts, and a verified Drive handoff. An already-approved user plan can satisfy the brief review within its authorized scope; record it rather than asking again.

## Non-negotiable laws

1. **The folder is the tenancy boundary.** Everything brand-related comes from
   `agents/{slug}/`. Never read another agent's folder in a run. Never carry brand facts between
   runs from memory. If a needed brand fact is missing, ask — do not infer it from the photos, the
   listing, or a prior agent.
2. **Composite, don't request.** The generative model never produces the logo, the exact brand hex,
   the license number, or the disclosure line. Those are placed by `scripts/composite.py` from files
   on disk. Asking a model for them is the failure this product exists to prevent.
3. **Brief before spend.** Stage 4 writes `BRIEF.md` before generation. An explicitly approved
   campaign plan authorizes production within that scope; record the approval rather than
   asking again. New purchases or material scope changes still need their own authorization.
4. **The lint must be able to fail.** `brand_lint.py` is a gate, not a formality. If it has never
   failed on a run, it is not wired correctly.
5. **This system does not publish.** The client agreement says so in their own folder: "Nothing
   in this system posts anything, ever." Finished work is delivered to `01 – Waiting` and the
   client approves it. Publishing is a separate paid product. Only when a client has
   `posting_enabled: true` in `config/clients.json` does anything reach `post-bridge-schedule`,
   and only after explicit user posting authorization plus a verified client destination context.
   An upload or draft is also an external write. Never use Ryan's personal Post Bridge workspace
   for client output unless he explicitly requests that specific personal sample. Missing client
   credentials stop posting; they never trigger a fallback to global/personal credentials.
6. **A listing job runs under the listing's presenting agent's folder.** No folder → run
   `setup --from-research {urls}` (see `references/prospect-research.md`) or a live setup first.
   Never default to a demo persona or a previously-used agent; demo folders refuse listing
   content by design.
7. **Compliance is placement, not wording.** The skill enforces that required language is present
   and legible. The brokerage supplies the wording. Never invent or paraphrase a legal disclosure.
   This is assistive, not legal advice.

## Setup mode

Run before an agent's first production run.

1. Locate `agents/{slug}/`. If absent, create it from `references/context-kit-import.md`.
2. Read `_MANIFEST.md` and honor its stated load order and its Tier-1-overrides-Tier-2 rule.
3. Read Tier 1 (`about-me.md`, `brand-voice.md`, `working-style.md`). Any file still containing
   template placeholder comments is **blank** — interview the agent to fill it. Do not fabricate
   voice or identity.
4. Author the two Tier-2 files if missing (see `references/context-kit-import.md`):
   - `brand-context-visual.md` — hexes, logo paths, fonts, photography style
   - `brand-context-compliance.md` — brokerage disclosure, license number + placement, Fair
     Housing language, banned claims
   If the agent drops a brand guide PDF, extract and pre-fill, then confirm every extracted value.
5. **Dependency check at setup:** run `python scripts/doctor.py` — it verifies
   Python/Pillow (required), ffmpeg/node (video tier), and Post Bridge (optional) with per-OS
   install hints. Also confirm the logo files at the declared paths actually exist. Anything
   missing is reported now, in plain language; a dependency discovered missing at Stage 6 is a
   defect.
   For a full listing campaign use `doctor.py --campaign --skip-postbridge` in the exact Python
   runtime used by the workflow. This also checks the QR, PDF, font and skill-validation libraries.
   A changed runtime requires another preflight; packages installed in a different interpreter do
   not establish readiness. The skip flag avoids probing an unneeded publishing dependency.
6. Verify per `_MANIFEST.md`'s own test: can you state who this agent is, how they sound, and what
   the rules are? If any answer is vague, the files need more work — say so.

## The pipeline

Track state in `run.json.stages` (pending → in-progress → done). Update after each stage.
Run artifacts live in `runs/{YYYYMMDD-slug}/`.

### Stage 0 — CONTEXT PULL
`python scripts/drive_sync.py all --client {slug}`
`python scripts/drive_sync.py agent-folder --client {slug}`

**Brand context syncs on every run, not just weekly ones.** Guardrails, voice and client cards
change between weeks, and stale compliance rules are the expensive kind of stale.

Two folders per the client's own README:
- **`00 – Weekly Context`** — what they dropped this week. Never tidy it. A screenshot of a text
  message is a valid input. Client questions are the highest value item in there.
- **brand context** — `my business/` (about-me, brand-voice, working-style, GUARDRAILS),
  `my clients/`, `my deals/`.

`agent-folder` maps the Drive layout onto the Tier-1/Tier-2 names the rest of this pipeline
expects, by symlink, so the Drive sync stays the one source of truth. It reports anything missing.
`brand-context-visual.md` has no Drive equivalent yet — without it Stage 7 cannot place brand
colour or the logo.

Uses rclone, not the Drive MCP. The MCP returns file bytes as base64 into the model context, which
is wrong for a folder of photos and video.

**Note:** rclone's shared Google client_id is being retired during 2026. Each operator needs their
own OAuth client_id before then or every weekly run breaks at this stage.

### Stage 1 — INGEST
`python scripts/inventory.py {drop-path} --out runs/{run}/asset-manifest.json`

Deterministic walk: type, size, hash, dimensions, EXIF. Flags duplicates by hash, unsupported
types, and empty folders. **Unsupported files are reported, never fatal.** If the folder is empty or
every asset is unusable, stop here and say so — don't proceed to spend tokens.

### Stage 2 — UNIFY
`python scripts/unify.py runs/{run}/asset-manifest.json --out runs/{run}/unified-context.md`

Per-type handlers → text + structured metadata:
- audio / video → transcript (whisper or equivalent)
- PDF → extracted text (MLS sheets, brand guides)
- `.txt` / `.md` containing links → fetch and summarize
- images → model-generated description + EXIF

Output is one canonical document describing everything dropped. Describe images honestly: a
screenshot of a prior marketing graphic is a *reference*, not a listing photo, and the brief should
know the difference.

### Stage 3 — RESEARCH
Web search scoped by the prompt. Depth comes from the `prompt-library.md` entry
(`market update` = deep; `testimonial spotlight` = skip). Cite every statistic with a source URL —
uncited numbers cannot pass the truth check in Stage 8.

### Stage 4 — BRIEF ✋
Compose `runs/{run}/BRIEF.md`: objective, key message, target channels, brand constraints (from the
agent folder), channel constraints (from `channel-specs.md`), assets to feature (by filename),
research citations, and the composite plan (which hex where, logo placement, disclosure position).

Write it to disk. If the user has already approved the campaign plan or directed this rebuild,
record that authorization and continue. Otherwise present the concrete brief for review.

### Stage 5 — ROUTE

Route on what the dump actually contains, established in Stage 1:

| What came in | What it becomes |
|---|---|
| Property photos or walkthrough video, rights clear | For a requested full campaign, the mandatory Listing Campaign route below; otherwise the explicitly requested listing media |
| B-roll with no specific property | list posts, process explainers, misconception corrections, market notes |
| A client question in the notes | answer it precisely. The README calls this the most valuable input there is |
| MLS sheet or market report | sourced market post. Every number cites Stage 3 or the sheet itself |
| Rights unclear on any asset | it does not get made. Unclear rights are missing, not pending |

For routine weekly jobs, respect the configured floor and cap. An explicit full-campaign request
uses its complete required deliverable inventory instead; it cannot be reduced to a weekly quota.
Use authorized agent recordings when supplied and requested. Never invent the agent's appearance
or impersonate their voice. Future recording requirements remain clearly awaiting real footage.

| Output need | Engine | Reference |
|---|---|---|
| Static graphic, carousel, quote card | Still-image engine | `references/engine-stills.md` |
| Full listing campaign, flagship house tour, or cinematic listing teaser | Required AIA editor workflow: original-photo or original-footage compositions, narration and a complete story | `../aia-listing-campaign/references/source-camera-workflow.md` and `../aia-listing-campaign/references/motion-edit.md` |
| Text-led explainer or sales brief that does not promise a photographic property tour | Existing Remotion compositions | `references/engine-remotion.md` |
| Interactive scroll-tour listing microsite | scroll-world engine | `references/engine-scroll-tour.md` |
| Outreach spec sample — full suite + live page | canonical workflow | `references/engine-outreach.md` |
| Outreach landing page component | `engines/outreach/build_page.py` | `references/engine-outreach.md` |
| Photographic camera movement from listing stills | Bundled FFmpeg/Pillow editing with source-preserving framing; no invented 3D geometry | `../aia-listing-campaign/references/source-camera-workflow.md` |
| Supporting spatial diagram from verified source geometry | AIA spatial-diagram workflow; a diagram is never a finished photographic house tour | `../aia-listing-campaign/references/spatial-diagrams.md` |

For a full campaign, the first video route above overrides legacy slideshow/Remotion templates,
optional BYO-video guidance, and post-v1 3D labels in older references. Complete original-source coverage,
the full narrated flagship and all required independent edits are current mandatory outputs.
When the user chooses the basic-editor route, use original photographs with controlled motion,
varied shot timing, narration and a coherent full-home story. Do not describe these edits as a
measured 3D scan or generated camera footage. Reject repeated title cards and padded still holds.
Read the Listing Campaign skill and its referenced production instructions before execution.
Load only the routed engine's doc. If a requested engine is unavailable, continue independent
deliverables and keep the affected output explicitly unfinished. Do not replace a required film
with a still/carousel, count a camera test as a finished film, or stop the whole campaign at one
missing bundled capability. Do not impose new purchases, provider sign-ins, subscriptions or optional paid tools on the full campaign. Follow the listing campaign's per-deliverable workflow runner. Inspect the actual edit for engaging pacing, readable images and a coherent property story; software availability alone is not quality evidence.
An image API key is unnecessary when authorized source photographs already supply the base.

### Stage 6 — GENERATE
For full listing campaigns, execute the AIA campaign workflow: source preparation, verified camera
footage, narration, soundtrack, independent edits and graphics. Do not apply the still-image-only
instruction below to film production. Keep intermediate files private; only final client deliverables
reach the output handoff.

For static-image jobs, produce **base imagery only** into `runs/{run}/working/`. No logo, no headline type, no disclosure
in the generated pixels. Steer the prompt toward the brand palette so the composite doesn't fight
the base, but never rely on that steering for correctness.

### Stage 7 — COMPOSITE ⚙️
`python scripts/composite.py runs/{run} --agent {slug} --channel {ch}`

Deterministically layers, at `channel-specs.md` coordinates:
- brand color blocks / scrims from `brand-context-visual.md`
- the logo file's actual bytes
- headline and caption type, laid out by **Pretext** into the channel safe zone
- license number and disclosure line from `brand-context-compliance.md`

### Stage 8 — QC GATE (all three must pass)
0. `python scripts/compliance.py check --batch runs/{run}/captions.json --client {slug}`

   Fair Housing and claim gate, over every line of copy. Merges the client's own GUARDRAILS card
   over a 29 phrase baseline. Blocks demographic targeting, safety and school quality claims,
   "walking distance", promises of price, timeline, appreciation, rent or return, and unsourced
   square footage, room counts, percentages, HOA fees, tax figures or year built.

   This gate is about **wording**. Stage 7's compliance work is about **placement**. Both are
   required and neither substitutes for broker or legal review.

1. `python scripts/brand_lint.py runs/{run} --agent {slug}` — composite verification (logo present,
   exact hexes drawn, compliance string present and legible at thumbnail size) plus palette ΔE
   sampling of the generated region.
2. `python scripts/slop_check.py runs/{run}` plus a model QC pass against `references/qc-gate.md`:
   slop taxonomy, hook strength, one idea per asset, thumbnail readability. Verify every on-screen
   number against a Stage 3 citation or a dropped asset.

Failures route back to Stage 6 with a written root-cause note. **Max 2 retries**, then stop and
explain to the user in plain language what failed and what would fix it. Never quietly ship a
failing asset; never loop silently.

### Stage 9 — EXPORT
`python scripts/export.py runs/{run} --channels ig,fb,li`

Sizes/encodes per channel, applies `[AGENT]_[TYPE]_[descriptor]_[YYYY-MM-DD]`, writes to `output/`
containing only finished client files. Export receipts stay in the private `working/export-receipts/`
folder, never `output/` or Drive. Photo-design composite manifests live privately in
`working/design-receipts/`; pass their explicit path with `--manifest` to both `brand_lint.py`
and `export.py`. Report actual delivery links in the conversation.

### Stage 10 — DELIVER
`python scripts/drive_sync.py deliver --client {slug} --from output/ --yes`

Uploads the finished set to `01 – Waiting`. Media folders contain only playable `.mp4` and decoded
`.png`/`.jpg`/`.jpeg` images. Useful PDFs, the six recording scripts, captions/copy and the calendar
remain client deliverables, but only in a separate, explicitly named document folder. Pass both
`--document-folder "04 Chelsea Recording Kit"` and an exact `--document "04 Chelsea Recording Kit/Recording guide.pdf"`
for each useful document (repeat flags as needed). `.pdf`, `.md` and `.txt` documents are supported.
The preflight rejects the entire batch before upload if any technical JSON, logs, subtitle sidecars,
audio stems, project/source files, hidden files, unfinished renders or unknown files occur anywhere.
Misleading file extensions fail actual image/video/PDF validation. Never relabel a media folder as
a document folder or rename technical records as useful documents. Embed captions in finished videos;
keep timing files, claim/source ledgers and production metadata private. Do not upload a raw run,
context or project directory into Weekly Context or any other client Drive folder. The client
approves or requests revision. This stage writes only to the authorized client Drive folder.
It never uploads media to Post Bridge or creates a draft as a preview. Nothing publishes on its own.

Without `--yes` it prints what it would send and stops. The folder is client-visible.

### Stage 11 — SCHEDULE (only if posting was purchased)
Only when `posting_enabled: true`, the work sits in `02 – Approved`, **and the user explicitly
authorizes posting to that client's verified Post Bridge workspace**. Require the private posting
authority context and live roster verification described in that skill. Client media generation
is not authority for personal-workspace samples. A media-only campaign stops after Drive delivery. Hand
to the `post-bridge-schedule` skill, which owns per-channel captions, analytics-derived windows,
collision detection and verified writes. Approved is not published; scheduling is a separate,
explicit step.

## Failure surfaces — say these plainly

| Condition | Response |
|---|---|
| Drop folder empty or all-unusable | Stop at Stage 1, list what was found and what's needed |
| Tier-1 file still has template placeholders | Stop, run setup interview for that file |
| Logo path in Tier 2 doesn't resolve | Stop at setup/composite, name the missing path |
| Image API key absent | Stop at setup with the key-configuration steps |
| Brand lint fails twice | Surface root cause + the specific brand value that didn't land |
| Required disclosure missing from Tier 2 | Ask the brokerage for wording; never draft it |

## Scripts added for the Drive workflow
- `scripts/drive_sync.py` — pull brand and weekly context, build the agent folder, deliver a set
- `scripts/compliance.py` — Fair Housing and claim gate over copy

## References
- `references/context-kit-import.md` — agent folder import + Tier-2 authoring
- `references/channel-specs.md` — platform dimensions, safe zones, caption limits
- `references/prompt-library.md` — 8 realtor jobs-to-be-done
- `references/engine-stills.md` — image API + Pretext layout + composite recipe
- `references/qc-gate.md` — slop taxonomy + brand lint checklist
- `references/postbridge-automation.md` — draft-first scheduling
