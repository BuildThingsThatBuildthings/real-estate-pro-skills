#!/usr/bin/env bash
# Offline tests for post-bridge-schedule. The write path needs live credentials
# and is exercised by doctor.py's preflight; these pin the property that makes
# the whole skill safe to hand to a second person:
#
#   an explicit profile dir is AUTHORITATIVE. A missing file there RAISES.
#   It never falls back to the repo config, because a silent fallback posts
#   one person's content to another person's accounts.
set -u
cd "$(dirname "$0")/.."
PASS=0; FAIL=0
ok()  { echo "  ok    $1"; PASS=$((PASS+1)); }
bad() { echo "  FAIL  $1"; FAIL=$((FAIL+1)); }

echo "== config isolation (the safety law) =="
EMPTY=$(mktemp -d)
# channels.json missing from an explicit profile dir must raise, not fall back
if RE_SKILLS_CONFIG_DIR="$EMPTY" python3 -c "import sys; sys.path.insert(0,'scripts'); import config" 2>/dev/null; then
  bad "empty profile dir silently fell back to repo config — CROSS-ACCOUNT POSTING RISK"
else
  ok "empty explicit profile dir refuses (no fallback to repo accounts)"
fi
# and the error must say what to do
ERR=$(RE_SKILLS_CONFIG_DIR="$EMPTY" python3 -c "import sys; sys.path.insert(0,'scripts'); import config" 2>&1)
echo "$ERR" | grep -q "channels" && ok "refusal names the missing file" || bad "refusal is unhelpful"

# a COMPLETE profile dir is honored over the repo config
cat > "$EMPTY/channels.json" <<'JSON'
{"channels": {"999": {"label": "isolated-test", "platform": "tiktok", "brand": "test"}},
 "min_gap_minutes": 45}
JSON
OUT=$(RE_SKILLS_CONFIG_DIR="$EMPTY" python3 -c "
import sys; sys.path.insert(0,'scripts'); import config
print(config.NAME[999], config.MIN_GAP)" 2>&1)
echo "$OUT" | grep -q "isolated-test 45" && ok "explicit profile dir is authoritative" || bad "profile dir not honored: $OUT"

echo "== the example config is valid and carries sane defaults =="
# Hermetic: config/channels.json is user config and never committed, so validate
# the EXAMPLE through a temp profile dir — the same file every new user copies.
EX=$(mktemp -d)
cp ../../config/channels.example.json "$EX/channels.json"
RE_SKILLS_CONFIG_DIR="$EX" python3 -c "
import sys; sys.path.insert(0,'scripts'); import config
assert config.NAME, 'no channels in the example'
assert config.MIN_GAP >= 1
print('ok')" >/dev/null 2>&1 && ok "channels.example.json loads with sane constants" || bad "example config broken"

echo "== forbidden hours actually forbid =="
RE_SKILLS_CONFIG_DIR="$EX" python3 -c "
import sys; sys.path.insert(0,'scripts'); import config
overnight = {0,1,2,3,4}
assert overnight & set(config.FORBIDDEN_HOURS), 'overnight hours are schedulable'
print('ok')" >/dev/null 2>&1 && ok "overnight hours are in the forbidden set by default" || bad "overnight scheduling possible by default"
rm -rf "$EX"

rm -rf "$EMPTY"
echo
echo "$PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
