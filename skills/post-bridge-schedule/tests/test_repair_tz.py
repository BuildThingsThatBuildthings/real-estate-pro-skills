"""repair.py: real Nashville time and the lint's own slot set.

Offline: urllib and every Post Bridge call are blocked, analytics are mocked.
"""
import argparse
import io
import sys
import unittest
from collections import defaultdict
from contextlib import redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parent.parent / 'scripts'
sys.path.insert(0, str(SCRIPTS))
import pb  # noqa: E402
import repair  # noqa: E402
import create_batch  # noqa: E402

# analytics-ranked hours, as windows.score returns them (best first)
SCORES = dict.fromkeys([13, 11, 14, 16, 19, 18, 12, 20, 9, 15, 21, 8, 10, 17], {})
CH = 101


def rec(ident, utc, status='scheduled', accounts=(CH,)):
    return {'id': ident, 'status': status, 'scheduled_at': utc, 'social_accounts': list(accounts)}


class RepairTimezone(unittest.TestCase):
    def setUp(self):
        for target in ('urllib.request.urlopen', 'pb.req', 'pb.paged'):
            p = patch(target, side_effect=AssertionError(f'{target}: network / Post Bridge forbidden in tests'))
            p.start()
            self.addCleanup(p.stop)
        for name, value in (('NAME', {CH: 'test-channel'}), ('MIN_GAP', 90), ('LADDER', [])):
            p = patch.object(repair, name, value)
            p.start()
            self.addCleanup(p.stop)

    def test_after_dst_ends_nov_10_19_15_ct_is_01_15z_nov_11(self):
        repair.LADDER = ['19:15']
        post = rec('p1', '2026-11-10T20:00:00Z')          # 14:00 CST
        slot = repair.free_slot(post, [post], defaultdict(list))
        self.assertEqual(slot.strftime('%Y-%m-%d %H:%M'), '2026-11-10 19:15')
        # the old month guess called November UTC-5 and would have written 00:15Z
        self.assertEqual(slot.astimezone(timezone.utc), datetime(2026, 11, 11, 1, 15, tzinfo=timezone.utc))
        self.assertEqual(repair.when(rec('x', '2026-11-11T01:15:00Z')).strftime('%Y-%m-%d %H:%M'),
                         '2026-11-10 19:15')
        # and the day before DST ends is still CDT
        self.assertEqual(repair.when(rec('y', '2026-11-01T00:15:00Z')).strftime('%Y-%m-%d %H:%M'),
                         '2026-10-31 19:15')

    def test_repair_moves_to_2200_never_2215(self):
        """06:00-22:00 CT inclusive: 22:00 is a legal move target, 22:15 is skipped."""
        repair.LADDER = ['22:15', '22:00']
        post = rec('p1', '2026-11-10T20:00:00Z')          # 14:00 CST
        slot = repair.free_slot(post, [post], defaultdict(list))
        self.assertEqual(slot.strftime('%Y-%m-%d %H:%M'), '2026-11-10 22:00')
        repair.LADDER = ['22:15', '05:45']
        self.assertIsNone(repair.free_slot(post, [post], defaultdict(list)))

    def test_slot_set_equals_the_lint_allowed_set(self):
        with patch('windows.rows', return_value=[]), patch('windows.score', return_value=SCORES):
            ladder = repair.allowed_ladder()
            allowed = create_batch._allowed_ct()
        self.assertEqual(set(ladder), allowed)
        self.assertEqual(len(ladder), len(allowed))
        for rejected in ('15:00', '20:30', '12:00', '18:00', '10:00'):
            self.assertNotIn(rejected, ladder)

    def test_analytics_failure_has_no_invented_fallback(self):
        with patch('windows.rows', side_effect=RuntimeError('unavailable')):
            with self.assertRaises(RuntimeError):
                repair.allowed_ladder()
        with self.assertRaises(RuntimeError):
            repair.free_slot(rec('p1', '2026-11-10T20:00:00Z'), [], defaultdict(list))

    def test_posted_and_processing_records_occupy_their_slot(self):
        """Scored 19, 21 -> daypart ladder 09:15 (morning default), 13:15 (afternoon default),
        19:15, 21:15. A non-scheduled record at 09:15 CT takes the first choice, 13:15 is inside
        90 min of a (14:00), so the move lands on 19:15 CT = 01:15Z."""
        a = rec('a', '2026-11-10T20:00:00Z')              # 14:00 CST
        b = rec('b', '2026-11-10T20:30:00Z')              # 14:30 CST, collides with a -> b moves
        for status in ('posted', 'processing'):
            busy = rec('busy', '2026-11-10T15:15:00Z', status=status)   # 09:15 CST
            moved = []

            def fake_patch(pid, body, check):
                moved.append((pid, body))
                return True, 'mocked'

            with patch('windows.rows', return_value=[]), \
                    patch('windows.score', return_value=dict.fromkeys([19, 21], {})), \
                    patch.object(repair, 'live', return_value=[a, b]), \
                    patch('pb.paged', return_value=[a, b, busy]), \
                    patch.object(repair, 'patch_verify', side_effect=fake_patch), \
                    redirect_stdout(io.StringIO()):
                repair.cmd_fix(argparse.Namespace(dedupe=False, collisions=True, all=False))
            self.assertEqual(moved, [('b', {'scheduled_at': '2026-11-11T01:15:00Z'})], status)


if __name__ == '__main__':
    unittest.main()
