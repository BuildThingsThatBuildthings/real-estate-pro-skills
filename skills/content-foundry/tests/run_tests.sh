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
# vertical crops bias downward: sky/ceiling is dead space in listing photos
python3 - <<'PY' && ok "cover_crop keeps the subject low on vertical crops" || bad "cover_crop centers vertically (ceiling-heavy)"
import sys; sys.path.insert(0, "scripts")
from PIL import Image
import composite
spy = {}
orig = Image.Image.crop
Image.Image.crop = lambda self, b: spy.update(b=b) or orig(self, b)
composite.cover_crop(Image.new("RGB", (2048, 1360)), (1200, 630))
Image.Image.crop = orig
y = spy["b"][1]
nh = 1360 * (1200 / 2048)
centered = (nh - 630) // 2
sys.exit(0 if y > centered else 1)
PY

# demo persona without --allow-demo must refuse
python3 scripts/composite.py --base "$TMP/base.jpg" --agent tests/fixtures/agent \
  --channel ig --headline "x" --out "$TMP/refused.jpg" >/dev/null 2>&1 \
  && bad "demo persona produced listing content without --allow-demo" \
  || ok "demo persona refuses without --allow-demo"
rm -rf "$TMP"

echo "== no-drop path: research-only library jobs run without a drop =="
TMP=$(mktemp -d)
mkdir -p "$TMP/empty"
python3 scripts/inventory.py "$TMP/empty" --out "$TMP/r0/asset-manifest.json" >/dev/null 2>&1
[ $? -eq 1 ] && ok "empty drop still stops by default" || bad "empty drop no longer stops"
python3 scripts/inventory.py "$TMP/empty" --allow-empty --out "$TMP/r0/asset-manifest.json" >/dev/null 2>&1
[ $? -eq 1 ] && ok "--allow-empty without --job refuses" || bad "no-drop run allowed without naming a job"
python3 scripts/inventory.py none --job 1 --out "$TMP/r1/asset-manifest.json" >/dev/null 2>&1
[ $? -eq 1 ] && [ ! -f "$TMP/r1/run.json" ] && ok "listing job (#1) refuses to run with no drop" \
  || bad "a job that needs drop assets ran with no drop"
for J in 4 7 8 "market update"; do
  R="$TMP/r-$(echo $J | tr ' ' '-')"
  python3 scripts/inventory.py none --job "$J" --out "$R/asset-manifest.json" >/dev/null 2>&1 \
    && python3 - "$R" <<'PY' && ok "job '$J' runs with no drop and run.json records it" || bad "job '$J' no-drop path broken"
import json, sys
r = json.load(open(sys.argv[1] + "/run.json"))["drop"]
m = json.load(open(sys.argv[1] + "/asset-manifest.json"))["drop"]
sys.exit(0 if r["mode"] == m["mode"] == "none" and r["job"] in (4, 7, 8) else 1)
PY
done
python3 scripts/inventory.py "$TMP/empty" --allow-empty --job 4 --out "$TMP/r-ae/asset-manifest.json" >/dev/null 2>&1 \
  && ok "--allow-empty --job 4 on an empty folder runs" || bad "--allow-empty --job 4 refused"
python3 scripts/unify.py "$TMP/r-4/asset-manifest.json" --out "$TMP/r-4/unified-context.md" >/dev/null 2>&1 \
  && grep -q "Source drop: \*\*none\*\*" "$TMP/r-4/unified-context.md" \
  && ok "unify writes a no-drop context document" || bad "unify stops on a recorded no-drop run"
