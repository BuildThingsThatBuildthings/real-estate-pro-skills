import hashlib, importlib.util, json, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
spec=importlib.util.spec_from_file_location('panorama_sequence',Path(__file__).parents[1]/'scripts/panorama_sequence.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class PanoramaSequenceTests(unittest.TestCase):
    def test_original_lineage_and_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);original=root/'original.jpg';original.write_bytes(b'original capture')
            parent={'root':tmp,'source':'original.jpg','source_sha256':m.digest(original),'run_id':'fresh','projection':'equirectangular','source_identity':'capture-01','output':'room.mp4','room_identity':'kitchen','rights':'authorized','rights_basis':'Listing photographer authorized client campaign'}
            config=root/'parent.json';config.write_text(json.dumps(parent));shot={'panorama_config':str(config),'path':str(root/'room.mp4'),'origin':'generated','room_identity':'kitchen'}
            self.assertEqual(m.panorama_inputs(shot,'fresh')[1],original.resolve())
            original.write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'missing, changed'):m.panorama_inputs(shot,'fresh')
    def test_varied_actual_capture_coverage(self):
        shots=[{'panorama_config':str(i),'seconds':6} for i in range(5)]+[{'seconds':4.5} for i in range(10)]
        config={'mode':'panorama_photo_edit','kind':'flagship','run_id':'fresh','shots':shots}
        parents=[{'source_sha256':str(i),'room_identity':str(i%4)} for i in range(5)]
        with patch.object(m,'panorama_inputs',side_effect=[(None,None,p) for p in parents]):m.validate_coverage(config,{str(i):[] for i in range(8)},75)
        parents[4]['source_sha256']='0'
        with patch.object(m,'panorama_inputs',side_effect=[(None,None,p) for p in parents]):
            with self.assertRaisesRegex(ValueError,'five distinct'):m.validate_coverage(config,{str(i):[] for i in range(8)},75)
    def test_all_photo_substitution_rejected(self):
        with self.assertRaises(ValueError):m.validate_coverage({'mode':'panorama_photo_edit','kind':'flagship','run_id':'fresh','shots':[{'seconds':3} for _ in range(25)]},{str(i):[] for i in range(25)},75)
if __name__=='__main__':unittest.main()
