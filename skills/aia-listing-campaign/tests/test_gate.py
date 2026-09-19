import importlib.util, unittest, tempfile, subprocess, shutil, json
from unittest.mock import patch
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

class FullCampaignGate(unittest.TestCase):
    def fixture(self):
        return {'profile': 'full-listing-campaign', 'client_slug': 'fictional-alpine', 'brand': {'name': 'Alpine & River'}, 'deliverables': [{'id': key, 'kind': kind, 'required': True, 'status': 'planned'} for key, kind in gate.FULL_INVENTORY.items()]}

    def test_full_inventory_can_plan(self):
        self.assertEqual(gate.validate(self.fixture()), [])

    def test_omitted_flagship_rejected_even_if_remaining_all_complete(self):
        run = self.fixture(); run['deliverables'] = [d for d in run['deliverables'] if d['id'] != 'property-film-horizontal']
        self.assertIn('property-film-horizontal: missing full campaign deliverable', gate.validate(run))

    def test_doc_cannot_replace_film_or_drop_required_status(self):
        run = self.fixture(); run['deliverables'][0].update(kind='document', path='story.pdf', required=False)
        self.assertIn('cannot be downgraded or substituted', ' '.join(gate.validate(run)))

    def test_technical_sidecar_never_deliverable(self):
        run = self.fixture(); run['deliverables'].append({'id':'metadata', 'kind':'document', 'status':'planned', 'path':'run.json'})
        self.assertIn('file type does not match', ' '.join(gate.validate(run)))

    def test_review_booleans_do_not_complete_full_review(self):
        run = self.fixture(); run['deliverables'][0].update(status='complete', path='missing.mp4', review={'full_sound':True, 'full_muted':True, 'fidelity':True, 'reviewer':'Test', 'reviewed_at':'2026-09-07'})
        errors = ' '.join(gate.validate(run))
        self.assertIn('exact finished video hash', errors)
        self.assertIn('missing private sound review evidence', errors)
        self.assertIn('missing private muted review evidence', errors)

    @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'FFmpeg required')
    def test_actual_duration_aspect_and_audio_checked(self):
        with tempfile.TemporaryDirectory() as directory:
            movie = Path(directory)/'test.mp4'
            subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=c=red:s=160x90:d=0.2', '-f', 'lavfi', '-i', 'sine=frequency=440:duration=0.2', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-shortest', str(movie)], check=True)
            self.assertGreater(gate.probe_film(movie, (0, 1, '16:9')), 0)
            with self.assertRaisesRegex(ValueError, 'duration'): gate.probe_film(movie, (75, 90, '16:9'))
            with self.assertRaisesRegex(ValueError, 'composition'): gate.probe_film(movie, (0, 1, '9:16'))
            silent = Path(directory)/'silent.mp4'
            subprocess.run(['ffmpeg', '-v', 'error', '-i', str(movie), '-an', '-c:v', 'copy', str(silent)], check=True)
            with self.assertRaisesRegex(ValueError, 'audio stream'): gate.probe_film(silent)

if __name__ == '__main__': unittest.main()
