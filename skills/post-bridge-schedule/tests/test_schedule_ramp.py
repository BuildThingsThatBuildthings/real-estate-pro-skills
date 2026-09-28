"""Offline regression cases for the actual post-bridge-schedule ramp."""
import importlib.util
import sys
import unittest
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
CANONICAL = Path('/Users/ryan/real-estate-pro-skills/skills/post-bridge-schedule/scripts')
sys.path.insert(0, str(CANONICAL))
target = HERE / 'schedule_engine.py' if (HERE / 'schedule_engine.py').exists() else CANONICAL / 'schedule_engine.py'
spec = importlib.util.spec_from_file_location('tested_schedule_engine', target)
engine = importlib.util.module_from_spec(spec)
spec.loader.exec_module(engine)


class RampTests(unittest.TestCase):
    def setUp(self):
        self.net = patch('urllib.request.urlopen', side_effect=AssertionError('Network forbidden in tests'))
        self.net.start()
        self.addCleanup(self.net.stop)
        engine.RUNGS = [3, 5, 7, 8]
        engine.BLOCK = 30
        engine._cfg.HORIZON_BLOCKS = 2
        engine.CHANNELS = {i: str(i) for i in range(1, 10)}
        engine.N_CH = 9
        engine.MIN_GAP_MIN = 90
        engine.LEAD_HOURS = 36
        engine.FORBIDDEN_HOURS = set(range(8)) | {22, 23}
        engine.LADDER = ['08:15', '10:00', '11:45', '13:30', '15:15', '17:00', '18:45', '20:30']
        engine.SLOTS = {r: engine.LADDER[:r] for r in engine.RUNGS}
        self.now = datetime(2026, 9, 24, 12, tzinfo=engine.TZ)

    def post(self, ident, day, slot, channels=None):
        dt = datetime.combine(day, datetime.strptime(slot, '%H:%M').time(), engine.TZ)
        return {'id': ident, 'scheduled_at': dt.astimezone(timezone.utc).isoformat(),
                'social_accounts': list(engine.CHANNELS) if channels is None else channels}

    def test_first_30_then_second_30_before_five(self):
        p, b = engine.plan_placements([], 181, now=self.now)
        self.assertFalse(b)
        self.assertEqual(Counter(x[2] for x in p[:90]), {1: 90})
        self.assertEqual(Counter(x[2] for x in p[90:180]), {2: 90})
        self.assertTrue(all(x[1] == 3 for x in p[:180]))
        self.assertEqual(p[180][1:], (5, 1))

    def test_all_rungs_and_third_block(self):
        p, b = engine.plan_placements([], 481, now=self.now)
        self.assertFalse(b)
        self.assertEqual(Counter(r for _, r, _ in p[:480]), {3:180, 5:120, 7:120, 8:60})
        self.assertEqual(p[-1][1:], (3, 3))

    def test_continues_beyond_old_horizon(self):
        p, b = engine.plan_placements([], 961, now=self.now)
        self.assertFalse(b)
        self.assertEqual(p[-1][1:], (3, 5))
        self.assertGreater((p[-1][0].date() - engine.first_day(self.now)).days, 100)

    def test_blocked_block_one_prevents_block_two_and_next_rung(self):
        engine.LADDER = ['10:15']
        engine.SLOTS = {r: ['10:15'] for r in engine.RUNGS}
        p, b = engine.plan_placements([], 181, now=self.now)
        self.assertTrue(b)
        self.assertEqual(len(p), 30)
        self.assertTrue(all((r, block) == (3, 1) for _, r, block in p))

    def test_partial_deliveries_do_not_round_up(self):
        self.assertEqual(engine.gap(26, 3), 1)
        self.assertEqual(engine.gap(27, 3), 0)
        self.assertEqual(engine.gap(17, 3), 2)

    def test_existing_records_and_duplicate_ids_credit_once(self):
        d = engine.first_day(self.now)
        p = self.post('existing', d, '08:15')
        _, units = engine.occupancy([p, p])
        self.assertEqual(units[d], 9)
        plans, _ = engine.plan_placements([p, p], 2, now=self.now)
        # the morning already holds 08:15, so the day fills afternoon then evening
        self.assertEqual([x[0].strftime('%H:%M') for x in plans], ['13:30', '17:00'])

    def test_live_and_pending_spacing(self):
        d = engine.first_day(self.now)
        p = self.post('near', d, '09:00', [1])
        plans, _ = engine.plan_placements([p], 3, now=self.now)
        # afternoon, evening, then morning: 08:15 and 10:00 are inside 90 min of 09:00
        self.assertEqual([x[0].strftime('%H:%M') for x in plans], ['13:30', '17:00', '11:45'])

    def test_five_a_day_spreads_morning_afternoon_evening(self):
        engine.RUNGS = [5]
        engine.SLOTS = {5: engine.LADDER[:5]}
        p, b = engine.plan_placements([], 10, now=self.now)
        self.assertFalse(b)
        first = [t.strftime('%H:%M') for t, _, _ in p[:5]]
        # test LADDER is plain time order, so each daypart's best is its first slot
        self.assertEqual(first, ['08:15', '13:30', '17:00', '10:00', '15:15'])
        self.assertEqual(len({t.date() for t, _, _ in p[:5]}), 1)
        self.assertEqual(p[5][0].date() - p[0][0].date(), timedelta(days=1))

    def test_existing_records_count_toward_five(self):
        engine.RUNGS = [5]
        engine.SLOTS = {5: engine.LADDER[:5]}
        d = engine.first_day(self.now)
        existing = [self.post(f'e{i}', d, t) for i, t in enumerate(('10:23', '12:41', '14:57'))]
        p, _ = engine.plan_placements(existing, 2, now=self.now)
        self.assertEqual([t.date() for t, _, _ in p], [d, d])
        # evening is emptiest, then morning (clear of 10:23); never a third afternoon
        self.assertEqual([t.strftime('%H:%M') for t, _, _ in p], ['17:00', '08:15'])

    def test_real_timezone_at_dst_boundaries(self):
        before = self.post('pre', datetime(2026,11,1).date(), '00:15')
        after = self.post('post', datetime(2026,11,1).date(), '08:15')
        self.assertIn('05:15', before['scheduled_at'])
        self.assertIn('14:15', after['scheduled_at'])
        per, _ = engine.occupancy([before, after])
        self.assertEqual([t.hour for t in per[1]], [0, 8])

    def test_no_slot_before_lead(self):
        now = datetime(2026,9,24,23,tzinfo=engine.TZ)
        p, _ = engine.plan_placements([], 1, now=now)
        self.assertGreaterEqual(p[0][0].replace(tzinfo=engine.TZ), now + timedelta(hours=36))

    def test_supported_hours_beyond_top_eight_are_available(self):
        scores = dict.fromkeys([13,11,14,16,19,18,12,20,9,15,21,8,10,17], {})
        with patch("windows.rows", return_value=[]), patch("windows.score", return_value=scores):
            slots = engine._derived_slots()
        self.assertEqual(len(slots[8]), 8)
        self.assertIn("08:15", engine.LADDER)
        self.assertIn("21:15", engine.LADDER)
        self.assertEqual(len(engine.LADDER), 14)

    def test_analytics_failure_has_no_invented_fallback(self):
        with patch('windows.rows', side_effect=RuntimeError('unavailable')):
            with self.assertRaises(RuntimeError):
                engine._derived_slots()


if __name__ == '__main__':
    unittest.main()
