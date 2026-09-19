#!/usr/bin/env python3
"""Render an attributed geographic overview from verified coordinates, without route claims."""
import argparse, hashlib, json, math, subprocess, sys
import xml.etree.ElementTree as ET
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'aia-listing-campaign/scripts'))
from production_inputs import Inputs

def render(config_path):
    inputs=Inputs();inputs.read(config_path)
    c=json.loads(Path(config_path).read_text())
    width,height=int(c['width']),int(c['height']);fps=int(c.get('fps',24));duration=float(c['seconds'])
    if width<320 or height<320 or not 2<=duration<=20:raise ValueError('Invalid map composition')
    locations=c['locations']
    if len(locations)<2 or any(not x.get('source_url') or not x.get('verified_at') for x in locations):raise ValueError('Every mapped point requires verification')
    font=Path(c['font']);inputs.read(font)
    unit=min(width,height)
    big=ImageFont.truetype(str(font),max(26,int(unit*.046)));small=ImageFont.truetype(str(font),max(18,int(unit*.022)));label=ImageFont.truetype(str(font),max(22,int(unit*.030)))
    lat=[float(x['latitude']) for x in locations];lon=[float(x['longitude']) for x in locations]
    if any(not -90<=x<=90 for x in lat) or any(not -180<=x<=180 for x in lon):raise ValueError('Invalid geographic coordinate')
    centerlat=sum(lat)/len(lat);cos=math.cos(math.radians(centerlat));xs=[x*cos for x in lon]
    minx,maxx=min(xs),max(xs);miny,maxy=min(lat),max(lat)
    spanx=max(maxx-minx,.008);spany=max(maxy-miny,.008)
    scale=min(width*.56/spanx,height*.42/spany)
    centerx=(minx+maxx)/2;centery=(miny+maxy)/2
    points=[(width/2+(x-centerx)*scale,height*.50-(y-centery)*scale) for x,y in zip(xs,lat)]
    geometry=[]
    if not c.get('osm_source'):raise ValueError('Geographic overview requires actual open map geometry')
    osm=ET.fromstring(inputs.read(c['osm_source']))
    nodes={n.attrib['id']:(float(n.attrib['lon'])*cos,float(n.attrib['lat'])) for n in osm.findall('node')}
    for way in osm.findall('way'):
        tags={t.attrib['k']:t.attrib['v'] for t in way.findall('tag')}
        vertices=[nodes[n.attrib['ref']] for n in way.findall('nd') if n.attrib['ref'] in nodes]
        if len(vertices)>1:geometry.append((vertices,tags))
    output=Path(c['output']);output.parent.mkdir(parents=True,exist_ok=True)
    cmd=['ffmpeg','-v','error','-nostdin','-y','-f','rawvideo','-pixel_format','rgb24','-video_size',f'{width}x{height}','-framerate',str(fps),'-i','pipe:0','-an','-c:v','libx264','-preset','fast','-crf','19','-pix_fmt','yuv420p','-movflags','+faststart',str(output)]
    proc=subprocess.Popen(cmd,stdin=subprocess.PIPE)
    for frame in range(round(duration*fps)):
        t=frame/fps;im=Image.new('RGB',(width,height),c.get('background','#F4F2EB'));d=ImageDraw.Draw(im)
        ink=c.get('ink','#171717');accent=c.get('accent','#D71920');margin=round(width*.07)
        zoom=1+.045*t/duration
        def project(x,y):return (width/2+(x-centerx)*scale*zoom,height*.5-(y-centery)*scale*zoom)
        for vertices,tags in geometry:
            xy=[project(x,y) for x,y in vertices]
            if len(xy)>2 and (tags.get('leisure') in ('park','pitch','playground') or tags.get('landuse') in ('forest','grass','recreation_ground') or tags.get('natural')=='wood'):
                d.polygon(xy,fill='#D3DFCA')
            elif len(xy)>2 and (tags.get('natural')=='water' or tags.get('water')):d.polygon(xy,fill='#ADD1D6')
            elif tags.get('building') and len(xy)>2:d.polygon(xy,fill='#DED9D0')
        for vertices,tags in geometry:
            xy=[project(x,y) for x,y in vertices]
            if tags.get('highway'):
                size=round(unit*(.005 if tags['highway'] in ('primary','secondary','tertiary') else .0027))
                d.line(xy,fill='#C5C0B6',width=size+3,joint='curve');d.line(xy,fill='#FFFFFF',width=size,joint='curve')
            elif tags.get('waterway'):d.line(xy,fill='#ADD1D6',width=3)
        d.rectangle((0,0,width,height*.19),fill=c.get('background','#F4F2EB'))
        d.rectangle((0,height*.85,width,height),fill=c.get('background','#F4F2EB'))
        d.text((margin,height*.07),c['title'],font=big,fill=ink)
        d.text((margin,height*.07+big.size+20),c.get('subtitle','Area overview'),font=small,fill=ink)
        for i,(rawx,rawy,location) in enumerate(zip(xs,lat,locations)):
            x,y=project(rawx,rawy)
            phase=max(0,min(1,(t-i*.7)/.8));radius=round((9+4*phase)*width/1080)
            if phase<=0:continue
            pulse=radius+round((math.sin(t*2-i)+1)*9*width/1080)
            d.ellipse((x-pulse,y-pulse,x+pulse,y+pulse),outline=accent,width=2)
            d.ellipse((x-radius,y-radius,x+radius,y+radius),fill=accent)
            text=location['label'];box=d.textbbox((0,0),text,font=label);tw=box[2]-box[0]
            tx=max(margin,min(width-margin-tw,x-tw/2));ty=y+radius+20
            d.rounded_rectangle((tx-12,ty-8,tx+tw+12,ty+label.size+12),radius=7,fill='#F4F2EB')
            d.text((tx,ty),text,font=label,fill=ink)
        d.line((width-margin,height*.24,width-margin,height*.19),fill=ink,width=3)
        d.polygon([(width-margin,height*.18),(width-margin-7,height*.20),(width-margin+7,height*.20)],fill=ink)
        d.text((width-margin-7,height*.145),'N',font=small,fill=ink)
        d.text((margin,height*.87),'Approximate area markers · not a route map',font=small,fill=ink)
        d.text((margin,height*.91),c['attribution'],font=small,fill=ink)
        if c.get('still_output') and frame == round(duration*fps/2):
            still=Path(c['still_output']);still.parent.mkdir(parents=True,exist_ok=True);im.save(still)
        proc.stdin.write(im.tobytes())
    proc.stdin.close()
    if proc.wait():raise RuntimeError('Map render failed')
    inputs.finish()
    print('Rendered area overview: '+str(output))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('config');render(p.parse_args().config)
