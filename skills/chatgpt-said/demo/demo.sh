#!/usr/bin/env bash
# 2-minute proof: watch the gate refuse a bad reconciliation, then pass a real one.
# No setup, no keys, no network. Run it from anywhere:  bash demo/demo.sh
set -u
cd "$(dirname "$0")/.."
P() { printf '\n\033[1m%s\033[0m\n' "$*"; }

P "THE SCENARIO"
echo "A seller pasted their home into ChatGPT. It said \$540,000. The agent's comp"
echo "set says \$505-522k. Here is what the chatbot told them, verbatim:"
echo; sed 's/^/    /' tests/fixtures/pass/chatbot.txt | head -8; echo "    ..."

P "STEP 1 — split it into checkable claims (deterministic, not narrative)"
python3 scripts/claim_split.py show --claims tests/fixtures/pass/claims.json | head -8

P "STEP 2 — the WRONG response. The agent argues, drops a claim, asserts unsourced numbers:"
sed 's/^/    /' tests/fixtures/fail/reconciliation.md | sed -n '1,5p'

P "THE GATE REFUSES IT — every failure named:"
python3 scripts/reconcile_gate.py check --claims tests/fixtures/fail/claims.json \
  --reconciliation tests/fixtures/fail/reconciliation.md 2>&1 | grep -E "FAIL|failure" | head -12

P "STEP 3 — the RIGHT response. Agreement first, every claim answered, every figure traced:"
sed 's/^/    /' tests/fixtures/pass/reconciliation.md | sed -n '10,16p'

P "THE GATE PASSES IT:"
python3 scripts/reconcile_gate.py check --claims tests/fixtures/pass/claims.json \
  --reconciliation tests/fixtures/pass/reconciliation.md 2>&1 | tail -2

P "That is the product: the argument you did NOT have."
