import importlib.util
import json
from pathlib import Path
import sys
import hashlib
import os
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS=Path(__file__).resolve().parents[1]/'scripts'
sys.path.insert(0,str(SCRIPTS))
spec=importlib.util.spec_from_file_location('prepare_camera_films',SCRIPTS/'prepare_films.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

class PrepareCameraFilmsTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);(self.root/'context').mkdir()
        self.config={'run_id':'new','compositions':[{'run_id':'new','composition_id':'vertical','output':str(self.root/'delivery/vertical.mp4')}]}
    def tearDown(self):self.tmp.cleanup()
    def prepare(self):
        (self.root/'context/film-timelines.json').write_text(json.dumps(self.config))
        path=self.root/'context/film-timelines.json'
        declared=[{'path':str(path.resolve()),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'origin':'original','source_id':'fixture'}]
        with patch.dict(os.environ,{'AIA_RUN_ID':'new','AIA_TASK_INPUTS_JSON':json.dumps(declared),'AIA_PRODUCTION_RECEIPT':str(self.root/'working/receipt.json')}), patch.object(module,'validate',return_value=80):return module.prepare(self.root)
    def test_writes_only_internal_camera_jobs(self):
        jobs=self.prepare();self.assertEqual(jobs[0]['operation'],'edit_camera_sequence.py')
        self.assertFalse((self.root/'delivery').exists());self.assertTrue(Path(jobs[0]['config']).is_file())
    def test_rejects_duplicate_composition(self):
        self.config['compositions']*=2
        with self.assertRaises(ValueError):self.prepare()
    def test_rejects_stale_run(self):
        self.config['compositions'][0]['run_id']='old'
        with self.assertRaises(ValueError):self.prepare()

if __name__=='__main__':unittest.main()
