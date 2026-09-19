import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
from select_handoff import selection
from validate_campaign import FULL_INVENTORY


class ExactSelectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.items = []
        for identifier, kind in FULL_INVENTORY.items():
            suffix = '.mp4' if kind == 'video' else '.pdf' if kind == 'document' else '.png'
            source = self.root / (identifier + suffix)
            source.write_bytes(b'fixture; media decode belongs to delivery gate')
            self.items.append({'id': identifier, 'source': source.name,
                               'destination': ('Documents/' if kind == 'document' else 'Media/') + source.name,
                               'producer_task': 'fixture-production', 'sha256': 'fixture'})

    def tearDown(self):
        self.temp.cleanup()

    def test_exact_inventory_is_selected(self):
        self.assertEqual(len(selection({'items': self.items}, self.root)), 60)

    def test_missing_flagship_is_rejected(self):
        with self.assertRaises(ValueError):
            selection({'items': [x for x in self.items if x['id'] != 'property-film-horizontal']}, self.root)

    def test_technical_destination_is_rejected(self):
        self.items[0]['destination'] = 'Media/property.review.json'
        with self.assertRaises(ValueError):
            selection({'items': self.items}, self.root)

    def test_path_escape_is_rejected(self):
        self.items[0]['destination'] = '../outside.mp4'
        with self.assertRaises(ValueError):
            selection({'items': self.items}, self.root)

    def test_missing_producer_is_rejected(self):
        self.items[0].pop('producer_task')
        with self.assertRaises(ValueError):
            selection({'items': self.items}, self.root)


if __name__ == '__main__':
    unittest.main()
