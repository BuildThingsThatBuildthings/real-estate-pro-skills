#!/usr/bin/env bash
# 90-second proof: the slop gate reads copy the way a tired buyer does.
set -u
cd "$(dirname "$0")/.."
P() { printf '\n\033[1m%s\033[0m\n' "$*"; }

P "COPY THAT SOUNDS LIKE EVERY AI EVER:"
sed 's/^/    /' tests/fixtures/slop.md

P "THE SLOP GATE REFUSES IT, PATTERN BY PATTERN:"
python3 scripts/slop_check.py tests/fixtures/slop.md 2>&1 | sed -n '1,12p'

P "THE SAME MARKET NOTE WITH ACTUAL INFORMATION IN IT:"
sed 's/^/    /' tests/fixtures/clean.md
python3 scripts/slop_check.py tests/fixtures/clean.md >/dev/null 2>&1 && echo "
  PASS  clean"

P "And the Fair Housing gate rides along on everything this skill produces,"
echo "imported from compliance-gate: one copy of those rules in the whole bundle."
