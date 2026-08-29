#!/usr/bin/env bash
# Gate tests for listing-price-brief.
#
# content-foundry law 4: a lint that has never failed is not wired correctly.
set -u
cd "$(dirname "$0")/.."
PASS=0; FAIL=0
ok()  { echo "  ok    $1"; PASS=$((PASS+1)); }
bad() { echo "  FAIL  $1"; FAIL=$((FAIL+1)); }
P=tests/fixtures/pass
F=tests/fixtures/fail

echo "== comp_source =="
T=$(mktemp)
python3 scripts/comp_source.py load --tier export --in $P/comps-export.csv --out "$T" --as-of 2026-08-29 >/dev/null 2>&1 \
  && ok "normalizes an MLS-style export" || bad "export load failed"
# Unwired tiers must refuse loudly, not silently fall back to export.
python3 scripts/comp_source.py load --tier reso --in $P/comps-export.csv --out /dev/null >/dev/null 2>&1 \
  && bad "reso tier silently accepted" || ok "unconfigured tier refuses rather than falling back"
# A missing required field must name itself, not produce a half-empty comp set.
BADCSV=$(mktemp).csv; printf 'Address,Beds\n1 Main St,3\n' > "$BADCSV"
python3 scripts/comp_source.py load --tier export --in "$BADCSV" --out /dev/null >/dev/null 2>&1 \
  && bad "accepted a file missing close_price" || ok "missing required fields abort the load"

echo "== arithmetic =="
A=$(mktemp); N=$(mktemp)
python3 scripts/comps.py adjust --comps $P/comps.json --subject $P/subject.json --rates $P/rates.json \
  --as-of 2026-08-29 --out "$A" >/dev/null 2>&1 && ok "adjusts without error" || bad "adjust errored"
# Every ledger must re-derive. This is the defect a reader never catches.
python3 - "$A" <<'PY' && ok "every ledger sums to its own net" || bad "a ledger does not re-derive"
import json,sys
d=json.load(open(sys.argv[1]))
for r in d["included"]:
    s=round(sum(l["dollars"] for l in r["ledger"]),2)
    if abs(s-r["net_adjustment"])>0.01: sys.exit(1)
    if abs(round(r["close_price"]+s,2)-r["adjusted_value"])>0.01: sys.exit(1)
PY
python3 - "$A" <<'PY' && ok "every ledger line shows its formula" || bad "a ledger line has no arithmetic"
import json,sys
d=json.load(open(sys.argv[1]))
sys.exit(0 if all(l.get("how") and l.get("dollars") is not None
                  for r in d["included"] for l in r["ledger"]) else 1)
PY
# Presentation figures are computed, not rounded in prose.
python3 - "$A" <<'PY' && ok "rounded presentation figures are computed" || bad "no computed rounding"
import json,sys
r=json.load(open(sys.argv[1]))["range"]
sys.exit(0 if all(k in r for k in ("supported_low_rounded","supported_high_rounded","median_rounded")) else 1)
PY
python3 scripts/net_sheet.py build --adjusted "$A" --costs $P/costs.json --out "$N" >/dev/null 2>&1 \
  && ok "net sheet builds" || bad "net sheet errored"
python3 - "$N" <<'PY' && ok "every scenario re-derives" || bad "a scenario does not re-derive"
import json,sys
for s in json.load(open(sys.argv[1]))["scenarios"]:
    if abs(round(sum(l["amount"] for l in s["lines"]),2)-s["total_costs"])>0.01: sys.exit(1)
    if abs(round(s["price"]-s["total_costs"]-s["mortgage_payoff"],2)-s["estimated_net_to_seller"])>0.01: sys.exit(1)
PY
# A net sheet on an unsupported price is a number the seller will hold the agent to.
python3 scripts/net_sheet.py build --adjusted $F/adjusted.json --costs $P/costs.json --out /dev/null >/dev/null 2>&1 \
  && bad "built a net sheet below the comp floor" || ok "refuses a net sheet below the comp floor"

echo "== gate: a clean brief passes =="
python3 scripts/brief_gate.py check --adjusted $P/adjusted.json --net-sheet $P/net_sheet.json \
  --brief $P/brief.md >/dev/null 2>&1 && ok "pass fixture exits 0" || bad "pass fixture did not pass"

echo "== gate: a broken brief fails, gate by gate =="
REPORT=$(python3 scripts/brief_gate.py check --adjusted $F/adjusted.json --net-sheet $F/net_sheet.json \
           --brief $F/brief.md 2>&1)
[ $? -ne 0 ] && ok "fail fixture exits non-zero" || bad "fail fixture exited 0 — the gate is not wired"
for g in COMP_FLOOR ADJUSTED EXCLUSIONS NET_SHEET GROUNDED NOT_APPRAISAL COMPLIANCE; do
  echo "$REPORT" | grep -q "FAIL  $g" && ok "$g fires" || bad "$g never fired"
done
echo "$REPORT" | grep -q "could not be imported" && bad "compliance import is broken" || ok "compliance baseline imported"

echo
echo "$PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
