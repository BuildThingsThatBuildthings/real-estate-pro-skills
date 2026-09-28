"""Per-account gap, cross-account stagger, the 06:00-22:00 window, median windows,
the daypart ladder, and the warehouse source with its live fallback.

Offline: urllib and every Post Bridge call are blocked; HTTP is mocked.
"""
import io
import json
import sys
import unittest
from collections import defaultdict
from contextlib import redirect_stderr
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parent.parent / 'scripts'
sys.path.insert(0, str(SCRIPTS))
import pb  # noqa: E402
import windows  # noqa: E402
import schedule_engine as engine  # noqa: E402
import create_batch  # noqa: E402

DAY = date(2026, 10, 7)
WINDOW_FORBIDDEN = {0, 1, 2, 3, 4, 5, 23}   # 22 is open: its slot is exactly 22:00
RUNGS_3578 = {3: 3, 5: 5, 7: 7, 8: 8}


def ct(hhmm, day=DAY):
    return datetime.combine(day, datetime.strptime(hhmm, '%H:%M').time())


class Offline(unittest.TestCase):
    def setUp(self):
        for target in ('urllib.request.urlopen', 'pb.req', 'pb.paged', 'subprocess.run'):
            p = patch(target, side_effect=AssertionError(f'{target}: network / Post Bridge forbidden in tests'))
            p.start()
            self.addCleanup(p.stop)


