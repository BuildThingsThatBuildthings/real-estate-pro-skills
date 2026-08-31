#!/usr/bin/env bash
# Gate tests for compliance-gate — the ONE copy of the Fair Housing rules.
# Four skills import this module, so a regression here silently breaks all of
# their COMPLIANCE gates at once. This suite is the tripwire.
set -u
cd "$(dirname "$0")/.."
PASS=0; FAIL=0
ok()  { echo "  ok    $1"; PASS=$((PASS+1)); }
bad() { echo "  FAIL  $1"; FAIL=$((FAIL+1)); }
FH="python3 scripts/fair_housing.py"

echo "== the gate can pass and can fail =="
$FH check --file tests/fixtures/pass/copy.txt >/dev/null 2>&1 && ok "clean copy passes" || bad "clean copy failed"
REPORT=$($FH check --file tests/fixtures/fail/copy.txt 2>&1)
[ $? -ne 0 ] && ok "violating copy fails" || bad "violating copy passed — the gate is not wired"
for cat in BANNED PROMISE NEEDS_SOURCE; do
  echo "$REPORT" | grep -q "\[$cat\]" && ok "$cat fires" || bad "$cat never fired"
done
# spot-check the rules that exist because of specific failure modes
for phrase in "safe neighborhood" "perfect for" "top-rated schools" "guarantee"; do
  echo "$REPORT" | grep -qi "$phrase" && ok "catches '$phrase'" || bad "'$phrase' slipped through"
done

# Two evasions found by a real run, pinned forever:
$FH check --text "one of the safest neighborhoods around" >/dev/null 2>&1 \
  && bad "'safest neighborhoods' evades the safety rule" || ok "superlative safety claims caught"
printf 'walking\ndistance to everything' > /tmp/cg-wrap.txt
$FH check --file /tmp/cg-wrap.txt >/dev/null 2>&1 \
  && bad "line-wrapped phrase evades matching" || ok "line-wrapped phrases caught"

echo "== MLS profiles add, never remove =="
P=$($FH check --text "Coming soon to market!" --profile example-mls 2>&1)
[ $? -ne 0 ] && ok "profile phrase fires with --profile" || bad "profile phrase did not fire"
$FH check --text "Coming soon to market!" >/dev/null 2>&1 && ok "profile phrase is NOT baseline" || bad "profile leaked into baseline"
PB=$($FH check --text "a safe neighborhood, coming soon" --profile example-mls 2>&1)
echo "$PB" | grep -q "safe neighborhood" && ok "baseline still fires under a profile" || bad "profile removed a baseline rule"
$FH check --text "x" --profile no-such-profile >/dev/null 2>&1 && bad "unknown profile accepted" || ok "unknown profile aborts"

echo "== the importers actually reach this copy =="
for caller in ../chatgpt-said/scripts/reconcile_gate.py ../sphere-signal/scripts/touch_gate.py ../listing-price-brief/scripts/brief_gate.py; do
  grep -q "compliance-gate" "$caller" && ok "$(basename $(dirname $(dirname $caller))) imports from here" \
    || bad "$(basename $(dirname $(dirname $caller))) does not import from compliance-gate"
done
python3 -c "
import sys; sys.path.insert(0, '../content-foundry/scripts'); import compliance
assert compliance.BANNED" 2>/dev/null && ok "content-foundry shim resolves" || bad "content-foundry shim broken"

echo
echo "$PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
