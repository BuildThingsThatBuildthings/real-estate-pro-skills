#!/usr/bin/env bash
# Gate tests for sphere-signal.
#
# content-foundry law 4: a lint that has never failed is not wired correctly.
# So this suite asserts both directions -- clean drafts pass, and a deliberately
# broken set trips every gate by name. A gate that stops firing fails here.
set -u
cd "$(dirname "$0")/.."
PASS=0; FAIL=0
ok()  { echo "  ok    $1"; PASS=$((PASS+1)); }
bad() { echo "  FAIL  $1"; FAIL=$((FAIL+1)); }

F_PASS=tests/fixtures/pass
F_FAIL=tests/fixtures/fail

echo "== notice.py =="
OUT=$(mktemp); OUT2=$(mktemp)
python3 scripts/notice.py scan --contacts $F_PASS/contacts.csv --touchpoints $F_PASS/touchpoints.csv \
  --today 2026-08-29 --out "$OUT" >/dev/null 2>&1 && ok "scan runs" || bad "scan errored"

# Reproducible: same inputs and same --today must give the same reason ids, or a
# draft written yesterday cites a reason that no longer exists today.
python3 scripts/notice.py scan --contacts $F_PASS/contacts.csv --touchpoints $F_PASS/touchpoints.csv \
  --today 2026-08-29 --out "$OUT2" >/dev/null 2>&1
diff -q "$OUT" "$OUT2" >/dev/null && ok "scan is reproducible for a fixed date" || bad "scan output drifted"

# The committed fixture must still match what the scanner produces today.
LIVE="$OUT" python3 - <<'PY' && ok "fixture reasons match live scanner" || bad "reasons fixture is stale"
import json, os, sys
live = json.load(open(os.environ["LIVE"])); fix = json.load(open("tests/fixtures/pass/reasons.json"))
sys.exit(0 if {r["id"] for r in live["reasons"]} == {r["id"] for r in fix["reasons"]} else 1)
PY

# An opted-out contact must never surface as a reason in the first place.
python3 - "$OUT" <<'PY' && ok "opted-out contact never surfaces" || bad "opted-out contact surfaced"
import json, sys
d = json.load(open(sys.argv[1]))
sys.exit(1 if any(r["contact_id"] == "c-005" for r in d["reasons"]) else 0)
PY

# Every reason must carry its arithmetic. A reason with no computed basis is a guess.
python3 - "$OUT" <<'PY' && ok "every reason carries a source" || bad "a reason has no source"
import json, sys
d = json.load(open(sys.argv[1]))
sys.exit(0 if all(r.get("source") and r.get("human") for r in d["reasons"]) else 1)
PY

# Reading a protected-class column must abort, not warn. Silently ignoring it
# leaves it one edit away from being used.
python3 scripts/notice.py scan --contacts $F_FAIL/contacts-protected-column.csv \
  --today 2026-08-29 --out /dev/null >/dev/null 2>&1 \
  && bad "protected-class columns were accepted" || ok "protected-class columns abort the scan"

echo "== gate: clean drafts pass =="
python3 scripts/touch_gate.py check --drafts $F_PASS/drafts.json --reasons $F_PASS/reasons.json \
  --contacts $F_PASS/contacts.csv >/dev/null 2>&1 && ok "pass fixture exits 0" || bad "pass fixture did not pass"

echo "== gate: broken drafts fail, gate by gate =="
REPORT=$(python3 scripts/touch_gate.py check --drafts $F_FAIL/drafts.json --reasons $F_FAIL/reasons.json \
           --contacts $F_FAIL/contacts.csv 2>&1)
[ $? -ne 0 ] && ok "fail fixture exits non-zero" || bad "fail fixture exited 0 — the gate is not wired"
for g in REASON CONSENT EARNED NO_INFERENCE FACTS NO_SEND COMPLIANCE; do
  echo "$REPORT" | grep -q "FAIL  $g" && ok "$g fires" || bad "$g never fired"
done
echo "$REPORT" | grep -q "could not be imported" && bad "compliance import is broken" || ok "compliance baseline imported"

echo
echo "$PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