class EngineSpacing(Offline):
    def setUp(self):
        super().setUp()
        for name, value in (('CHANNELS', {i: f'ch{i}' for i in range(1, 10)}), ('MIN_GAP_MIN', 90),
                            ('MIN_STAGGER_MIN', 10), ('FORBIDDEN_HOURS', set(WINDOW_FORBIDDEN)),
                            ('LADDER', [])):
            p = patch.object(engine, name, value)
            p.start()
            self.addCleanup(p.stop)

    def slot(self, hhmm, per_ch, accounts, pending=()):
        return engine.free_slot(per_ch, DAY, [hhmm], list(pending), accounts=accounts)

    def test_adjacent_post_on_a_different_account_is_legal(self):
        per_ch = defaultdict(list, {2: [ct('10:23')]})
        self.assertEqual(self.slot('11:15', per_ch, {1}), ct('11:15'))    # 52 min, other account

    def test_adjacent_post_on_the_same_account_is_refused(self):
        per_ch = defaultdict(list, {2: [ct('10:23')]})
        self.assertIsNone(self.slot('11:15', per_ch, {2}))
        self.assertIsNone(self.slot('11:15', per_ch, {1, 2}))            # shares account 2
        self.assertIn('within 90 min', engine.slot_conflict(ct('11:15'), {2}, per_ch, []))

    def test_same_account_boundary_is_ninety_minutes(self):
        per_ch = defaultdict(list, {2: [ct('09:45')]})
        self.assertEqual(self.slot('11:15', per_ch, {2}), ct('11:15'))    # exactly 90 min

    def test_under_ten_minutes_from_any_post_is_refused(self):
        per_ch = defaultdict(list, {2: [ct('11:10')]})
        self.assertIsNone(self.slot('11:15', per_ch, {1}))
        self.assertIn('stagger', engine.slot_conflict(ct('11:15'), {1}, per_ch, []))
        per_ch = defaultdict(list, {2: [ct('11:05')]})
        self.assertEqual(self.slot('11:15', per_ch, {1}), ct('11:15'))    # exactly 10 min

    def test_pending_posts_follow_the_same_rules(self):
        pending = [(ct('10:23'), 'p', {2})]
        self.assertEqual(self.slot('11:15', {}, {1}, pending), ct('11:15'))
        self.assertIsNone(self.slot('11:15', {}, {2}, pending))
        # a two-field pending entry is a full-roster post: it shares every account
        self.assertIsNone(self.slot('11:15', {}, {1}, [(ct('10:23'), 'p')]))

    def test_full_roster_post_is_blocked_by_a_single_account_post(self):
        """A planned post fans out to every channel, so it shares an account with
        any single-account record and still needs 90 minutes from it."""
        per_ch = defaultdict(list, {7: [ct('10:23')]})
        self.assertIsNone(engine.free_slot(per_ch, DAY, ['11:15'], []))
        self.assertEqual(engine.free_slot(per_ch, DAY, ['11:15', '12:15'], []), ct('12:15'))

    def test_0600_and_0615_are_legal_and_0545_is_refused(self):
        self.assertEqual(self.slot('06:00', {}, None), ct('06:00'))
        self.assertEqual(self.slot('06:15', {}, None), ct('06:15'))
        self.assertIsNone(self.slot('05:45', {}, None))
        self.assertIsNone(self.slot('05:59', {}, None))

    def test_2200_is_the_latest_legal_start_and_2215_is_refused(self):
        """06:00 to 22:00 CT inclusive: a post may start exactly at 22:00, never after."""
        self.assertEqual(self.slot('21:45', {}, None), ct('21:45'))
        self.assertEqual(self.slot('22:00', {}, None), ct('22:00'))
        self.assertIsNone(self.slot('22:01', {}, None))
        self.assertIsNone(self.slot('22:15', {}, None))
        self.assertIsNone(self.slot('22:45', {}, None))
        self.assertIsNone(self.slot('23:15', {}, None))

    def test_a_blocked_2200_falls_back_inside_the_evening_never_later(self):
        ladder = ['22:00', '19:15', '11:15']
        with patch.object(engine, 'LADDER', ladder):
            per_ch = defaultdict(list, {1: [ct('21:30')]})
            self.assertEqual(engine.free_slot(per_ch, DAY, ['22:00'], []), ct('19:15'))


    def test_blocked_slot_falls_back_within_its_daypart_first(self):
        ladder = ['11:15', '13:15', '19:15', '08:15', '16:15', '18:15', '10:15', '15:15']
        with patch.object(engine, 'LADDER', ladder):
            # 11:15 is blocked on every account: the next morning slot wins, not 13:15
            per_ch = defaultdict(list, {1: [ct('11:05')]})
            self.assertEqual(engine.free_slot(per_ch, DAY, ['11:15'], []), ct('08:15'))
            # the whole morning blocked: only then another daypart
            per_ch = defaultdict(list, {1: [ct('08:00'), ct('09:30'), ct('11:05')]})
            self.assertEqual(engine.free_slot(per_ch, DAY, ['11:15'], []), ct('13:15'))

    def test_existing_posts_fill_the_emptiest_dayparts_first(self):
        """A day holding 10:23 / 12:41 / 14:57 gets its next posts in the evening,
        then in the morning away from 10:23, never another afternoon."""
        ladder = ['11:15', '13:15', '19:15', '08:15', '16:15', '18:15', '10:15', '15:15']
        per_ch = defaultdict(list)
        for hhmm in ('10:23', '12:41', '14:57'):
            for a in range(1, 10):
                per_ch[a].append(ct(hhmm))
        with patch.object(engine, 'LADDER', ladder), patch.object(engine, 'N_CH', 9):
            pending = []
            for _ in range(2):
                cands = engine.day_candidates(per_ch, pending, DAY, ladder[:5])
                pending.append((engine.free_slot(per_ch, DAY, cands, pending), 'p'))
        self.assertEqual([t for t, _ in pending], [ct('19:15'), ct('08:15')])


