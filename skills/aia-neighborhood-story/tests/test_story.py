import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location('story', Path(__file__).resolve().parents[1] / 'scripts/validate_story.py')
STORY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(STORY)


class StoryValidation(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        asset = self.root / 'original.mp4'
        asset.write_bytes(b'original fixture, not a rendered film')
        self.plan = {
            'run_id': 'new-run',
            'narrative': {k: 'A specific editorial choice' for k in ('opening', 'discovery', 'payoff', 'place_specificity', 'sound_direction')},
            'locations': {'home': {'name': 'Fictional home'}, 'park': {'name': 'Fictional park'}},
            'claims': {'park-detail': {'text': 'A fixture detail', 'source': 'fixture:original-record', 'checked_at': '2026-09-07', 'location_id': 'park'}},
            'media': {k: {'path': str(asset), 'rights_basis': 'fixture owned', 'source': 'fixture:original', 'sha256': hashlib.sha256(asset.read_bytes()).hexdigest(), 'origin': 'original', 'location_id': k} for k in ('home', 'park')},
            'films': {'vertical': 'vertical.json', 'horizontal': 'horizontal.json'},
        }
        self.configs = {}
        for orientation in self.plan['films']:
            self.configs[orientation] = {
                'run_id': 'new-run', 'kind': 'neighborhood', 'composition_id': orientation,
                'output': str(self.root / f'{orientation}.mp4'),
                'width': 1080 if orientation == 'vertical' else 1920,
                'height': 1920 if orientation == 'vertical' else 1080,
                'narration': {'path': 'voice.wav', 'rights_basis': 'owned'},
                'captions': [{'start': 0, 'end': 3, 'text': 'Fixture'}],
                'shots': [{'path': str(asset), 'media_id': loc, 'location_id': loc,
                           'source_sha256': self.plan['media'][loc]['sha256'], 'origin': 'original',
                           'claim_ids': ['park-detail'] if loc == 'park' else [],
                           'framing_note': f'{orientation} intentional frame', 'narrative_beat': beat}
                          for loc, beat in [('home', 'opening'), ('park', 'discovery'), ('home', 'payoff')]],
            }

    def check(self):
        for name, config in self.configs.items():
            (self.root / f'{name}.json').write_text(json.dumps(config))
        return STORY.validate(self.plan, self.root)[0]

    def test_valid_structure_does_not_claim_finished_film(self):
        self.assertEqual(self.check(), [])
        self.assertFalse((self.root / 'vertical.mp4').exists())

    def test_old_generated_asset_rejected(self):
        self.plan['media']['park'].update(origin='generated', run_id='old-run')
        self.assertTrue(any('another run' in e for e in self.check()))

    def test_missing_film_and_wrong_dimensions_rejected(self):
        del self.plan['films']['horizontal']
        self.configs['vertical']['width'] = 1920
        self.assertTrue(any('Both vertical' in e for e in self.check()))
        self.assertTrue(any('dimensions' in e for e in self.check()))

    def test_wrong_location_rejected(self):
        self.configs['vertical']['shots'][1]['location_id'] = 'home'
        self.assertTrue(any('another location' in e for e in self.check()))

    def test_forged_source_identity_rejected(self):
        self.configs['vertical']['shots'][1]['origin'] = 'generated'
        self.assertTrue(any('source identity' in e for e in self.check()))

    def test_future_project_without_disclosure_rejected(self):
        self.plan['claims']['park-detail'].update(development_status='approved')
        errors = self.check()
        self.assertTrue(any('proximity and relevance' in e for e in errors))
        self.assertTrue(any('screen label' in e for e in errors))
        self.assertTrue(any('also be spoken' in e for e in errors))

    def test_changed_source_and_missing_payoff_rejected(self):
        Path(self.plan['media']['park']['path']).write_bytes(b'changed')
        self.configs['vertical']['shots'].pop()
        errors = self.check()
        self.assertTrue(any('hash mismatch' in e for e in errors))
        self.assertTrue(any('final payoff' in e for e in errors))


if __name__ == '__main__':
    unittest.main()
