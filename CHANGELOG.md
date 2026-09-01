# Changelog

Schema stability promise: artifact schemas carry a version field
(`chatgpt-said/claims/v1`, `sphere-signal/reasons/v1`, `listing-price-brief/adjusted/v1`).
A breaking change to any schema bumps its `/vN` and lands here with a migration note.
Rule additions to `compliance-gate` are NOT breaking changes — gates are allowed to get
stricter without notice, because that is their job.

## 1.3.0 — 2026-09-01

- **New desktop lane: `content-machine/`** — the seven-station weekly content loop
  (Intake → Log → Brand compare → Generate → Approve → Schedule → Learn) packaged for
  non-technical owners running the desktop app of Claude, ChatGPT, or Gemini. One pasted
  prompt (`content-machine/INSTALL-PROMPT.md`) fetches the skill and card templates from
  this repo, installs into the app's persistent layer (Project / Gem), connects Google
  Drive, builds the four-folder approval system, and interviews the owner to fill the four
  context cards. `POWER-UPS.md` documents the optional tiers (agent browser, video lane,
  generation accounts), all degrade-gracefully. The crosswalk in `content-machine/README.md`
  maps each station onto the advanced-lane skills; no skill was refactored.
- README and getting-started now lead with the desktop lane; the plugin/`install.sh` path
  is labeled the advanced Claude Code lane.

## 1.2.0 — 2026-08-31

- **Every skill now has a test suite and a demo** — 94 assertions across seven suites.
  - `brand-voice` gained `voice_lint.py`: the mechanical half of the voice audit is now
    enforced (banned words from the pack, hashtag piles, duplicated captions, links in an
    X body, hookless first lines, unsourced figures). Voice itself stays a human judgment.
  - `content-foundry` gained offline gate tests (slop gate + the compliance shim) and a demo.
  - `post-bridge-schedule` gained hermetic tests pinning its safety law: an explicit
    profile dir is authoritative and a missing file there refuses rather than falling back
    to the repo's accounts.
- CI runs all seven suites and all seven demos.
- Two fixtures were corrected by the gates themselves during authoring (hookless first
  lines; em-dash density) — recorded here because it is the design working as intended.

## 1.1.0 — 2026-08-30

- **New skill: `compliance-gate`** — the Fair Housing rules promoted to a standalone,
  invocable skill and the canonical module every other gate imports. Adds per-MLS
  profiles (`config/compliance/<board>.json`) that can add rules but never remove one.
  `content-foundry` keeps a working shim at its old path.
- **Claim ids are edit-stable** (`chatgpt-said`). Ids derive from the sentence text
  alone; inserting a sentence no longer detaches citations below it. Old-format ids
  (`C-01-d91b`) are gone; re-split any in-flight claims.json (classifications carry
  over by claim text).
- **Two Fair Housing evasions closed**: superlative safety claims ("safest
  neighborhoods") and phrases wrapped across line breaks now match. Both pinned as tests.
- **CI** — four suites, four doctors, four demos, compile and manifest checks on every
  push, Python 3.8 and 3.13.
- **Evals** — eight cases in the `claude plugin eval` layout (routing + behavior).
- **Demos** — `demo/demo.sh` in every gated skill: watch the gate refuse, then pass.
- `fair_housing` no longer requires any Post Bridge config to import.
- Shared doctor framework (`lib/skill_doctor.py`); per-skill doctors are declarations.
- `skills/*/runs/` is gitignored — run data holds client information and never commits.

## 1.0.0 — 2026-08-29

- Initial public bundle: `content-foundry`, `post-bridge-schedule`, `brand-voice`,
  `chatgpt-said`, `sphere-signal`, `listing-price-brief`.
- Two-line plugin install; Drive delivery doctrine (everything stops at `01 Waiting`).