class LeadTime(Offline):
    """approval.lead_hours is 1: a new post may be placed an hour from now."""

    def setUp(self):
        super().setUp()
        for name, value in (('CHANNELS', {1: 'ch1'}), ('N_CH', 1), ('RUNGS', [1]), ('BLOCK', 30),
                            ('MIN_GAP_MIN', 45), ('MIN_STAGGER_MIN', 10),
                            ('FORBIDDEN_HOURS', set(WINDOW_FORBIDDEN)),
                            ('LADDER', ['21:15', '22:00']), ('SLOTS', {1: ['21:15', '22:00']}),
                            ('LEAD_HOURS', engine._cfg.LEAD_HOURS)):
            p = patch.object(engine, name, value)
            p.start()
            self.addCleanup(p.stop)

    def test_lead_is_one_hour(self):
        self.assertEqual(engine._cfg.LEAD_HOURS, 1.0)
        now = datetime.combine(DAY, datetime.strptime('20:30', '%H:%M').time(), engine.TZ)
        self.assertEqual(engine.first_day(now), DAY)
        placed, blocked = engine.plan_placements([], 1, now=now)
        # 21:15 is inside the hour; 22:00, the last legal start, is the first placement
        self.assertEqual([t for t, _, _ in placed], [ct('22:00')])
        self.assertEqual(blocked, [])

    def test_nothing_is_placed_after_2200(self):
        now = datetime.combine(DAY, datetime.strptime('21:01', '%H:%M').time(), engine.TZ)
        placed, blocked = engine.plan_placements([], 1, now=now)
        # earliest is 22:01: nothing is left today, so the post goes to tomorrow's first slot
        self.assertEqual([t for t, _, _ in placed], [ct('21:15', DAY + timedelta(days=1))])


class LintSpacing(Offline):
    def setUp(self):
        super().setUp()
        for name, value in (('scoped_channels', lambda: {1: 'ch1', 2: 'ch2'}),
                            ('_allowed_ct', lambda preferred=(): {'11:15'}),
                            ('MIN_GAP_MIN', 90), ('MIN_STAGGER_MIN', 10)):
            p = patch.object(create_batch, name, value)
            p.start()
            self.addCleanup(p.stop)
        # 11:15 CDT on DAY
        self.post = {'slug': 's', 'scheduled_at': '2026-10-07T16:15:00Z',
                     'captions': {'1': 'one', '2': 'two'}, 'youtube_title': 't', 'gmb_media_id': ''}

    def spacing(self, per_ch):
        errs = create_batch.lint({'posts': [self.post]}, defaultdict(list, per_ch))
        return [e for e in errs if 'within' in e]

    def utc(self, hhmm):
        return datetime.combine(DAY, datetime.strptime(hhmm, '%H:%M').time(),
                                engine.TZ).astimezone(timezone.utc)

    def test_other_account_post_52_min_away_passes(self):
        self.assertEqual(self.spacing({3: [self.utc('10:23')]}), [])

    def test_same_account_post_52_min_away_fails(self):
        errs = self.spacing({1: [self.utc('10:23')]})
        self.assertEqual(len(errs), 1)
        self.assertIn('ch1 within 90min', errs[0])

    def test_any_post_under_ten_minutes_fails(self):
        errs = self.spacing({3: [self.utc('11:10')]})
        self.assertEqual(len(errs), 1)
        self.assertIn('10min cross-account stagger', errs[0])


def rows_at(hour, platform, values, metric='v'):
    t = datetime(2026, 9, 1, hour, 30, tzinfo=windows.TZ)
    return [dict(p=platform, t=t, v=x if metric == 'v' else 0, l=x if metric == 'l' else 0)
            for x in values]


