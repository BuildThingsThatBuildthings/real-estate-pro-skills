import json, os, subprocess, sys, tempfile, unittest
from pathlib import Path
SCRIPT=Path(__file__).resolve().parents[1]/"scripts/drive_sync.py"
class DriveOnlyProfileTests(unittest.TestCase):
    def test_media_client_needs_no_social_channels(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp,"clients.json").write_text(json.dumps({"clients":{"fictional-harbor":{"name":"Fictional Harbor","posting_enabled":False,"drive":{"waiting_folder_id":"fixture-waiting"}}}}))
            p=subprocess.run([sys.executable,str(SCRIPT),"clients"],env={**os.environ,"RE_SKILLS_CONFIG_DIR":tmp},capture_output=True,text=True)
            self.assertEqual(p.returncode,0,p.stderr)
            self.assertIn("fictional-harbor",p.stdout)
            self.assertNotIn("channels.json",p.stderr)
    def test_missing_explicit_profile_never_falls_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=subprocess.run([sys.executable,str(SCRIPT),"clients"],env={**os.environ,"RE_SKILLS_CONFIG_DIR":tmp},capture_output=True,text=True)
            self.assertNotEqual(p.returncode,0)
            self.assertIn(str(Path(tmp,"clients.json")),p.stderr)
if __name__=="__main__":unittest.main()
