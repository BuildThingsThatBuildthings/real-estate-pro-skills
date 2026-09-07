import importlib.util
import json
import tempfile
import subprocess
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('delivery', Path(__file__).parents[1] / 'scripts/verify_drive_delivery.py')
delivery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(delivery)


class DeliveryChecks(unittest.TestCase):
    def test_total_deadline_preserves_incomplete_receipt(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); local = root / 'upload'; local.mkdir()
            (local / 'clip.mp4').write_bytes(b'fixture')
            receipt = root / 'receipt.json'
            with patch.object(delivery.subprocess, 'run', side_effect=subprocess.TimeoutExpired('rclone', 180, stderr=b'DNS unavailable')) as call:
                self.assertEqual(delivery.verify(local, 'gdrive:', 'parent', 'review', receipt), 124)
            record = json.loads(receipt.read_text())
            self.assertFalse(record['downloaded_bytes_match'])
            self.assertTrue(record['timed_out'])
            self.assertEqual(call.call_args.kwargs['timeout'], 180)

    def test_transfer_failure_cannot_be_reported_as_verified(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); local = root / 'upload'; local.mkdir()
            (local / 'clip.mp4').write_bytes(b'fixture')
            receipt = root / 'receipt.json'
            with patch.object(delivery.subprocess, 'run', return_value=SimpleNamespace(returncode=1, stderr='missing clip')) as call:
                self.assertEqual(delivery.verify(local, 'gdrive:', 'parent', 'review', receipt), 1)
            self.assertFalse(json.loads(receipt.read_text())['downloaded_bytes_match'])
            self.assertIn('--download', call.call_args.args[0])
            self.assertIn('--one-way', call.call_args.args[0])

    def test_receipt_cannot_change_checked_directory(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); (root / 'asset.png').write_bytes(b'fixture')
            with self.assertRaises(ValueError):
                delivery.verify(root, 'gdrive:', 'parent', 'review', root / 'receipt.json')


if __name__ == '__main__':
    unittest.main()
