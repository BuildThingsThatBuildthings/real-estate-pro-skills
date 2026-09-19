"""Synthetic evidence fixtures test validation, not a real provider job."""
import importlib.util
import sys
import json
import os
from pathlib import Path
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).parents[1]/'scripts'))
SCRIPT=Path(__file__).resolve().parents[1]/'scripts/external_operation.py'
spec=importlib.util.spec_from_file_location('external_operation',SCRIPT)
bridge=importlib.util.module_from_spec(spec);spec.loader.exec_module(bridge)

class ExternalOperationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);(self.root/'working').mkdir()
        self.source=self.root/'original.txt';self.source.write_text('Original fixture source')
        self.output=self.root/'fresh.txt';self.record=self.root/'working/operation.json';self.evidence=self.root/'working/evidence.json'
        self.spec={'scope':'test','run_id':'fresh','task_id':'author','skill':'aia-listing-campaign','operation':'agent_authoring','root':str(self.root),'inputs':[{'path':str(self.source),'sha256':bridge.digest(self.source),'origin':'original','source_id':'fixture'}],'outputs':['fresh.txt']}
    def tearDown(self):self.temp.cleanup()
    def begin(self):return bridge.begin(self.spec,self.record)
    def evidence_for(self,provider=False):
        self.output.write_text('Newly authored fictional output')
        raw=self.root/'working/tool-response.txt';raw.write_text('Synthetic test fixture, not a real generation claim')
        moment=bridge.now()
        evidence={'run_id':'fresh','task_id':'author','tool':'fixture','action_id':'fixture-action','recorded_at':moment,'inspection':{'reviewer':'unit-test','reviewed_at':moment,'outcome':'accepted'},'source_hashes':{str(self.source.resolve()):bridge.digest(self.source)},'outputs':[{'path':'fresh.txt','sha256':bridge.digest(self.output)}],'evidence_files':[str(raw)]}
        if provider:evidence['provider']={'job_id':'fixture-job','submitted_at':moment,'completed_at':moment}
        self.evidence.write_text(json.dumps(evidence));return evidence
    def test_begin_and_complete_are_distinct_and_revalidated(self):
        self.assertEqual(self.begin()['status'],'awaiting_external_action');self.evidence_for()
        receipt=bridge.complete(self.record,self.evidence)
        self.assertEqual(receipt['status'],'externally_verified');self.assertEqual(bridge.verify(self.record,'fresh')['hashes'],{'fresh.txt':bridge.digest(self.output)})
        self.output.write_text('Changed after verification')
        with self.assertRaises(ValueError):bridge.verify(self.record,'fresh')
    def test_begin_rejects_existing_output(self):
        self.output.write_text('Old generation')
        with self.assertRaisesRegex(ValueError,'already exists'):self.begin()
    def test_complete_rejects_changed_source(self):
        self.begin();self.evidence_for();self.source.write_text('Changed')
        with self.assertRaisesRegex(ValueError,'changed'):bridge.complete(self.record,self.evidence)
    def test_complete_rejects_wrong_run(self):
        self.begin();evidence=self.evidence_for();evidence['run_id']='old';self.evidence.write_text(json.dumps(evidence))
        with self.assertRaisesRegex(ValueError,'another run'):bridge.complete(self.record,self.evidence)
    def test_provider_requires_job_and_concrete_evidence(self):
        self.spec['operation']='provider_generation';self.begin();self.evidence_for()
        with self.assertRaisesRegex(ValueError,'job ID'):bridge.complete(self.record,self.evidence)
        evidence=self.evidence_for(provider=True);evidence['evidence_files']=[];self.evidence.write_text(json.dumps(evidence))
        with self.assertRaisesRegex(ValueError,'concrete'):bridge.complete(self.record,self.evidence)
    def test_rejects_stale_artifact_and_changed_evidence(self):
        self.begin();self.evidence_for();os.utime(self.output,(1,1))
        with self.assertRaisesRegex(ValueError,'stale'):bridge.complete(self.record,self.evidence)
        self.evidence_for();bridge.complete(self.record,self.evidence)
        (self.root/'working/tool-response.txt').write_text('Replaced fixture evidence')
        with self.assertRaisesRegex(ValueError,'changed'):bridge.verify(self.record,'fresh')
    def test_provider_success_retains_honest_verification_limit(self):
        self.spec['operation']='provider_generation';self.begin();self.evidence_for(provider=True)
        result=bridge.complete(self.record,self.evidence)
        self.assertEqual(result['provider_job_id'],'fixture-job');self.assertIn('cannot cryptographically',result['verification_limit'])

if __name__=='__main__':unittest.main()
