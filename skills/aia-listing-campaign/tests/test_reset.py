import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('reset', Path(__file__).parents[1]/'scripts/reset_campaign.py')
reset = importlib.util.module_from_spec(spec); spec.loader.exec_module(reset)


class ResetTests(unittest.TestCase):
    def plan(self):
        return {'remote':'drive:', 'parent_id':'explicit-parent', 'authorization':'User requested all generated outputs removed',
                'targets':[{'id':'old-id','path':'Rejected campaign','directory':True}], 'require_empty':True}

    def test_never_targets_parent_and_reads_back(self):
        calls=[]; state=[{'ID':'old-id','Path':'Rejected campaign','IsDir':True}]
        def fake(cmd):
            calls.append(cmd)
            if cmd[1]=='lsjson': return json.dumps(state)
            state.clear(); return ''
        with tempfile.TemporaryDirectory() as d:
            result=reset.execute(self.plan(), Path(d)/'receipt.json', fake)
        self.assertTrue(result['complete'])
        mutations=[c for c in calls if c[1]!='lsjson']
        self.assertEqual(mutations[0][2], 'drive:Rejected campaign')
        self.assertIn('--drive-use-trash=true', mutations[0])

    def test_replaced_target_refused_before_deletion(self):
        def fake(cmd):
            self.assertEqual(cmd[1], 'lsjson')
            return json.dumps([{'ID':'new-id','Path':'Rejected campaign','IsDir':True}])
        with tempfile.TemporaryDirectory() as d, self.assertRaises(ValueError):
            reset.execute(self.plan(), Path(d)/'receipt.json', fake)

    def test_requested_removal_is_not_verified_removal(self):
        def fake(cmd):
            return json.dumps([{'ID':'old-id','Path':'Rejected campaign','IsDir':True}]) if cmd[1]=='lsjson' else ''
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'receipt.json'
            with self.assertRaises(RuntimeError): reset.execute(self.plan(),path,fake)
            self.assertFalse(json.loads(path.read_text())['complete'])

    def test_missing_authority_and_root_paths_refused(self):
        plan=self.plan(); plan['authorization']=''
        with self.assertRaises(ValueError): reset.validate_targets(plan)
        plan=self.plan(); plan['targets'][0]['path']='../originals'
        with self.assertRaises(ValueError): reset.validate_targets(plan)


if __name__=='__main__': unittest.main()
