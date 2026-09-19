import importlib.util,json,hashlib,sys,tempfile,unittest
from pathlib import Path
from PIL import Image
scripts=Path(__file__).resolve().parents[1]/'scripts';sys.path.insert(0,str(scripts))
from inspect_composition_frames import inspect
class I:
 run_id="fixture"
 def read(self,p):return Path(p).read_bytes()
 def finish(self):pass
class InspectionTest(unittest.TestCase):
 def test_actual_portrait_crop_and_private_destination(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);p=r/'source.png';im=Image.new('RGB',(400,200),'blue');im.paste('red',(0,0,120,200));im.save(p)
   c={'run_id':'fixture','width':100,'height':200,'shots':[{'path':str(p),'source_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'motion':{'start':{'x':0,'y':0,'width':100,'height':200},'end':{'x':20,'y':0,'width':100,'height':200}}}]};cp=r/'config.json';cp.write_text(json.dumps(c));out=r/'working/contact.jpg';inspect(cp,out,I())
   with Image.open(out) as result:self.assertGreater(result.getpixel((100,200))[0],200)
   with self.assertRaises(ValueError):inspect(cp,r/'output/contact.jpg',I())
 def test_changed_source_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);p=r/'source.png';Image.new('RGB',(100,200)).save(p);cp=r/'config.json';cp.write_text(json.dumps({'run_id':'fixture','width':100,'height':200,'shots':[{'path':str(p),'source_sha256':'wrong'}]}))
   with self.assertRaises(ValueError):inspect(cp,r/'working/contact.jpg',I())
if __name__=='__main__':unittest.main()
