#!/usr/bin/env bash
# 90-second proof: why this scheduler is safe to hand to a second person.
# The write path needs live credentials; the property worth demonstrating
# does not.  bash demo/demo.sh
set -u
cd "$(dirname "$0")/.."
P() { printf '\n\033[1m%s\033[0m\n' "$*"; }

P "THE FAILURE THIS SKILL REFUSES TO ALLOW:"
echo "  Two people share the bundle. One sets up a profile dir but forgets channels.json."
echo "  A scheduler that 'helpfully' falls back to the repo config would post THEIR"
echo "  content to YOUR accounts. So it refuses instead:"
EMPTY=$(mktemp -d)
RE_SKILLS_CONFIG_DIR="$EMPTY" python3 -c "
import sys; sys.path.insert(0,'scripts')
try:
    import config
    print('    (unexpectedly loaded — this would be the bug)')
except Exception as e:
    print('    REFUSED:', str(e).splitlines()[0])
    for line in str(e).splitlines()[1:3]: print('   ', line)"

P "A COMPLETE PROFILE DIR IS AUTHORITATIVE — nothing from the repo leaks in:"
cat > "$EMPTY/channels.json" <<'JSON'
{"channels": {"999": {"label": "demo-profile", "platform": "tiktok", "brand": "demo"}},
 "min_gap_minutes": 45}
JSON
RE_SKILLS_CONFIG_DIR="$EMPTY" python3 -c "
import sys; sys.path.insert(0,'scripts'); import config
print(f'    channel 999 -> {config.NAME[999]}, min gap {config.MIN_GAP} min')"
rm -rf "$EMPTY"

P "AND THE LIVE PIPELINE HAS A PREFLIGHT — doctor.py runs 18 checks before anything writes:"
echo "  posting windows derived from YOUR analytics, a cadence ramp, same-channel"
echo "  collision detection, one distinct caption per channel, and every write"
echo "  verified after the fact (the API returns success without reliably persisting)."
echo
echo "  python3 scripts/doctor.py     # run it with your key to see all 18"
