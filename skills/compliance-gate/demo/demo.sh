#!/usr/bin/env bash
# 90-second proof: the copy that FEELS warm is the copy that creates liability.
set -u
cd "$(dirname "$0")/.."
P() { printf '\n\033[1m%s\033[0m\n' "$*"; }

P "THIS CAPTION READS AS NORMAL MARKETING:"
sed 's/^/    /' tests/fixtures/fail/copy.txt

P "THE GATE READS IT DIFFERENTLY:"
python3 scripts/fair_housing.py check --file tests/fixtures/fail/copy.txt 2>&1 | sed -n '2,14p'

P "AND THE COMPLIANT VERSION OF THE SAME LISTING PASSES:"
sed 's/^/    /' tests/fixtures/pass/copy.txt
python3 scripts/fair_housing.py check --file tests/fixtures/pass/copy.txt 2>&1 | tail -2

P "One copy of these rules, imported by every skill in the bundle. Change it once, every gate updates."
