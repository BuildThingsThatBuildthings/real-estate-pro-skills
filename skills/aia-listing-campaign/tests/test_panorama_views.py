import hashlib,importlib.util,tempfile,unittest,sys
from pathlib import Path
from PIL import Image,ImageDraw
S=Path(__file__).resolve().parents[1]/'scripts';sys.path.insert(0,str(S))
from inspect_panorama_views import render
class Inputs:
    run_id='fixture'
    def read(self,p):return Path(p).read_bytes()
    def finish(self):self.finished=True
class PanoramaViewsTests(unittest.TestCase):
    def test_actual_projection_and_private_destination(self):
        with tempfile.TemporaryDirectory() as t:
            r=Path(t);source=r/'original.png';p=Image.new('RGB',(512,256),'red');d=ImageDraw.Draw(p);d.rectangle((256,0,511,255),fill='blue');p.save(source)
            sha=hashlib.sha256(source.read_bytes()).hexdigest();v={'source':str(source),'sha256':sha,'label':'fixture','yaw':-100}
            spec={'root':str(r),'run_id':'fixture','views':[v]};i=Inputs();out=r/'working/views.png';render(spec,i,out)
            self.assertTrue(i.finished);self.assertEqual(Image.open(out).size,(1920,396))
            with self.assertRaises(ValueError):render(spec,Inputs(),r/'output/views.png')
            with self.assertRaises(ValueError):render(spec,Inputs(),out)
            spec['views']=[{**v,'yaw':181}]
            with self.assertRaises(ValueError):render(spec,Inputs(),r/'working/invalid.png')
            spec['views']=[{**v,'sha256':'0'*64}]
            with self.assertRaises(ValueError):render(spec,Inputs(),r/'working/changed.png')
if __name__=='__main__':unittest.main()
