import importlib.util, unittest
from pathlib import Path
spec = importlib.util.spec_from_file_location('gate', Path(__file__).parents[1] / 'scripts/validate_campaign.py')
gate = importlib.util.module_from_spec(spec); spec.loader.exec_module(gate)

class PortabilityGate(unittest.TestCase):
    def fixture(self):
        return {'client_slug':'fictional-harbor','brand':{'name':'Harbor & Pine','color':'#174E52'},'sources':[{'id':'fictional-brief'}], 'claims':[{'id':'harbor','status':'verified','source_ids':['fictional-brief']}], 'media':[{'id':'map','rights':'original','rights_basis':'Fictional diagram created for test'}], 'deliverables':[{'id':'harbor-film','kind':'video','required':True,'status':'planned','claim_ids':['harbor'],'media_ids':['map']}]}
    def test_other_brand_can_plan(self):
        self.assertEqual(gate.validate(self.fixture()), [])
    def test_missing_film_is_not_complete(self):
        self.assertIn('required deliverable incomplete', ' '.join(gate.validate(self.fixture(), True)))
    def test_unverified_local_claim_rejected(self):
        r=self.fixture(); r['claims'][0]['status']='unresolved'
        self.assertIn('unsupported claim', ' '.join(gate.validate(r)))
    def test_public_image_without_permission_rejected(self):
        r=self.fixture(); r['media'][0]['rights']='unresolved'
        self.assertIn('unresolved rights', ' '.join(gate.validate(r)))
    def test_public_provider_voice_is_not_automatically_commercial(self):
        r=self.fixture(); r['media'][0].update(rights='licensed',rights_basis='Public voice on Free plan')
        self.assertIn('commercial license not established', ' '.join(gate.validate(r)))

    def test_fractional_bath_count_preserved_by_source_scanner(self):
        path=Path(__file__).parents[2]/'compliance-gate/scripts/fair_housing.py'
        spec=importlib.util.spec_from_file_location('fair',path);fair=importlib.util.module_from_spec(spec);spec.loader.exec_module(fair)
        self.assertIn(('NEEDS_SOURCE','2.5 baths','room counts needs a source, a VERIFY marker, or first-person attribution'),fair.check('This home has 2.5 baths.'))

    def test_frame_samples_not_full_review(self):
        r=self.fixture(); r['deliverables'][0].update(status='complete',path='film.mp4',review={'frames':True})
        self.assertIn('missing complete video review', ' '.join(gate.validate(r)))

if __name__ == '__main__': unittest.main()
