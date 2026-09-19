import sys,tempfile,hashlib,unittest
from pathlib import Path
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from inspect_photo_sources import render
class I:
 run_id='fixture'
 def read(self,p):return Path(p).read_bytes()
 def finish(self):self.done=True
class Tests(unittest.TestCase):
 def test_uncropped_private_source_review(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);p=r/'source.png';Image.new('RGB',(300,600),'red').save(p);s={'root':str(r),'run_id':'fixture','pages':[{'output':'working/sheet.png','images':[{'id':'original portrait','path':p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}]}]};i=I();render(s,i);self.assertTrue(i.done)
   with Image.open(r/'working/sheet.png') as im:self.assertEqual(im.getpixel((250,170)),(255,0,0));self.assertEqual(im.getpixel((10,170)),(23,23,23))
   s['pages'][0]['output']='output/sheet.png'
   with self.assertRaises(ValueError):render(s,I())
if __name__=='__main__':unittest.main()
