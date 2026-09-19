import importlib.util
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from pathlib import Path
from PIL import Image
from pypdf import PdfWriter

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
from delivery_gate import validate_delivery


class DeliveryGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
    def tearDown(self):
        self.temp.cleanup()
    def file(self, name, data=b'not media'):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path
    def test_valid_media(self):
        Image.new('RGB', (20, 20)).save(self.file('03 Graphics/cover.png'))
        self.assertEqual(len(validate_delivery(self.root)), 1)
    def test_technical_sidecars_rejected_everywhere(self):
        for ext in ('json', 'srt', 'log', 'vtt', 'csv', 'py'):
            with self.subTest(ext=ext):
                path = self.file(f'Documents/metadata.{ext}')
                with self.assertRaises(ValueError):
                    validate_delivery(self.root, ['Documents'], [f'Documents/metadata.{ext}'])
                path.unlink()
    def test_useful_pdf_and_recording_copy_allowed_only_when_identified(self):
        pdf = self.root / 'Documents' / 'Recording Kit.pdf'
        pdf.parent.mkdir()
        writer = PdfWriter(); writer.add_blank_page(width=100, height=100)
        writer.write(pdf)
        name = 'Documents/Recording Kit.pdf'
        for folders, docs in [([], [name]), (['Documents'], []), ([], [])]:
            with self.assertRaises(ValueError): validate_delivery(self.root, folders, docs)
        self.assertEqual(len(validate_delivery(self.root, ['Documents'], [name])), 1)
        self.file('Documents/Captions.md', b'# Listing captions\nCome take a look.')
        self.assertEqual(len(validate_delivery(self.root, ['Documents'], [name, 'Documents/Captions.md'])), 2)
    def test_docs_cannot_enter_media_folder(self):
        self.file('01 Property Videos/Recording guide.md', b'Useful spoken copy')
        with self.assertRaisesRegex(ValueError, 'Media folders'):
            validate_delivery(self.root, ['01 Property Videos'], ['01 Property Videos/Recording guide.md'])
    def test_unknown_files_and_misleading_extensions(self):
        for name in ('unknown.bin', 'fake.png', 'fake.mp4', 'Documents/fake.pdf'):
            with self.subTest(name=name):
                path = self.file(name)
                with self.assertRaises(ValueError):
                    validate_delivery(self.root, ['Documents'], ['Documents/fake.pdf'] if name.endswith('.pdf') else [])
                path.unlink()
        path = self.file('fake.jpg'); Image.new('RGB', (10, 10)).save(path, 'PNG')
        with self.assertRaises(ValueError): validate_delivery(self.root)
    def test_hidden_partial_missing_and_renamed_metadata(self):
        for name, data in [('.receipt', b'x'), ('tour.partial.mp4', b'x'), ('Documents/data.txt', b'{"technical": true}')]:
            path = self.file(name, data)
            with self.assertRaises(ValueError): validate_delivery(self.root, ['Documents'], [name] if name.startswith('Documents') else [])
            path.unlink()
        with self.assertRaises(ValueError): validate_delivery(self.root, ['Documents'], ['Documents/missing.pdf'])
    @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'FFmpeg required')
    def test_real_mp4_decodes(self):
        path = self.root / 'tour.mp4'
        subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=c=red:s=32x32:d=0.2', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(path)], check=True)
        self.assertEqual(validate_delivery(self.root), [path])
    def test_delivery_refuses_before_any_transfer(self):
        with patch.dict(sys.modules, {'config': SimpleNamespace(load=lambda name: {})}):
            import drive_sync
        self.file('run.json', b'{}')
        args = SimpleNamespace(client='fixture', src=str(self.root), yes=True, label='Listing', document_folders=[], documents=[])
        with patch.object(drive_sync, 'client', return_value=({}, {'drive': {'waiting_folder_id': 'test'}})), patch.object(drive_sync.subprocess, 'run') as transfer:
            with self.assertRaises(SystemExit): drive_sync.cmd_deliver(args)
            transfer.assert_not_called()

    def test_export_receipt_stays_outside_media(self):
        asset = self.root / 'base.jpg'; Image.new('RGB', (1080, 1350)).save(asset)
        asset.with_suffix('.composite.json').write_text('{"channel":"ig"}')
        output = self.root / 'output'
        result = subprocess.run([sys.executable, str(SCRIPTS / 'export.py'), str(asset), '--agent-slug', 'fixture', '--type', 'listing', '--descriptor', 'fixture', '--channels', 'ig', '--outdir', str(output)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(all(p.suffix == '.jpg' for p in output.iterdir()))
        self.assertEqual(len(list((self.root / 'working/export-receipts').glob('*.json'))), 1)

    def test_nested_exports_cannot_leak_receipts_into_public_parent(self):
        asset = self.root/'base.jpg'; Image.new('RGB', (1080,1350)).save(asset)
        asset.with_suffix('.composite.json').write_text('{"channel":"ig"}')
        output = self.root/'output/Graphics/Feed'
        command = [sys.executable, str(SCRIPTS/'export.py'), str(asset), '--agent-slug', 'fixture', '--type', 'listing', '--descriptor', 'fixture', '--channels', 'ig', '--outdir', str(output)]
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertFalse(list((self.root/'output').rglob('*.json')))
        result = subprocess.run(command+['--metadata-dir',str(self.root/'output/private')],capture_output=True,text=True)
        self.assertEqual(result.returncode,1)

if __name__ == '__main__': unittest.main()
