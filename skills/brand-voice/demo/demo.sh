#!/usr/bin/env bash
# 90-second proof: the pack is the source of truth, and the mechanical half of
# the voice audit is enforced, not requested.  bash demo/demo.sh
set -u
cd "$(dirname "$0")/.."
P() { printf '\n\033[1m%s\033[0m\n' "$*"; }

P "A VOICE PACK IS A CONTRACT — here is the fixture pack's banned list:"
sed -n '/## Banned words/,/## Audience/p' tests/fixtures/riley-shore-pack.md | sed '1d;$d' | sed 's/^/    /'

P "FOUR CAPTIONS THAT VIOLATE IT — banned words, a hashtag pile, a copied caption, an unsourced figure:"
python3 scripts/voice_lint.py check --pack tests/fixtures/riley-shore-pack.md \
  --draft tests/fixtures/fail-draft.json 2>&1 | grep "FAIL" | head -10

P "THE SAME IDEAS, WRITTEN IN THE VOICE — one caption per channel, hooks front-loaded, figures sourced:"
python3 scripts/voice_lint.py check --pack tests/fixtures/riley-shore-pack.md \
  --draft tests/fixtures/pass-draft.json 2>&1 | tail -2

P "The linter settles the mechanical half. Whether it SOUNDS like the brand stays a human judgment,"
echo "made against the pack's on-brand and off-brand examples — which is why every pack must carry both."
