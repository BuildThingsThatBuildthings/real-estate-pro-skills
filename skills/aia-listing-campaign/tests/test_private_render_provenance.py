import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image

SCRIPTS = Path(__file__).resolve().parents[1]/'scripts'
sys.path.insert(0, str(SCRIPTS))
from production_inputs import Inputs
import render_photo_designs
import render_manifest


def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()


class PrivateProvenanceTests(unittest.TestCase):
    def test_actual_photo_hash_and_private_sidecars(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve()
            agent=root/'agents/fixture'
            shutil.copytree(SCRIPTS.parents[1]/'content-foundry/tests/fixtures/agent', agent)
            source=root/'photo.png';Image.new('RGB',(20,20),'red').save(source)
            run=root/'run.json';run.write_text('{"run_id":"new-run"}')
            spec={'run_id':'new-run','id':'cover','agent':'fixture','size':[20,20],'safe_zone':{},'output':'output/03 Graphics/cover.png','layers':[{'type':'photo','path':'photo.png','rights':'original','rights_basis':'test fixture'},{'type':'logo','path':'photo.png','box':[0,0,2,2],'rights':'original','rights_basis':'test fixture'}]}
            paths=[source,agent/'brand-context-visual.md',agent/'brand-context-compliance.md']
            declarations=[{'path':str(p),'sha256':digest(p),'origin':'original','source_id':str(i)} for i,p in enumerate(paths)]
            receipt=root/'working/production.json'
            with patch.dict(os.environ, {'AIA_RUN_ID':'new-run','AIA_PRODUCTION_RECEIPT':str(receipt),'AIA_TASK_INPUTS_JSON':json.dumps(declarations)}):
                inputs=Inputs()
                # Isolate provenance from the separately tested footer policy.
                with patch.object(render_photo_designs.AgentBrand,'required_strings',return_value={}):
                    out=Path(render_photo_designs.render(spec,root,inputs))
                inputs.finish()
            self.assertEqual([p.suffix for p in (root/'output/03 Graphics').iterdir()], ['.png'])
            evidence=json.loads((root/'working/design-receipts/cover.json').read_text())
            self.assertEqual(evidence['rendered_layers'][0]['source_sha256'],digest(source))
            self.assertEqual(evidence['run_id'],'new-run')
            self.assertTrue((root/'working/design-receipts/cover.composite.json').is_file())
            self.assertEqual(len(json.loads(receipt.read_text())['consumed']),3)

    def test_source_window_preserves_selected_pixels_and_rejects_outside_source(self):
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();agent=root/'agents/fixture'
            shutil.copytree(SCRIPTS.parents[1]/'content-foundry/tests/fixtures/agent',agent)
            source=root/'photo.png';im=Image.new('RGB',(20,40),'red')
            im.paste(Image.new('RGB',(20,20),'blue'),(0,20));im.save(source)
            inputs=SimpleNamespace(run_id='new-run',consumed={},read=lambda p:Path(p).read_bytes())
            layer={'type':'photo','path':'photo.png','rights':'original','rights_basis':'fixture','source_box':[0,20,20,40]}
            spec={'run_id':'new-run','id':'crop','agent':'fixture','size':[20,20],'safe_zone':{},'output':'output/03 Graphics/crop.png','layers':[layer,{'type':'logo','path':'photo.png','box':[0,0,2,2],'rights':'original','rights_basis':'fixture'}]}
            with patch.object(render_photo_designs.AgentBrand,'required_strings',return_value={}):
                output=render_photo_designs.render(spec,root,inputs)
            with Image.open(output) as result:self.assertEqual(result.getpixel((10,10)),(0,0,255))
            for bounds in ([0,20,21,40],[0,-1,20,30],[1,1,0,10]):
                layer['source_box']=bounds
                with self.assertRaisesRegex(ValueError,'Source box'):render_photo_designs.render(spec,root,inputs)

    def test_undeclared_or_changed_inputs_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);path=root/'photo.png';path.write_bytes(b'original')
            declarations=[{'path':str(path.resolve()),'sha256':digest(path),'origin':'original','source_id':'fixture'}]
            with patch.dict(os.environ, {'AIA_RUN_ID':'run','AIA_PRODUCTION_RECEIPT':str(root/'working/receipt.json'),'AIA_TASK_INPUTS_JSON':json.dumps(declarations)}):
                inputs=Inputs()
                with self.assertRaisesRegex(ValueError,'undeclared'):inputs.read(root/'other.png')
                path.write_bytes(b'replacement')
                with self.assertRaisesRegex(ValueError,'hash changed'):inputs.read(path)
                with self.assertRaisesRegex(ValueError,'not actually consumed'):inputs.finish()

    def test_valid_duration_cannot_reuse_prior_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);movie=root/'film.mp4';movie.write_bytes(b'old bytes')
            receipt=root/'receipt.json';receipt.write_text(json.dumps({'inputs':{'run_id':'old'},'output_sha256':digest(movie)}))
            with patch.object(render_manifest,'valid',return_value=True):
                self.assertFalse(render_manifest.reusable(movie,receipt,{'run_id':'new'},80))
            self.assertFalse(render_manifest.reusable(movie,root/'missing.json',{'run_id':'new'},80))

if __name__ == '__main__':unittest.main()
