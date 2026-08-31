#!/usr/bin/env bash
# Gate tests for brand-voice's deterministic linter.
# The voice judgment stays with a human/model reading the pack; these tests pin
# the mechanical half — and per the bundle's law, prove the gate CAN fail.
set -u
cd "$(dirname "$0")/.."
PASS=0; FAIL=0
ok()  { echo "  ok    $1"; PASS=$((PASS+1)); }
bad() { echo "  FAIL  $1"; FAIL=$((FAIL+1)); }
VL="python3 scripts/voice_lint.py"
PACK="tests/fixtures/riley-shore-pack.md"

echo "== the linter can pass and can fail =="
$VL check --pack "$PACK" --draft tests/fixtures/pass-draft.json >/dev/null 2>&1 \
  && ok "clean draft passes" || bad "clean draft failed"
REPORT=$($VL check --pack "$PACK" --draft tests/fixtures/fail-draft.json 2>&1)
[ $? -ne 0 ] && ok "bad draft fails" || bad "bad draft passed — linter is not wired"
for k in BANNED_WORD HASHTAG_PILE DUPLICATE_CAPTION LINK_IN_X_BODY UNSOURCED_CLAIM NO_HOOK; do
  echo "$REPORT" | grep -q "\[$k\]" && ok "$k fires" || bad "$k never fired"
done

echo "== the pack is the source of truth =="
echo "$REPORT" | grep -q "7 banned words" && ok "banned list parsed from the pack" || bad "pack parsing broke"
# a missing pack refuses rather than inventing a voice
$VL check --pack /nonexistent-pack.md --draft tests/fixtures/pass-draft.json >/dev/null 2>&1
[ $? -eq 2 ] && ok "missing pack refuses (never invent a voice)" || bad "missing pack did not refuse"

echo
echo "$PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
