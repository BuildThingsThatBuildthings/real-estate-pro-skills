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
# posting window is 06:00-22:00 Central inclusive (last start 22:00) at 5 posts/day, 1h lead,
# by default, in the example pipeline, and in the live pipeline.json when present
RE_SKILLS_CONFIG_DIR="$EX" python3 -c "
import sys; sys.path.insert(0,'scripts'); import config
assert set(config.FORBIDDEN_HOURS) == {0,1,2,3,4,5,23}, config.FORBIDDEN_HOURS
assert (config.EARLIEST_START, config.LATEST_START) == ('06:00', '22:00')
assert config.in_window('22:00') and config.in_window('06:00')
assert not config.in_window('22:15') and not config.in_window('05:45')
assert config.LEAD_HOURS == 1, config.LEAD_HOURS
assert config.MIN_GLOBAL_STAGGER == 10
assert list(config.RUNGS) == [5], config.RUNGS
assert (config.BLOCK_DAYS, config.HORIZON_BLOCKS) == (30, 2)
print('ok')" >/dev/null 2>&1 && ok "default window is 06:00-22:00 inclusive, 1h lead, 5/day, 10-min stagger" || bad "default window/rungs/stagger wrong"
cp ../../config/pipeline.example.json "$EX/pipeline.json"
RE_SKILLS_CONFIG_DIR="$EX" python3 -c "
import sys; sys.path.insert(0,'scripts'); import config
assert set(config.FORBIDDEN_HOURS) == {0,1,2,3,4,5,23}, config.FORBIDDEN_HOURS
assert (config.EARLIEST_START, config.LATEST_START) == ('06:00', '22:00')
assert config.in_window('22:00') and config.in_window('06:00')
assert not config.in_window('22:15') and not config.in_window('05:45')
assert config.LEAD_HOURS == 1, config.LEAD_HOURS
assert config.MIN_GLOBAL_STAGGER == 10
assert list(config.RUNGS) == [5], config.RUNGS
assert (config.BLOCK_DAYS, config.HORIZON_BLOCKS) == (30, 2)
print('ok')" >/dev/null 2>&1 && ok "pipeline.example.json window is 06:00-22:00 inclusive, 1h lead, 5/day, 10-min stagger" || bad "example window/rungs/stagger wrong"
if [ -f ../../config/pipeline.json ]; then
  cp ../../config/pipeline.json "$EX/pipeline.json"
  RE_SKILLS_CONFIG_DIR="$EX" python3 -c "
import sys; sys.path.insert(0,'scripts'); import config
assert set(config.FORBIDDEN_HOURS) == {0,1,2,3,4,5,23}, config.FORBIDDEN_HOURS
assert (config.EARLIEST_START, config.LATEST_START) == ('06:00', '22:00')
assert config.in_window('22:00') and config.in_window('06:00')
assert not config.in_window('22:15') and not config.in_window('05:45')
assert config.LEAD_HOURS == 1, config.LEAD_HOURS
assert list(config.RUNGS) == [5], config.RUNGS
print('ok')" >/dev/null 2>&1 && ok "live pipeline.json window is 06:00-22:00 inclusive, 1h lead, at 5/day" || bad "live pipeline.json window/rungs wrong"
fi
# no ladder slot at or after 22:00 or before 06:00, whatever the scorer returns
RE_SKILLS_CONFIG_DIR="$EX" python3 -c "
import sys; sys.path.insert(0,'scripts'); import windows
windows.score = lambda rs: dict.fromkeys(range(24), {})
order = windows.ladder_order([])
assert order and all('06:00' <= s <= '22:00' and (s.endswith(':15') or s == '22:00') for s in order), order
assert '22:00' in order and '22:15' not in order, order
assert [windows.daypart_of(s) for s in order[:3]] == ['morning','afternoon','evening'], order
print('ok')" >/dev/null 2>&1 && ok "daypart ladder stays inside 06:00-22:00 (hour 22 = 22:00) and opens one slot per daypart" || bad "ladder escapes the window or clusters"
rm -rf "$EX"

rm -rf "$EMPTY"

echo "== python unit tests (offline) =="
if python3 -m unittest discover -s tests -p 'test_*.py' >/tmp/pbs-unittest.$$ 2>&1; then
  ok "$(grep -E '^Ran ' /tmp/pbs-unittest.$$)"
else
  cat /tmp/pbs-unittest.$$; bad "python unit tests"
fi
rm -f /tmp/pbs-unittest.$$
echo
echo "$PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