class MedianScoring(Offline):
    def setUp(self):
        super().setUp()
        for name, value in (('MIN_N', 8), ('FORBIDDEN', set(WINDOW_FORBIDDEN)),
                            ('VIEW_RELIABLE', {'tiktok', 'youtube', 'facebook'}),
                            ('LIKE_SIGNAL', {'instagram'})):
            p = patch.object(windows, name, value)
            p.start()
            self.addCleanup(p.stop)
        p = patch.object(windows, 'RUNG_SIZES', dict(RUNGS_3578))
        p.start()
        self.addCleanup(p.stop)

    def test_one_viral_outlier_does_not_make_its_hour_top(self):
        rs = (rows_at(13, 'tiktok', [5] * 9 + [1_000_000])     # mean ~100k, median 5
              + rows_at(11, 'tiktok', [100] * 10)
              + rows_at(15, 'tiktok', [60] * 10))
        ranked = list(windows.score(rs))
        self.assertEqual(ranked[0], 11)
        self.assertEqual(ranked[-1], 13)
        # evening has no evidence at all: it still gets its default 19:15
        self.assertEqual(windows.ladder(rs)[3], ['11:15', '15:15', '19:15'])

    def test_instagram_ranks_on_median_likes_and_zero_medians_do_not_crash(self):
        rs = rows_at(9, 'instagram', [10] * 8, 'l') + rows_at(10, 'instagram', [2] * 8, 'l')
        sc = windows.score(rs)
        self.assertEqual(list(sc), [9, 10])
        self.assertEqual(sc[9]['score'], 0.25)
        zero = rows_at(9, 'instagram', [0] * 8, 'l') + rows_at(10, 'tiktok', [4] * 8)
        self.assertEqual(list(windows.score(zero)), [10, 9])

    def test_hours_with_too_few_posts_and_forbidden_hours_are_not_scored(self):
        rs = rows_at(12, 'youtube', [900] * 7) + rows_at(23, 'youtube', [900] * 20) \
            + rows_at(6, 'youtube', [50] * 8)
        self.assertEqual(list(windows.score(rs)), [6])
        # afternoon has no scored hour: its hour with the most posts (12, n=7) stands in;
        # evening has only forbidden-hour data: default 19:15
        self.assertEqual(windows.ladder(rs)[3], ['06:15', '12:15', '19:15'])

    def test_view_platforms_average_only_those_with_enough_posts(self):
        rs = (rows_at(8, 'facebook', [100] * 8) + rows_at(8, 'youtube', [1] * 3)
              + rows_at(9, 'facebook', [100] * 8) + rows_at(9, 'youtube', [10] * 8)
              + rows_at(10, 'youtube', [20] * 8))
        sc = windows.score(rs)
        # facebook and youtube both have evidence somewhere, so coverage is out of 2
        self.assertEqual(sc[8]['score'], round(0.75 * 1.0 * (1 / 2) ** 0.5, 3))   # facebook only
        self.assertEqual(sc[9]['score'], round(0.75 * (1.0 + 0.5) / 2, 3))       # both: full weight
        self.assertEqual(sc[8]['view_coverage'], '1/2')
        self.assertEqual(list(sc)[:2], [9, 8])

    def test_one_platform_hour_does_not_outrank_a_three_platform_hour_by_averaging(self):
        rs = (rows_at(8, 'facebook', [100] * 8)                                   # fb best, alone
              + rows_at(12, 'facebook', [60] * 8) + rows_at(12, 'youtube', [60] * 8)
              + rows_at(12, 'tiktok', [60] * 8)                                   # all three at 0.6
              + rows_at(14, 'youtube', [100] * 8) + rows_at(15, 'tiktok', [100] * 8))
        sc = windows.score(rs)
        # without the coverage factor hour 8 scores 0.75 and hour 12 only 0.45
        self.assertEqual(sc[12]['score'], 0.45)
        self.assertEqual(sc[8]['score'], round(0.75 * (1 / 3) ** 0.5, 3))       # 0.433
        self.assertLess(list(sc).index(12), list(sc).index(8))


