#!/usr/bin/env bash
# Gate tests for chatgpt-said.
#
# content-foundry law 4: "The lint must be able to fail. If it has never failed
# on a run, it is not wired correctly." So this suite asserts both directions —
# a clean reconciliation passes, and a deliberately broken one trips every
# single gate by name. A gate that stops firing fails the build here.
set -u
cd "$(dirname "$0")/.."
PASS=0; FAIL=0
ok()   { echo "  ok    $1"; PASS=$((PASS+1)); }
bad()  { echo "  FAIL  $1"; FAIL=$((FAIL+1)); }

echo "== splitter =="
OUT=$(mktemp)
python3 scripts/claim_split.py split --in tests/fixtures/pass/chatbot.txt --out "$OUT" >/dev/null 2>&1 \
  && ok "splits without error" || bad "splitter errored"
# Determinism: the same paste must yield the same ids, or every citation an agent
# already wrote silently detaches on the next run.
OUT2=$(mktemp)
python3 scripts/claim_split.py split --in tests/fixtures/pass/chatbot.txt --out "$OUT2" >/dev/null 2>&1
if diff -q "$OUT" "$OUT2" >/dev/null; then ok "claim ids are stable across runs"; else bad "claim ids drifted"; fi
# No claim may begin mid-clause; that is the hard-wrap bug this splitter exists to avoid.
if python3 - "$OUT" <<'PY'
import json,sys,re
d=json.load(open(sys.argv[1]))
bad=[c["id"] for c in d["claims"] if re.match(r"^[a-z]", c["text"]) and not c["text"].startswith("lived")]
sys.exit(1 if bad else 0)
PY
then ok "no claim starts mid-clause"; else bad "a claim starts mid-clause (hard-wrap regression)"; fi
# The committed fixture must still describe what the splitter produces today.
# If the splitter changes shape, the fixture stops being a test and becomes a lie.
if LIVE="$OUT" python3 - <<'PY'
import json, os, sys
live = json.load(open(os.environ["LIVE"]))
fix = json.load(open("tests/fixtures/pass/claims.json"))
sys.exit(0 if {c["id"] for c in live["claims"]} == {c["id"] for c in fix["claims"]} else 1)
PY
then ok "fixture ids match live splitter output"; else bad "fixture is stale vs splitter"; fi

echo "== gate: a clean reconciliation passes =="
if python3 scripts/reconcile_gate.py check \
     --claims tests/fixtures/pass/claims.json \
     --reconciliation tests/fixtures/pass/reconciliation.md >/dev/null 2>&1
then ok "pass fixture exits 0"; else bad "pass fixture did not pass"; fi

echo "== gate: a broken reconciliation fails, gate by gate =="
REPORT=$(python3 scripts/reconcile_gate.py check \
           --claims tests/fixtures/fail/claims.json \
           --reconciliation tests/fixtures/fail/reconciliation.md 2>&1)
if [ $? -ne 0 ]; then ok "fail fixture exits non-zero"; else bad "fail fixture exited 0 — the gate is not wired"; fi
for g in CLASSIFIED SOURCED CITED GROUNDED NO_ARGUMENT REFERRALS COMPLIANCE; do
  echo "$REPORT" | grep -q "FAIL  $g" && ok "$g fires" || bad "$g never fired"
done
# The Fair Housing baseline is imported, not copied. If that import breaks, the
# gate must say so rather than quietly passing everything.
echo "$REPORT" | grep -q "could not be imported" && bad "compliance import is broken" || ok "compliance baseline imported"

echo
echo "$PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
