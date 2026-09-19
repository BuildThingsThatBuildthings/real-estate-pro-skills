#!/usr/bin/env python3
"""Inspect authored photo framing before an expensive film render. Private evidence only."""
import argparse,hashlib,json,sys
from pathlib import Path
from PIL import Image,ImageDraw
from production_inputs import Inputs
from edit_camera_sequence import photo_windows,PHOTO_SUFFIXES

def inspect(config_path, output, inputs=None):
 inputs=inputs or Inputs();c=json.loads(inputs.read(config_path));out=Path(output).resolve()
 if c.get("run_id")!=inputs.run_id:raise ValueError("Composition belongs to another run")
 if 'working' not in out.parts or any(p in out.parts for p in ('output','delivery','handoff')) or out.suffix!='.jpg':raise ValueError('Composition inspection stays private under working as JPG')
 if out.exists():raise ValueError('Fresh private inspection output required')
 photos=[(i,s) for i,s in enumerate(c['shots']) if Path(s['path']).suffix.lower() in PHOTO_SUFFIXES]
 if not photos:raise ValueError('No authored source-photo frames')
 width=240;height=round(width*c['height']/c['width']);row=height+30
 sheet=Image.new('RGB',(width*3,row*len(photos)),'#eeeeee');draw=ImageDraw.Draw(sheet)
 for index,(shot_index,shot) in enumerate(photos):
  raw=inputs.read(shot['path']);actual=hashlib.sha256(raw).hexdigest()
  if actual!=shot.get('source_sha256'):raise ValueError('Reviewed photo bytes changed')
  _,_,windows=photo_windows(shot,c['width'],c['height'])
  with Image.open(shot['path']) as original:
   picture=original.convert('RGB')
   for column,t in enumerate((0,.5,1)):
    x,y,w,h=[a+(b-a)*t for a,b in zip(*windows)]
    tile=picture.transform((width,height),Image.Transform.EXTENT,(x,y,x+w,y+h),resample=Image.Resampling.BICUBIC)
    sheet.paste(tile,(column*width,index*row));draw.text((column*width+6,index*row+height+5),f'Shot {shot_index+1}: {Path(shot["path"]).stem} / {t:.0%}',fill='black')
 out.parent.mkdir(parents=True,exist_ok=True);sheet.save(out,quality=90);inputs.finish();return out
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('config');p.add_argument('output');a=p.parse_args();print(inspect(a.config,a.output))
