#!/usr/bin/env python3
"""Private, uncropped contact sheets of exact source photographs for framing decisions."""
import argparse,hashlib,io,json,math
from pathlib import Path
from PIL import Image,ImageOps,ImageDraw,ImageFont
from production_inputs import Inputs

def render(spec,inputs):
 root=Path(spec['root']).resolve()
 if spec.get('run_id')!=inputs.run_id:raise ValueError('Active run required')
 for page in spec['pages']:
  out=(root/page['output']).resolve();items=page['images']
  if not out.is_relative_to(root/'working') or out.suffix!='.png' or out.exists() or not 1<=len(items)<=18:raise ValueError('Fresh private sheet with1to18 originals required')
  image=Image.new('RGB',(1536,math.ceil(len(items)/3)*380),'#171717');draw=ImageDraw.Draw(image);font=ImageFont.load_default(size=20)
  for n,item in enumerate(items):
   data=inputs.read((root/item['path']).resolve())
   if hashlib.sha256(data).hexdigest()!=item['sha256']:raise ValueError('Source changed')
   with Image.open(io.BytesIO(data)) as src:tile=ImageOps.contain(src.convert('RGB'),(512,340))
   x=n%3*512;y=n//3*380;image.paste(tile,(x+(512-tile.width)//2,y+(340-tile.height)//2));draw.text((x+12,y+348),item['id'],font=font,fill='white')
  out.parent.mkdir(parents=True,exist_ok=True);image.save(out);print(out)
 inputs.finish()
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('spec');a=p.parse_args();i=Inputs();render(json.loads(i.read(a.spec)),i)
