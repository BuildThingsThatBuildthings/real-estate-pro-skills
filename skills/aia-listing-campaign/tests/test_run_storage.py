import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
spec=importlib.util.spec_from_file_location('run_storage',Path(__file__).parents[1]/'scripts/run_storage.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class RunStorageTests(unittest.TestCase):
    def test_temporary_production_rejected(self):
        with tempfile.TemporaryDirectory() as p:
            with self.assertRaisesRegex(ValueError,'persistent'):m.initialize(Path(p)/'campaign','client')
            self.assertEqual(m.initialize(Path(p)/'fixture','fixture','test')['scope'],'test')
    def test_exact_original_restore_and_idempotence(self):
        with tempfile.TemporaryDirectory() as p:
            base=Path(p);source=base/'old/assets/photos';source.mkdir(parents=True);(source/'photo.jpg').write_bytes(b'actual original')
            root=base/'fixture';m.initialize(root,'recovery','test');item=m.inventory(source,'source/photos','original','Authorized listing source')
            plan={'root':str(root),'run_id':'recovery','scope':'test','authorization':'Restore original listing assets','allowed_source_roots':[str(base/'old')],'sources':[item]}
            receipt=root/'working/restore.json';self.assertTrue(m.restore(plan,receipt)['complete']);self.assertTrue(m.restore(plan,receipt)['complete']);self.assertEqual((root/'source/photos/photo.jpg').read_bytes(),b'actual original')
            (source/'photo.jpg').write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'changed since'):m.restore(plan,receipt)
    def test_rejected_export_never_original(self):
        with tempfile.TemporaryDirectory() as p:
            base=Path(p);source=base/'old/delivery/film.mp4';source.parent.mkdir(parents=True);source.write_bytes(b'rejected')
            root=base/'fixture';m.initialize(root,'recovery','test');item=m.inventory(source,'source/film.mp4','original','Claimed original')
            plan={'root':str(root),'run_id':'recovery','scope':'test','authorization':'Restore sources','allowed_source_roots':[str(base/'old')],'sources':[item]}
            with self.assertRaisesRegex(ValueError,'Rejected exports'):m.restore(plan,root/'working/restore.json')
    def test_conflicting_destination_preserved(self):
        with tempfile.TemporaryDirectory() as p:
            base=Path(p);source=base/'font.ttf';source.write_bytes(b'font');root=base/'fixture';m.initialize(root,'recovery','test');item=m.inventory(source,'dependencies/font.ttf','dependency','Licensed font')
            (root/'dependencies/font.ttf').write_bytes(b'other')
            plan={'root':str(root),'run_id':'recovery','scope':'test','authorization':'Restore dependencies','allowed_source_roots':[str(base)],'sources':[item]}
            with self.assertRaisesRegex(ValueError,'conflicting'):m.restore(plan,root/'working/restore.json')
            self.assertEqual((root/'dependencies/font.ttf').read_bytes(),b'other')
if __name__=='__main__':unittest.main()
