#!/usr/bin/env python3
"""Deterministic source-photo graphics, exact fonts/logos, and auditable text layout."""
import argparse,json,textwrap
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont,ImageOps
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

def main():
 ap=argparse.ArgumentParser();ap.add_argument('run');a=ap.parse_args();r=Path(a.run);brand=json.loads((r/'context/brand.json').read_text());items=json.loads((r/'context/graphics.json').read_text())
 for weight in (400,700):
  out=r/'working'/f'inter-{weight}.ttf'
  if not out.exists():
   f=TTFont(r/'assets'/brand.get('font_source','inter.woff2'));f=instantiateVariableFont(f,{'wght':weight});f.flavor=None;f.save(out)
 font=lambda n,b=False:ImageFont.truetype(str(r/'working'/f'inter-{700 if b else 400}.ttf'),n)
 manifest=[]
 for g in items:
  w,h=(1080,1920) if g.get('format')=='story' else (1080,1350);im=Image.new('RGB',(w,h),brand['paper']);d=ImageDraw.Draw(im);pad=76
  d.rectangle((0,0,w,9),fill=brand['red']);d.text((pad,57),brand['name'].upper(),font=font(26,True),fill=brand['dark']);d.text((pad,130),g['eyebrow'].upper(),font=font(25,True),fill=brand['red'])
  y=186;fs=82 if h>1400 else 76
  for line in g['headline'].split('\n'):
   if d.textlength(line,font=font(fs,True))>w-2*pad:raise ValueError('Headline overflow: '+g['id'])
   d.text((pad,y),line,font=font(fs,True),fill=brand['dark']);y+=fs+2
  photo_top=max(y+36,400 if h>1400 else 360);photo_h=720 if h>1400 else 540
  if g.get('photo'):
   p=Image.open(r/'assets/photos'/f"photo-{g['photo']:02}.webp").convert('RGB');p=ImageOps.contain(p,(w,photo_h));im.paste(p,((w-p.width)//2,photo_top+(photo_h-p.height)//2))
  else:
   d.rectangle((0,photo_top,w,photo_top+photo_h),fill=brand['dark'])
   if g.get('map'):
    points=[(m['x'],photo_top+m['y'],m['label']) for m in g['map_markers']]
    for x,yy,label in points:
     d.ellipse((x-15,yy-15,x+15,yy+15),fill=brand['red']);d.text((x-170,yy+40),label,font=font(27,True),fill='white')
    d.text((pad,photo_top+photo_h-65),'Area diagram · Not to scale',font=font(23),fill='#cccccc')
   else:
    d.text((pad,photo_top+100),g.get('hero_text','LOOK A LITTLE CLOSER'),font=font(94,True),fill='white')
    for j in range(5):d.arc((300+j*40,photo_top+60+j*25,1300+j*70,photo_top+850+j*40),180,315,fill='#666666',width=2)
  by=photo_top+photo_h+35;bodyfont=font(33 if h>1400 else 29)
  for para in g['body'].split('\n'):
   lines=[];line=''
   for word in para.split():
    if d.textlength((line+' '+word).strip(),font=bodyfont)>w-2*pad:lines.append(line);line=word
    else:line=(line+' '+word).strip()
   if line:lines.append(line)
   for line in lines:d.text((pad,by),line,font=bodyfont,fill=brand['dark']);by+=42 if h>1400 else 37
  footer=h-(300 if h>1400 else 170)
  if by>footer-18:raise ValueError('Body overflow: '+g['id'])
  d.line((pad,footer,w-pad,footer),fill=brand['red'],width=3)
  d.text((pad,footer+23),brand['agent']+', REALTOR®',font=font(26,True),fill=brand['dark']);d.text((pad,footer+61),'C '+brand['phone']+' · O '+brand['officePhone'],font=font(22),fill=brand['dark']);d.text((pad,footer+96),brand['website']+' · '+brand.get('licenseLabel','License #')+brand['license'],font=font(20),fill=brand['dark'])
  logo=Image.open(r/'assets'/brand['logo_source']).convert('RGBA');logo.thumbnail((245,62));im.paste(logo,(w-pad-logo.width,footer+22),logo);d.text((w-pad-245,footer+96),brand['brokerage'],font=font(18),fill=brand['dark'])
  out=r/'output/03 Graphics'/g['folder']/f"{g['id']}.png";out.parent.mkdir(parents=True,exist_ok=True);im.save(out)
  manifest.append({**g,'path':str(out),'dimensions':[w,h],'brand_color':brand['red'],'logo_source':'assets/'+brand['logo_source'],'text_bottom':by,'footer_top':footer})
 (r/'working/graphics-layout-manifest.json').write_text(json.dumps(manifest,indent=2));print(f'Rendered {len(manifest)} graphics')
if __name__=='__main__':main()