WAREHOUSE = {
    'ok': True, 'verb': 'social.windows', 'found': True,
    'computedAt': 1_790_000_000_000, 'ageHours': 5.2, 'tz': 'America/Chicago',
    'allowedHours': list(range(6, 23)), 'minSample': 8,
    'platforms': [
        {'platform': 'tiktok', 'metric': 'views',
         'hours': [{'hour': 13, 'n': 9, 'medianViews': 4, 'p75Views': 9, 'medianLikes': 0,
                    'medianEngagement': 0.01, 'score': 4},
                   {'hour': 9, 'n': 12, 'medianViews': 80, 'p75Views': 200, 'medianLikes': 3,
                    'medianEngagement': 0.03, 'score': 80}],
         'ranked': [{'hour': 9, 'score': 80, 'n': 12}], 'insufficient': [],
         'weekdays': [{'weekday': 1, 'n': 5, 'medianViews': 40}]},
        {'platform': 'instagram', 'metric': 'likes',
         'hours': [{'hour': 13, 'n': 10, 'medianViews': 0, 'p75Views': 0, 'medianLikes': 6,
                    'medianEngagement': 0.0, 'score': 6},
                   {'hour': 9, 'n': 10, 'medianViews': 0, 'p75Views': 0, 'medianLikes': 3,
                    'medianEngagement': 0.0, 'score': 3}],
         'ranked': [], 'insufficient': [], 'weekdays': []},
    ],
}


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class WarehouseSource(Offline):
    def setUp(self):
        super().setUp()
        for name, value in (('MIN_N', 8), ('FORBIDDEN', set(WINDOW_FORBIDDEN)),
                            ('VIEW_RELIABLE', {'tiktok', 'youtube', 'facebook'}),
                            ('LIKE_SIGNAL', {'instagram'}),
                            ('WAREHOUSE_URL', 'https://warehouse.test/api/ops/social.windows'),
                            ('WAREHOUSE_MAX_AGE_HOURS', 48), ('RUNG_SIZES', dict(RUNGS_3578))):
            p = patch.object(windows, name, value)
            p.start()
            self.addCleanup(p.stop)
        env = patch.dict('os.environ', {'WARROOM_OPS_KEY': 'test-ops-key'})
        env.start()
        self.addCleanup(env.stop)
        self.live = rows_at(15, 'youtube', [50] * 8)

    def run_rows(self, response=None, error=None):
        seen = []

        def urlopen(req, timeout=None):
            seen.append(req)
            if error:
                raise error
            return FakeResponse(json.dumps(response).encode())

        err = io.StringIO()
        with patch('urllib.request.urlopen', side_effect=urlopen), \
                patch.object(windows, 'live_rows', return_value=self.live), redirect_stderr(err):
            rs = windows.rows()
        return rs, err.getvalue(), seen

    def test_fresh_warehouse_is_used_and_announced(self):
        rs, err, seen = self.run_rows(WAREHOUSE)
        self.assertEqual(rs.source, 'warehouse')
        self.assertIn('WINDOWS SOURCE: warehouse (computed 2026-09-21', err)
        self.assertIn('41 facts', err)
        req = seen[0]
        self.assertEqual(req.get_method(), 'POST')
        self.assertEqual(req.full_url, 'https://warehouse.test/api/ops/social.windows')
        self.assertEqual(req.get_header('X-ops-key'), 'test-ops-key')
        self.assertEqual(json.loads(req.data), {})
        self.assertEqual(rs.stats['tiktok'][9], (12, 80.0))
        # tiktok median views decide 9 over 13 even though instagram likes favour 13
        sc = windows.score(rs)
        self.assertEqual(list(sc), [9, 13])
        self.assertEqual(sc[9]['score'], round(0.75 * 1.0 + 0.25 * 0.5, 3))
        self.assertEqual(windows.ladder(rs)[3], ['09:15', '13:15', '19:15'])

    def assertFallback(self, rs, err, reason):
        self.assertEqual(rs.source, 'live')
        self.assertIn('WINDOWS SOURCE: live Post Bridge fallback (warehouse unavailable:', err)
        self.assertIn(reason, err)
        self.assertEqual(list(windows.score(rs)), [15])

    def test_stale_warehouse_falls_back_loudly(self):
        rs, err, _ = self.run_rows(dict(WAREHOUSE, ageHours=49.5))
        self.assertFallback(rs, err, 'stale: 49.5h old > 48h')

    def test_stale_by_computed_at_when_age_is_missing(self):
        resp = {k: v for k, v in WAREHOUSE.items() if k != 'ageHours'}
        now = datetime.fromtimestamp(WAREHOUSE['computedAt'] / 1000, timezone.utc) + timedelta(hours=72)
        with self.assertRaises(windows.WarehouseUnavailable):
            windows.parse_warehouse(resp, now=now)
        fresh = now - timedelta(hours=60)
        self.assertEqual(windows.parse_warehouse(resp, now=fresh).source, 'warehouse')

    def test_not_found_falls_back(self):
        rs, err, _ = self.run_rows({'ok': True, 'verb': 'social.windows', 'found': False})
        self.assertFallback(rs, err, 'found=false')

    def test_http_error_falls_back(self):
        import urllib.error
        rs, err, _ = self.run_rows(error=urllib.error.HTTPError(
            'https://warehouse.test', 404, 'Not Found', {}, None))
        self.assertFallback(rs, err, 'HTTP 404')

    def test_not_ok_falls_back(self):
        rs, err, _ = self.run_rows({'ok': False, 'error': 'unauthorized'})
        self.assertFallback(rs, err, 'ok=false (unauthorized)')

    def test_unconfigured_url_falls_back_without_a_request(self):
        with patch.object(windows, 'WAREHOUSE_URL', ''):
            rs, err, seen = self.run_rows(WAREHOUSE)
        self.assertEqual(seen, [])
        self.assertFallback(rs, err, 'not configured')

    def test_key_is_never_printed(self):
        _, err, _ = self.run_rows(WAREHOUSE)
        self.assertNotIn('test-ops-key', err)
        _, err, _ = self.run_rows(dict(WAREHOUSE, ageHours=99))
        self.assertNotIn('test-ops-key', err)


