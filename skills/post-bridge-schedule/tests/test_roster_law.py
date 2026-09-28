"""AIA/BT2 roster law in the create_batch lint (Ryan, 2026-09-27).

Every AIA/BT2 post targets all nine roster accounts, each with a non-empty caption,
all nine pairwise distinct, plus a YouTube title. The only exception is a
LinkedIn-only post (72370 / 80927). Offline: every network path is blocked.
"""
import sys
import unittest
from collections import defaultdict
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parent.parent / 'scripts'
sys.path.insert(0, str(SCRIPTS))
import create_batch  # noqa: E402

ROSTER = [72366, 72367, 72370, 75843, 75846, 75850, 75841, 75844, 75848]
CONTEXT = {a: f'acct{a}' for a in ROSTER + [80927]}
# 11:15 CDT on 2026-10-07
WHEN = '2026-10-07T16:15:00Z'


def full_post(**over):
    post = {'slug': 's', 'scheduled_at': WHEN, 'youtube_title': 'A real title',
            'gmb_media_id': '', 'captions': {str(a): f'caption number {a}' for a in ROSTER}}
    post.update(over)
    return post


class RosterLaw(unittest.TestCase):
    def setUp(self):
        for target in ('urllib.request.urlopen', 'pb.req', 'pb.paged', 'subprocess.run'):
            p = patch(target, side_effect=AssertionError(f'{target}: network forbidden in tests'))
            p.start()
            self.addCleanup(p.stop)
        for name, value in (('scoped_channels', lambda: dict(CONTEXT)),
                            ('_allowed_ct', lambda preferred=(): {'11:15'}),
                            ('MIN_GAP_MIN', 45), ('MIN_STAGGER_MIN', 10)):
            p = patch.object(create_batch, name, value)
            p.start()
            self.addCleanup(p.stop)

    def roster_errs(self, post):
        errs = create_batch.lint({'posts': [post]}, defaultdict(list))
        # gmb_media_id is blank on purpose (no media lookups offline); ignore that check
        return [e for e in errs if 'gmb_media_id' not in e]

    def test_full_nine_account_post_passes(self):
        self.assertEqual(self.roster_errs(full_post()), [])

    def test_missing_one_roster_account_fails(self):
        post = full_post()
        del post['captions']['75844']
        errs = self.roster_errs(post)
        self.assertTrue(any('all 9 roster accounts' in e and '75844' in e for e in errs), errs)

    def test_three_account_subset_fails_even_if_context_is_three(self):
        with patch.object(create_batch, 'scoped_channels', lambda: {72366: 'a', 72367: 'b', 75843: 'c'}):
            post = full_post(captions={'72366': 'one', '72367': 'two', '75843': 'three'})
            errs = self.roster_errs(post)
        self.assertTrue(any('all 9 roster accounts' in e for e in errs), errs)
        self.assertTrue(any('verified posting context is missing' in e for e in errs), errs)

    def test_non_roster_account_alongside_roster_fails(self):
        post = full_post()
        post['captions']['80927'] = 'a tenth caption'
        errs = self.roster_errs(post)
        self.assertTrue(any('non-roster accounts [80927]' in e for e in errs), errs)

    def test_empty_caption_fails(self):
        post = full_post()
        post['captions']['75850'] = '   '
        errs = self.roster_errs(post)
        self.assertTrue(any('empty caption for roster accounts [75850]' in e for e in errs), errs)

    def test_duplicate_caption_fails_even_with_case_and_whitespace_changes(self):
        post = full_post()
        post['captions']['75841'] = 'Caption  number 72366 '
        errs = self.roster_errs(post)
        self.assertTrue(any('75841 duplicates 72366' in e for e in errs), errs)

    def test_missing_youtube_title_fails(self):
        for title in ('', '   ', None):
            errs = self.roster_errs(full_post(youtube_title=title))
            self.assertTrue(any('needs a YouTube title' in e for e in errs), (title, errs))

    def test_linkedin_only_post_passes_without_youtube_title_or_gbp_image(self):
        for caps in ({'72370': 'li aia'}, {'80927': 'li ryan'}, {'72370': 'li aia', '80927': 'li ryan'}):
            post = full_post(captions=caps, youtube_title='', gmb_media_id='')
            self.assertEqual(create_batch.lint({'posts': [post]}, defaultdict(list)), [], caps)

    def test_linkedin_only_duplicate_or_empty_captions_fail(self):
        post = full_post(captions={'72370': 'same', '80927': 'SAME'}, youtube_title='')
        self.assertTrue(any('not all distinct' in e for e in self.roster_errs(post)))
        post = full_post(captions={'80927': ''}, youtube_title='')
        self.assertTrue(any('empty caption' in e for e in self.roster_errs(post)))

    def test_linkedin_plus_one_other_account_is_not_the_exception(self):
        post = full_post(captions={'72370': 'li', '72367': 'x'}, youtube_title='')
        errs = self.roster_errs(post)
        self.assertTrue(any('all 9 roster accounts' in e for e in errs), errs)

    def test_build_fans_out_to_exactly_the_nine_roster_accounts(self):
        payload = create_batch.build(full_post(video_media_id='v', gmb_media_id='g'))
        self.assertEqual(sorted(payload['social_accounts']), sorted(ROSTER))
        caps = [c['caption'] for c in payload['account_configurations']['account_configurations']]
        self.assertEqual(len(set(caps)), 9)

    def test_build_linkedin_only_targets_only_linkedin(self):
        payload = create_batch.build(full_post(captions={'72370': 'li aia', '80927': 'li ryan'},
                                               video_media_id='v'))
        self.assertEqual(sorted(payload['social_accounts']), [72370, 80927])
        self.assertNotIn('platform_configurations', payload)

    def test_non_aia_profile_keeps_the_verified_roster_rule(self):
        with patch.object(create_batch, 'scoped_channels', lambda: {1: 'a', 2: 'b'}):
            ok = full_post(captions={'1': 'one', '2': 'two'})
            self.assertEqual(self.roster_errs(ok), [])
            bad = full_post(captions={'1': 'one'})
            self.assertTrue(any('differ from verified client roster' in e for e in self.roster_errs(bad)))


if __name__ == '__main__':
    unittest.main()
