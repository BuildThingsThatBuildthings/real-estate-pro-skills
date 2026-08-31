#!/usr/bin/env bash
# Offline gate tests for content-foundry. The media pipeline needs a toolchain;
# these pin the text gates and the wiring that other skills depend on, and per
# the bundle's law, prove each gate CAN fail.
set -u
cd "$(dirname "$0")/.."
PASS=0; FAIL=0
ok()  { echo "  ok    $1"; PASS=$((PASS+1)); }
bad() { echo "  FAIL  $1"; FAIL=$((FAIL+1)); }

echo "== slop gate =="
python3 scripts/slop_check.py tests/fixtures/clean.md >/dev/null 2>&1 \
  && ok "clean copy passes" || bad "clean copy failed"
REPORT=$(python3 scripts/slop_check.py tests/fixtures/slop.md 2>&1)
[ $? -ne 0 ] && ok "slop fails" || bad "slop passed — the gate is not wired"
echo "$REPORT" | grep -q "delve into" && ok "catches 'delve into'" || bad "'delve into' slipped through"
echo "$REPORT" | grep -q "fast-paced" && ok "catches 'in today's fast-paced'" || bad "fast-paced slipped"
echo "$REPORT" | grep -qi "em.dash\|em-dash\|—" && ok "em-dash density flagged" || bad "em-dash pile not flagged"

echo "== the compliance shim still resolves to compliance-gate =="
python3 -c "
import sys, os
sys.path.insert(0, 'scripts'); import compliance
assert compliance.BANNED and compliance.check('a safe neighborhood')" 2>/dev/null \
  && ok "shim imports and checks" || bad "compliance shim broken"
python3 scripts/compliance.py check --text "guaranteed to sell fast" >/dev/null 2>&1
[ $? -eq 1 ] && ok "shim CLI still gates" || bad "shim CLI broken"

echo "== slop patterns file is valid and non-trivial =="
python3 -c "
import json
d = json.load(open('scripts/slop-patterns.json'))
assert len(d['banned_phrases']) > 20, 'suspiciously few patterns'
print('ok')" >/dev/null 2>&1 && ok "slop-patterns.json valid, >20 phrases" || bad "slop-patterns.json broken"

echo
echo "$PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