class DaypartLadder(Offline):
    """06-11 morning, 12-16 afternoon, 17:00-22:00 evening; best of each, then round-robin."""

    def setUp(self):
        super().setUp()
        for name, value in (('MIN_N', 8), ('FORBIDDEN', set(WINDOW_FORBIDDEN)),
                            ('VIEW_RELIABLE', {'tiktok', 'youtube', 'facebook'}),
                            ('LIKE_SIGNAL', {'instagram'}), ('RUNG_SIZES', dict(RUNGS_3578))):
            p = patch.object(windows, name, value)
            p.start()
            self.addCleanup(p.stop)
        # the old top-8 ladder put every one of these before 4pm
        self.rs = (rows_at(11, 'youtube', [100] * 8) + rows_at(8, 'youtube', [95] * 8)
                   + rows_at(13, 'youtube', [90] * 8) + rows_at(12, 'youtube', [85] * 8)
                   + rows_at(10, 'youtube', [80] * 8) + rows_at(15, 'youtube', [75] * 8)
                   + rows_at(14, 'youtube', [70] * 8) + rows_at(9, 'youtube', [65] * 8)
                   + rows_at(19, 'youtube', [20] * 8) + rows_at(21, 'youtube', [15] * 8)
                   + rows_at(18, 'youtube', [10] * 8))

    def test_rung_three_is_one_slot_per_daypart(self):
        lad = windows.ladder(self.rs)
        self.assertEqual(lad[3], ['11:15', '13:15', '19:15'])
        self.assertEqual([windows.daypart_of(s) for s in lad[3]], ['morning', 'afternoon', 'evening'])

    def test_rungs_five_seven_eight_round_robin(self):
        lad = windows.ladder(self.rs)
        self.assertEqual(lad[5], ['11:15', '13:15', '19:15', '08:15', '12:15'])
        self.assertEqual(lad[7], ['11:15', '13:15', '19:15', '08:15', '12:15', '21:15', '10:15'])
        self.assertEqual(lad[8], ['11:15', '13:15', '19:15', '08:15', '12:15', '21:15', '10:15', '15:15'])

    def test_an_exhausted_daypart_is_skipped_by_the_round_robin(self):
        rs = rows_at(11, 'youtube', [100] * 8) + rows_at(8, 'youtube', [90] * 8) \
            + rows_at(9, 'youtube', [80] * 8) + rows_at(13, 'youtube', [70] * 8)
        self.assertEqual(windows.ladder(rs)[5], ['11:15', '13:15', '19:15', '08:15', '09:15'])

    def test_no_slot_before_0600_or_after_2200_and_hour_22_is_exactly_2200(self):
        rs = self.rs + rows_at(22, 'youtube', [9999] * 30) + rows_at(23, 'youtube', [9999] * 30) \
            + rows_at(5, 'youtube', [9999] * 30)
        order = windows.ladder_order(rs)
        self.assertTrue(order)
        # the hour-22 score is the best evening hour, and it maps to exactly 22:00
        self.assertEqual(windows.ladder(rs)[3], ['11:15', '13:15', '22:00'])
        for s in order:
            self.assertTrue('06:00' <= s <= '22:00', s)
            self.assertTrue(s.endswith(':15') or s == '22:00', s)
        self.assertNotIn('22:15', order)
        # even when a scorer hands back hours outside the window
        with patch.object(windows, 'score', return_value=dict.fromkeys([22, 23, 5, 21, 6, 12], {})):
            got = windows.ladder_order([])
            self.assertIn('22:00', got)
            for s in got:
                self.assertTrue('06:00' <= s <= '22:00', s)

    def test_a_daypart_with_no_evidence_still_gets_a_slot(self):
        rs = rows_at(8, 'youtube', [100] * 8) + rows_at(9, 'youtube', [50] * 8)
        lad = windows.ladder(rs)
        self.assertEqual(lad[3], ['08:15', '13:15', '19:15'])     # 13 and 19 are the defaults
        parts = windows.daypart_hours(rs)
        self.assertEqual(parts, {'morning': [8, 9], 'afternoon': [13], 'evening': [19]})

    def test_thin_evidence_beats_the_default(self):
        rs = rows_at(8, 'youtube', [100] * 8) + rows_at(20, 'tiktok', [3] * 2) \
            + rows_at(17, 'tiktok', [3] * 5)
        self.assertEqual(windows.daypart_hours(rs)['evening'], [17])

    def test_lint_allowed_set_is_the_full_daypart_ladder(self):
        with patch.object(windows, 'rows', return_value=self.rs):
            allowed = create_batch._allowed_ct()
        self.assertEqual(allowed, set(windows.ladder_order(self.rs)))
        self.assertIn('19:15', allowed)
        self.assertNotIn('22:15', allowed)


