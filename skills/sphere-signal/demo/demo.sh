#!/usr/bin/env bash
# 2-minute proof: reasons are computed from dates, and the gate refuses spam,
# inference, and anything that would auto-send.  bash demo/demo.sh
set -u
cd "$(dirname "$0")/.."
P() { printf '\n\033[1m%s\033[0m\n' "$*"; }

P "THE SCENARIO — a 5-contact database, one opted out. Who has a REASON to hear from you?"
python3 scripts/notice.py scan --contacts tests/fixtures/pass/contacts.csv \
  --touchpoints tests/fixtures/pass/touchpoints.csv --today 2026-08-29 --out /tmp/demo-reasons.json

P "EVERY REASON IS A DATE, NOT A GUESS:"
python3 -c "
import json
for r in json.load(open('/tmp/demo-reasons.json'))['reasons'][:4]:
    print(f\"    {r['contact_name']:<16} {r['reason']:<20} {r['human']}\")"

P "THE WRONG DRAFTS — no reason, opted-out contact, 'now that the kids are older', status=sent:"
python3 scripts/touch_gate.py check --drafts tests/fixtures/fail/drafts.json \
  --reasons tests/fixtures/fail/reasons.json --contacts tests/fixtures/fail/contacts.csv 2>&1 \
  | grep -E "FAIL|failure" | head -12

P "THE RIGHT DRAFTS — a kept promise first, an earned ask, every figure sourced:"
python3 scripts/touch_gate.py check --drafts tests/fixtures/pass/drafts.json \
  --reasons tests/fixtures/pass/reasons.json --contacts tests/fixtures/pass/contacts.csv 2>&1 | tail -2

P "AND THE PART A GATE CANNOT SHOW: a contacts file with a 'kids' column refuses to even load:"
printf 'id,name,kids\nc-1,Test,2\n' > /tmp/demo-bad.csv
python3 scripts/notice.py scan --contacts /tmp/demo-bad.csv --out /dev/null 2>&1 | head -2

P "Nothing here ever sends. A person approves every draft. That is why it can be trusted."
