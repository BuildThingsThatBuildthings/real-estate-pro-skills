import importlib.util,json,sys,tempfile,unittest
from pathlib import Path
s=importlib.util.spec_from_file_location('workflow',Path(__file__).parents[1]/'scripts/run_workflow.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class WorkflowTests(unittest.TestCase):
 def test_failed_video_does_not_stop_copy_and_never_claims_acceptance(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'workflow.json';p.write_text(json.dumps({'root':d,'tasks':[
    {'id':'video','skill':'aia-listing-campaign','command':[sys.executable,'-c','raise SystemExit(1)']},
    {'id':'video-package','skill':'aia-listing-campaign','depends_on':['video'],'command':[sys.executable,'-c','raise SystemExit(99)']},
    {'id':'copy','skill':'aia-listing-machine','command':[sys.executable,'-c',"from pathlib import Path;Path('copy.md').write_text('draft')"],'outputs':['copy.md']},
    {'id':'review','skill':'aia-listing-campaign','depends_on':['copy'],'manual_reason':'Full review required'}]}))
   f=m.execute(p);self.assertEqual([t.get('status','pending') for t in f['tasks']],['failed','pending','executed','pending']);self.assertIn('review',f['execution_summary']['unfinished'])
 def test_zero_exit_without_artifact_fails(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'w.json';p.write_text(json.dumps({'root':d,'tasks':[{'id':'render','skill':'aia-listing-campaign','command':[sys.executable,'-c','pass'],'outputs':['missing.mp4']}]}));self.assertEqual(m.execute(p)['tasks'][0]['status'],'failed')
 def test_unknown_dependency_refused(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'w.json';p.write_text(json.dumps({'root':d,'tasks':[{'id':'render','skill':'aia-listing-campaign','depends_on':['missing']}]}))
   with self.assertRaises(ValueError):m.execute(p)
if __name__=='__main__':unittest.main()
