#!/usr/bin/env bash
# 2-minute proof: Python owns every number, and the gate refuses a brief with
# an untraceable figure.  bash demo/demo.sh
set -u
cd "$(dirname "$0")/.."
P() { printf '\n\033[1m%s\033[0m\n' "$*"; }

P "THE SCENARIO — six closed sales, one subject property. Python computes the range:"
python3 -c "
import json
a = json.load(open('tests/fixtures/pass/adjusted.json'))
print(f\"    comps used: {len(a['included'])}, excluded: {len(a['excluded'])} (each with a named reason)\")
r = a['range']
print(f\"    supported range: \${r['supported_low_rounded']:,.0f} - \${r['supported_high_rounded']:,.0f}\")"

P "EVERY ADJUSTMENT SHOWS ITS FORMULA:"
python3 -c "
import json
c = json.load(open('tests/fixtures/pass/adjusted.json'))['included'][0]
for l in c['ledger'][:3]:
    print(f\"    {l['feature']:<12} {l['how']:<44} {l['dollars']:>+10,.0f}\")"

P "THE WRONG BRIEF — a figure Python never computed, appraisal language, a mystery exclusion:"
python3 scripts/brief_gate.py check --adjusted tests/fixtures/fail/adjusted.json \
  --net-sheet tests/fixtures/fail/net_sheet.json --brief tests/fixtures/fail/brief.md 2>&1 \
  | grep -E "FAIL|failure" | head -10

P "THE RIGHT BRIEF — every number traces to a computed output:"
python3 scripts/brief_gate.py check --adjusted tests/fixtures/pass/adjusted.json \
  --net-sheet tests/fixtures/pass/net_sheet.json --brief tests/fixtures/pass/brief.md 2>&1 | tail -2

P "Not an appraisal, never claims to be — and below 3 comps it refuses to produce a range at all."