python3 scripts/unify.py "$TMP/r0/asset-manifest.json" --out "$TMP/r0/u.md" >/dev/null 2>&1
[ $? -eq 1 ] && ok "unify still stops on an empty drop that was not allowed" || bad "unify accepted an unallowed empty drop"
# #5 agent intro: the headshot must come from the agent folder
cp -R tests/fixtures/agent "$TMP/agent"
python3 scripts/inventory.py none --job 5 --agent "$TMP/agent" --out "$TMP/r5a/asset-manifest.json" >/dev/null 2>&1
[ $? -eq 1 ] && ok "#5 refuses with no headshot in the agent folder" || bad "#5 ran with no headshot"
cp tests/fixtures/agent/logos/riley-shore-dark.png "$TMP/agent/logos/headshot.png"
printf '\n## Headshot\n- headshot: logos/headshot.png\n' >> "$TMP/agent/brand-context-visual.md"
python3 scripts/inventory.py none --job 5 --agent "$TMP/agent" --out "$TMP/r5b/asset-manifest.json" >/dev/null 2>&1 \
  && python3 -c "import json,sys; d=json.load(open('$TMP/r5b/run.json'))['drop']; sys.exit(0 if 'headshot' in d['satisfied_from_agent_folder'] else 1)" \
  && ok "#5 runs when the agent folder has a headshot" || bad "#5 refused despite a headshot"
rm -rf "$TMP"

echo "== agent folder: fonts, pending wording, linked assets =="
TMP=$(mktemp -d)
python3 -c "from PIL import Image; Image.new('RGB',(1200,1500),(16,42,67)).save('$TMP/base.jpg')"
cp -R tests/fixtures/agent "$TMP/agent"
mkdir -p "$TMP/agent/fonts"
cp assets/fonts/PlayfairDisplay.ttf "$TMP/agent/fonts/Headline.ttf"
cp assets/fonts/SourceSans3.ttf "$TMP/agent/fonts/Body.ttf"
printf -- '- headline font: fonts/Headline.ttf\n- body font: fonts/Body.ttf\n' >> "$TMP/agent/brand-context-visual.md"
HERE=$PWD
(cd "$TMP" && python3 "$HERE/scripts/composite.py" --base base.jpg --agent agent --channel ig \
  --headline "The county record says 2,400 square feet." --subhead "Showings start Saturday." \
  --allow-demo --out out.jpg >/dev/null 2>&1)
python3 - "$TMP" <<'PY' && ok "relative headline/body fonts resolve against the agent folder" || bad "declared fonts ignored or resolved against the cwd"
import json, sys
m = json.load(open(sys.argv[1] + "/out.composite.json"))
f = m.get("fonts", {})
ok = (f.get("headline", "").endswith("agent/fonts/Headline.ttf")
      and f.get("body", "").endswith("agent/fonts/Body.ttf")
      and not any("fell back" in w for w in m["warnings"]))
sys.exit(0 if ok else 1)
PY
sed -i.bak 's/^- agent license number:.*/- agent license number: [PENDING — request from brokerage]/' "$TMP/agent/brand-context-compliance.md"
OUT=$(python3 scripts/composite.py --base "$TMP/base.jpg" --agent "$TMP/agent" --channel ig \
  --headline "x" --allow-demo --out "$TMP/p.jpg" 2>&1)
[ $? -ne 0 ] && echo "$OUT" | grep -q "compliance strings not filled: license" \
  && ! echo "$OUT" | grep -q "blank template" \
  && ok "[PENDING …] reports unfilled compliance strings, still blocks" \
  || bad "[PENDING …] misreported or not blocking: $OUT"
