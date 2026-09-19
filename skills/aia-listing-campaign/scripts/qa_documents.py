#!/usr/bin/env python3
"""Private page previews, PDF extraction and exact QR decoding; never claims human approval."""
import argparse,hashlib,json,subprocess
from pathlib import Path
from PIL import Image,ImageDraw,ImageOps

def private(path):
 path=Path(path).resolve()
 if 'working' not in path.parts or any(x in path.parts for x in ('output','delivery','handoff')):raise ValueError('QA remains in private working storage')
 path.mkdir(parents=True,exist_ok=True);return path

def sheets(paths,dest,prefix):
 outputs=[]
 for start in range(0,len(paths),6):
  items=paths[start:start+6];im=Image.new('RGB',(1536,760 if len(items)<=3 else 1520),'#eeeeee');d=ImageDraw.Draw(im)
  for n,p in enumerate(items):
   with Image.open(p) as page:tile=ImageOps.contain(page.convert('RGB'),(500,715))
   x=n%3*512;y=n//3*760;im.paste(tile,(x+(512-tile.width)//2,y));d.text((x+8,y+720),p.stem[:64],fill='black')
  out=dest/f'{prefix}-{start//6+1:02}.jpg';im.save(out,quality=90);outputs.append(str(out))
 return outputs

def check(spec,destination):
 out=private(destination);records=[]
 for item in spec.get('documents',[]):
  p=Path(item['path']).resolve()
  if hashlib.sha256(p.read_bytes()).hexdigest()!=item['sha256']:raise ValueError('PDF bytes changed')
  folder=out/item['id'];folder.mkdir(exist_ok=True)
  subprocess.run(['pdftoppm','-r','72','-png',str(p),str(folder/'page')],check=True,capture_output=True)
  text=subprocess.check_output(['pdftotext','-layout',str(p),'-'],text=True);(folder/'extracted.txt').write_text(text)
  pages=sorted(folder.glob('page-*.png'));records.append({'id':item['id'],'pages':len(pages),'nonempty_text':bool(text.strip()),'source_sha256':item['sha256'],'sheets':sheets(pages,folder,'pages'),'perceptual_review':False})
 if spec.get('images'):
  paths=[]
  for item in spec['images']:
   p=Path(item['path']);
   if hashlib.sha256(p.read_bytes()).hexdigest()!=item['sha256']:raise ValueError('Image bytes changed')
   with Image.open(p) as im:im.verify()
   paths.append(p)
  records.append({'images':len(paths),'sheets':sheets(paths,out,'images'),'perceptual_review':False})
 if spec.get('qr'):
  import cv2
  q=spec['qr'];p=Path(q['path'])
  if p.suffix.lower()=='.pdf':
   subprocess.run(['pdftoppm','-f','1','-singlefile','-r','300','-png',str(p),str(out/'qr-page')],check=True,capture_output=True)
   p=out/'qr-page.png'
  decoded,_,_=cv2.QRCodeDetector().detectAndDecode(cv2.imread(str(p)))
  if decoded!=q['destination']:raise ValueError('QR destination mismatch' if decoded else 'QR could not be decoded at the supplied resolution')
  records.append({'qr_destination':decoded,'decoded':True,'live_destination_review':False})
 (out/'technical-review.json').write_text(json.dumps(records,indent=2));return records
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('manifest');p.add_argument('output');a=p.parse_args();r=check(json.loads(Path(a.manifest).read_text()),a.output);print(json.dumps(r,indent=2))
