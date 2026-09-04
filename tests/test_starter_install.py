import importlib.util, json, tempfile, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('install_starter',ROOT/'scripts/install_starter.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Installation(unittest.TestCase):
 def test_dry_run_does_not_write(self):
  with tempfile.TemporaryDirectory() as tmp:
   dest=Path(tmp)/'skills';r=m.install(ROOT,dest);self.assertFalse(dest.exists());self.assertEqual(len(r['skills']),4)
 def test_install_and_repeat_readback(self):
  with tempfile.TemporaryDirectory() as tmp:
   dest=Path(tmp)/'skills';r=m.install(ROOT,dest,True);self.assertEqual(r['verification'],'files-read-back');r=m.install(ROOT,dest,True);self.assertTrue(all(o['state']=='unchanged' for o in r['skills']))
 def test_conflict_prevents_all_changes(self):
  with tempfile.TemporaryDirectory() as tmp:
   dest=Path(tmp)/'skills';d=dest/'aia-content';d.mkdir(parents=True);(d/'SKILL.md').write_text('my edits')
   with self.assertRaises(ValueError):m.install(ROOT,dest,True)
   self.assertEqual(list(dest.iterdir()),[d]);self.assertEqual((d/'SKILL.md').read_text(),'my edits')
 def test_symlink_conflict(self):
  with tempfile.TemporaryDirectory() as tmp:
   dest=Path(tmp)/'skills';dest.mkdir();(dest/'aia-content').symlink_to(Path(tmp)/'elsewhere')
   with self.assertRaises(ValueError):m.install(ROOT,dest,True)
 def test_package_content_and_business_interview(self):
  manifest=json.loads((ROOT/'starter/manifest.json').read_text());self.assertEqual(len(manifest['skills']),4)
  for skill in manifest['skills']:
   text=(ROOT/skill['path']/'SKILL.md').read_text();self.assertIn('name: '+skill['name'],text);self.assertIn(manifest['authority']['masterSha256'],text)
  prompt=(ROOT/'INSTALL-PROMPT.md').read_text()
  for term in ['business email','calendar','time zone','CRM','verified/pending/unavailable','MCP is not required for v1'] :self.assertIn(term,prompt)
if __name__=='__main__':unittest.main()