# drive_sync agent-folder links the declared asset folder from Drive
mkdir -p "$TMP/cfg" "$TMP/cache/demo/brand-context/my business/assets"
cat > "$TMP/cfg/clients.json" <<JSON
{"cache_root": "$TMP/cache", "clients": {"demo": {"name": "Demo", "posting_enabled": false, "drive": {}}}}
JSON
BC="$TMP/cache/demo/brand-context/my business"
for f in about-me.md brand-voice.md working-style.md; do echo "# $f" > "$BC/$f"; done
cp tests/fixtures/agent/brand-context-compliance.md "$BC/GUARDRAILS.md"
sed 's#logos/#assets/#' tests/fixtures/agent/brand-context-visual.md > "$BC/brand-context-visual.md"
cp tests/fixtures/agent/logos/*.png "$BC/assets/"
RE_SKILLS_CONFIG_DIR="$TMP/cfg" python3 scripts/drive_sync.py agent-folder --client demo >"$TMP/af.log" 2>&1
python3 - "$TMP/cache/demo/agent" <<'PY' && ok "agent-folder links assets/ and the logo resolves" || { bad "agent-folder logo does not resolve"; cat "$TMP/af.log"; }
import sys; sys.path.insert(0, "scripts")
from brandkit import AgentBrand
b = AgentBrand(sys.argv[1])
sys.exit(0 if b.logo_path("light").exists() and b.logo_path("dark").exists() else 1)
PY
grep -q "MISSING" "$TMP/af.log" && bad "agent-folder reported a declared asset missing" || ok "agent-folder reports nothing missing"
python3 - "$TMP/agent" <<'PY' && ok "a declared path that escapes the folder is still refused" || bad "tenancy escape accepted"
import sys, re; sys.path.insert(0, "scripts")
from pathlib import Path
from brandkit import AgentBrand, BrandError
v = Path(sys.argv[1], "brand-context-visual.md")
v.write_text(re.sub(r"(light background:).*", r"\1 ../escape.png", v.read_text()))
Path(sys.argv[1]).parent.joinpath("escape.png").write_bytes(b"x")
try:
    AgentBrand(sys.argv[1]).logo_path("light"); sys.exit(1)
except BrandError as e:
    sys.exit(0 if "escapes" in str(e) else 1)
PY
rm -rf "$TMP"

echo "== market-update video props: sourced stats, legible inks =="
TMP=$(mktemp -d)
cat > "$TMP/scenes.json" <<'JSON'
{"kind": "market", "headline": "h", "subline": "s", "hook": "k",
 "market": {"area": "Fictional County", "period": "Demo month",
  "stats": [{"label": "Median price", "value": "$400,000", "detail": "", "source": ""}]}}
JSON
OUT=$(python3 scripts/video_props.py --agent tests/fixtures/agent --allow-demo \
  --scenes "$TMP/scenes.json" --out "$TMP/props.json" 2>&1)
[ $? -eq 1 ] && echo "$OUT" | grep -q "uncited" && ok "an uncited market stat stops the video" \
  || bad "uncited market stat passed: $OUT"
python3 - <<'PY' && ok "market inks clear WCAG on a light ground; unreadable ground stops" || bad "market ink selection broken"
import sys; sys.path.insert(0, "scripts")
from brandkit import contrast_ratio, hex_to_rgb
import video_props as vp
colors = {"primary": "#1d77b8", "accent": "#e63946", "text-on-light": "#0f1b2d",
          "text-on-dark": "#ffffff", "light-ground": "#f4f7fb"}
cfg = {"market": {"period": "Demo month", "stats": [
    {"label": "Median", "value": "$1", "source": "Demo"}]}}
m = vp.market_block(cfg, colors)
ok = contrast_ratio(hex_to_rgb(m["ink"]), hex_to_rgb(m["ground"])) >= 4.5
ok &= contrast_ratio(hex_to_rgb(m["valueInk"]), hex_to_rgb(m["ground"])) >= 3
ok &= m["ink"] != colors["text-on-dark"]
# a pale palette on a white ground falls back to neutral near-black, never white
pale = vp.market_block({"market": {**cfg["market"], "ground": "#ffffff"}},
                       {"primary": "#fafafa", "text-on-light": "#ffffff"})
ok &= pale["ink"] == "#111111"
try:  # a ground no ink can read on must stop, not render
    vp.market_block({"market": {**cfg["market"], "ground": "#101010"}},
                    {"primary": "#202020", "text-on-light": "#151515"})
    ok = False
except ValueError:
    pass
sys.exit(0 if ok else 1)
PY
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
