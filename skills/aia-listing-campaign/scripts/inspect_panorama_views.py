#!/usr/bin/env python3
"""Calibrate actual perspective views before a panorama motion batch; private QA only."""
import argparse, hashlib, io, json, math, subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from production_inputs import Inputs


def render(spec, inputs, output):
    root=Path(spec['root']).resolve();output=Path(output).resolve()
    if spec.get('run_id')!=inputs.run_id or not output.is_relative_to(root/'working') or output.suffix!='.png' or output.exists():
        raise ValueError('Fresh private sheet in the active run required')
    views=spec['views']
    if not 1<=len(views)<=48:raise ValueError('Select1to48 explicit source views')
    width,height,footer=640,360,36
    sheet=Image.new('RGB',(width*3,(height+footer)*math.ceil(len(views)/3)),'#171717')
    draw=ImageDraw.Draw(sheet);font=ImageFont.load_default(size=18)
    for n,v in enumerate(views):
        source=(root/v['source']).resolve();data=inputs.read(source)
        if hashlib.sha256(data).hexdigest()!=v['sha256']:raise ValueError('Original bytes changed')
        with Image.open(io.BytesIO(data)) as p:
            if p.width!=p.height*2:raise ValueError('Full2to1 panorama required')
        yaw,pitch,hfov=v['yaw'],v.get('pitch',0),v.get('h_fov',80)
        if not all(isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x) for x in (yaw,pitch,hfov)) or not -180<=yaw<=180 or not -85<=pitch<=85 or not 10<=hfov<=110:raise ValueError('Invalid authored view')
        vfov=math.degrees(2*math.atan(math.tan(math.radians(hfov/2))*height/width))
        filt=f'v360=input=equirect:output=flat:w={width}:h={height}:yaw={yaw}:pitch={pitch}:h_fov={hfov}:v_fov={vfov}:interp=cubic'
        result=subprocess.run(['ffmpeg','-v','error','-i',str(source),'-vf',filt,'-frames:v','1','-threads','1','-f','image2pipe','-vcodec','png','-'],capture_output=True,check=True,timeout=60)
        tile=Image.open(io.BytesIO(result.stdout));x=n%3*width;y=n//3*(height+footer)
        sheet.paste(tile,(x,y));draw.text((x+12,y+height+8),f"{v['label']} | yaw {yaw}",font=font,fill='white')
    output.parent.mkdir(parents=True,exist_ok=True);sheet.save(output);inputs.finish()
    print(f'Calibrated {len(views)} actual source views: {output}')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('spec');p.add_argument('output');a=p.parse_args();inputs=Inputs()
    render(json.loads(inputs.read(a.spec)),inputs,a.output)
