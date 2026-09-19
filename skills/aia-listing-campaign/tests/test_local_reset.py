import importlib.util
from pathlib import Path
import tempfile
import unittest

SCRIPT=Path(__file__).resolve().parents[1]/'scripts/reset_campaign.py'
spec=importlib.util.spec_from_file_location('local_reset',SCRIPT);reset=importlib.util.module_from_spec(spec);spec.loader.exec_module(reset)

class LocalResetTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.parent=Path(self.temp.name);self.old=self.parent/'old';self.old.mkdir();(self.old/'photo.jpg').write_bytes(b'original');(self.old/'failed.mp4').write_bytes(b'failed')
        self.root=self.parent/'fresh';self.receipt=self.root/'working/reset.json'
        self.plan={'authorization':'Delete all old generated work; preserve originals','allowed_parent':str(self.parent),'run_root':str(self.root),'targets':[str(self.old)],'trash_root':str(self.parent/'Trash'),'preserve':[{'source':str(self.old/'photo.jpg'),'destination':'source/photo.jpg','kind':'original','basis':'Supplied original fixture'}]}
    def tearDown(self):self.temp.cleanup()
    def test_preserves_bytes_before_recoverable_removal(self):
        result=reset.execute_local(self.plan,self.receipt)
        self.assertTrue(result['complete']);self.assertFalse(self.old.exists());self.assertEqual((self.root/'source/photo.jpg').read_bytes(),b'original')
        self.assertEqual((Path(result['removed'][0]['trash_path'])/'failed.mp4').read_bytes(),b'failed')
    def test_preservation_conflict_prevents_removal(self):
        (self.root/'source').mkdir(parents=True);(self.root/'source/photo.jpg').write_bytes(b'wrong')
        with self.assertRaises(ValueError):reset.execute_local(self.plan,self.receipt)
        self.assertTrue(self.old.exists())
    def test_skill_repository_never_target(self):
        (self.old/'skills').mkdir()
        with self.assertRaises(ValueError):reset.execute_local(self.plan,self.receipt)
        self.assertTrue(self.old.exists())

if __name__=='__main__':unittest.main()