class LintWindow(Offline):
    """The lint refuses any start outside 06:00-22:00 CT inclusive, whatever the allowed set says."""

    def setUp(self):
        super().setUp()
        for name, value in (('scoped_channels', lambda: {1: 'ch1', 2: 'ch2'}),
                            ('_allowed_ct', lambda preferred=(): {'05:45', '06:00', '22:00', '22:15'}),
                            ('MIN_GAP_MIN', 90), ('MIN_STAGGER_MIN', 10)):
            p = patch.object(create_batch, name, value)
            p.start()
            self.addCleanup(p.stop)

    def slot_errors(self, hhmm):
        utc = datetime.combine(DAY, datetime.strptime(hhmm, '%H:%M').time(),
                               engine.TZ).astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        post = {'slug': 's', 'scheduled_at': utc, 'captions': {'1': 'one', '2': 'two'},
                'youtube_title': 't', 'gmb_media_id': ''}
        return [e for e in create_batch.lint({'posts': [post]}, defaultdict(list)) if 'slot' in e]

    def test_2200_is_legal(self):
        self.assertEqual(self.slot_errors('22:00'), [])

    def test_0600_is_legal(self):
        self.assertEqual(self.slot_errors('06:00'), [])

    def test_2215_is_refused(self):
        errs = self.slot_errors('22:15')
        self.assertEqual(len(errs), 1)
        self.assertIn('outside the posting window 06:00-22:00', errs[0])

    def test_0545_is_refused(self):
        errs = self.slot_errors('05:45')
        self.assertEqual(len(errs), 1)
        self.assertIn('outside the posting window', errs[0])



class PreferredSlots(Offline):
    def test_preferred_2200_is_accepted_and_2215_or_0545_refused(self):
        with patch.object(windows, 'rows', return_value=[]), \
                patch.object(windows, 'score', return_value=dict.fromkeys([9, 13, 19], {})):
            self.assertIn('22:00', create_batch._allowed_ct(('22:00',)))
            self.assertIn('06:00', create_batch._allowed_ct(('06:00',)))
            for bad in ('22:15', '05:45'):
                with self.assertRaises(ValueError):
                    create_batch._allowed_ct((bad,))


if __name__ == '__main__':
    unittest.main()
