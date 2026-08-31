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

echo "== composite: the full pipeline runs offline on the fixture agent =="
TMP=$(mktemp -d)
python3 - "$TMP" <<'PY'
# a plain base image; composite must work on ANY base
import sys
from PIL import Image
Image.new("RGB", (1200, 1500), (16, 42, 67)).save(sys.argv[1] + "/base.jpg")
PY
python3 scripts/composite.py --base "$TMP/base.jpg" --agent tests/fixtures/agent \
  --channel ig --headline "The county record says 2,400 square feet." \
  --subhead "Just listed: 412 Maple Ridge Dr. Showings start Saturday. Request a time through the link." \
  --allow-demo --out "$TMP/out.jpg" >/dev/null 2>&1 \
  && ok "composite runs" || bad "composite failed"
python3 - "$TMP" <<'PY' && ok "subhead is rendered and recorded" || bad "subhead dropped (the silent-drop regression)"
import json, sys
m = json.load(open(sys.argv[1] + "/out.composite.json"))
types = [e["type"] for e in m["elements"]]
sys.exit(0 if "subhead" in types else 1)
PY
python3 - "$TMP" <<'PY' && ok "logo does not overlap the text block" || bad "logo collides with headline/subhead"
import json, sys
m = json.load(open(sys.argv[1] + "/out.composite.json"))
els = {e["type"]: e for e in m["elements"]}
lo, hd, sb = els["logo"]["box"], els["headline"]["box"], els["subhead"]["box"]
block = (hd[0], hd[1], hd[2], sb[3])
overlap = not (lo[2] <= block[0] or block[2] <= lo[0] or lo[3] <= block[1] or block[3] <= lo[1])
sys.exit(1 if overlap else 0)
PY
# the wrap bug lived on the story format, where the larger compliance font
# pushed the disclosure off the right edge — so that is where it is pinned
python3 scripts/composite.py --base "$TMP/base.jpg" --agent tests/fixtures/agent \
  --channel igs --headline "The county record says 2,400 square feet." \
  --subhead "Just listed: 412 Maple Ridge Dr." \
  --allow-demo --out "$TMP/out-igs.jpg" >/dev/null 2>&1
python3 - "$TMP" <<'PY' && ok "compliance text wraps inside the safe zone (igs)" || bad "compliance text overflows the frame"
import json, sys
m = json.load(open(sys.argv[1] + "/out-igs.composite.json"))
W = m["size"][0]; sr = m["safe_zone"]["right"]
comp = [e for e in m["elements"] if e["type"] == "compliance"]
sys.exit(0 if comp and all(e["box"][2] <= W - sr + 1 for e in comp) and any(e.get("lines", 1) >= 2 for e in comp) else 1)
PY
# demo persona without --allow-demo must refuse
python3 scripts/composite.py --base "$TMP/base.jpg" --agent tests/fixtures/agent \
  --channel ig --headline "x" --out "$TMP/refused.jpg" >/dev/null 2>&1 \
  && bad "demo persona produced listing content without --allow-demo" \
  || ok "demo persona refuses without --allow-demo"
rm -rf "$TMP"

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
