#!/usr/bin/env python3
"""Compose photograph-led campaign graphics from explicit private art direction.

No generated property pixels. Layout, crops and all copy live in the run manifest.
Writes layer evidence and refuses missing rights, text overflow and off-canvas type.
"""
import argparse, hashlib, io, json, re, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'content-foundry/scripts'))
from brandkit import AgentBrand, contrast_ratio, hex_to_rgb
from composite import region_worst
from production_inputs import Inputs

def render(spec, root, inputs):
    root = Path(root).resolve()
    run_id = inputs.run_id
    if not run_id or spec.get('run_id') != run_id:
        raise ValueError('An active matching run_id is required for photo production')
    if not re.fullmatch(r'[A-Za-z0-9_-]+', spec['id']):
        raise ValueError('Design id must be a safe filename')
    out = (root/spec['output']).resolve()
    if not out.is_relative_to(root/'output') or out.suffix.lower() != '.png':
        raise ValueError('Photo designs must export PNG inside the run output folder')
    for name in ('brand-context-visual.md', 'brand-context-compliance.md'):
        inputs.read(root/'agents'/spec['agent']/name)
    W,H=spec['size']; im=Image.new('RGBA',(W,H),spec.get('background','#171717'))
    evidence=[]; brand=AgentBrand(root/'agents'/spec['agent']); compliance=brand.required_strings(); audit=[]
    for layer in spec['layers']:
        kind=layer['type']; box=layer.get('box',[0,0,W,H]); x,y,x2,y2=map(int,box)
        if kind in ('photo','logo'):
            p=(root/layer['path']).resolve()
            if layer.get('rights') not in ('authorized','licensed','original') or not layer.get('rights_basis'):
                raise ValueError(f"{spec['id']}: missing rights for {p.name}")
            if p == out:
                raise ValueError('Cannot overwrite an input image')
            source_bytes = inputs.read(p)
            source_hash = hashlib.sha256(source_bytes).hexdigest()
            src=Image.open(io.BytesIO(source_bytes)).convert('RGBA')
            if kind=='photo':
                if 'source_box' in layer:
                    bounds = layer['source_box']
                    if len(bounds) != 4 or not all(isinstance(v, (int, float)) for v in bounds):
                        raise ValueError('Source box requires four pixel coordinates')
                    sx, sy, ex, ey = bounds
                    if not (0 <= sx < ex <= src.width and 0 <= sy < ey <= src.height):
                        raise ValueError('Source box exceeds original photograph')
                    src = src.crop(tuple(bounds))
                tile=ImageOps.fit(src,(x2-x,y2-y),Image.Resampling.LANCZOS,centering=tuple(layer.get('focal',[.5,.5])))
            else:
                tile=ImageOps.contain(src,(x2-x,y2-y),Image.Resampling.LANCZOS)
            im.alpha_composite(tile,(x,y))
            evidence.append({**layer,'source_sha256':source_hash,'source_path':str(p),'actual_size':list(tile.size)})
            if kind=='logo': audit.append({'type':'logo','source':str(p),'box':[x,y,x+tile.width,y+tile.height],'width':tile.width})
        elif kind=='gradient':
            overlay=Image.new('RGBA',(W,H)); d=ImageDraw.Draw(overlay)
            rgb=tuple(bytes.fromhex(layer.get('color','#171717').lstrip('#')))
            a0,a1=layer.get('alpha',[0,235])
            for row in range(y,y2):
                t=(row-y)/max(1,y2-y-1)
                d.line((x,row,x2,row),fill=(*rgb,round(a0+(a1-a0)*t)))
            im=Image.alpha_composite(im,overlay); evidence.append(layer)
        elif kind in ('rect','line'):
            d=ImageDraw.Draw(im); d.rectangle(box,fill=layer['color']); evidence.append(layer)
        elif kind=='text':
            background=im.copy();d=ImageDraw.Draw(im); font=ImageFont.truetype(io.BytesIO(inputs.read(root/layer['font'])),layer['size'])
            lines=layer['text'].split('\n'); leading=layer.get('leading',round(layer['size']*1.16)); boxes=[]
            for n,line in enumerate(lines):
                yy=y+n*leading
                b=d.textbbox((x,yy),line,font=font,anchor='lt')
                if b[2]>x2 or b[3]>y2 or b[0]<0 or b[1]<0 or b[2]>W or b[3]>H:
                    raise ValueError(f"{spec['id']}: text overflow {line!r}: {b} outside {box}")
                d.text((x,yy),line,font=font,fill=layer.get('color','#FFFFFF'),anchor='lt'); boxes.append(list(b))
            evidence.append({**layer,'actual_boxes':boxes})
            audit.append({'type':'headline' if layer.get('role')=='headline' else 'text','text':layer['text'],'box':[min(b[0] for b in boxes),min(b[1] for b in boxes),max(b[2] for b in boxes),max(b[3] for b in boxes)]})
            for field,value in compliance.items():
                if not value: continue
                for n,line in enumerate(lines):
                    if value not in line: continue
                    xx=x+round(d.textlength(line[:line.index(value)],font=font));yy=y+n*leading
                    cb=list(d.textbbox((xx,yy),value,font=font,anchor='lt'))
                    ink=hex_to_rgb(brand.colors['text-on-dark']);ratio=contrast_ratio(ink,region_worst(background,cb,ink))
                    audit.append({'type':'compliance','field':field,'text':value,'box':cb,'font_size':layer['size'],'contrast':round(ratio,2)})
        else: raise ValueError('Unknown layer '+kind)
    present=' '.join(layer.get('text','') for layer in spec['layers']).casefold()
    missing=[field for field,value in compliance.items() if value and value.casefold() not in present]
    if missing or not any(layer['type']=='logo' for layer in spec['layers']):
        raise ValueError(f"{spec['id']}: missing required brand footer elements {missing}")
    out.parent.mkdir(parents=True,exist_ok=True)
    temp=out.with_suffix('.tmp');im.convert('RGB').save(temp,format='PNG');temp.replace(out)
    receipt={**spec,'run_id':run_id,'consumed':list(inputs.consumed.values()),'rendered_layers':evidence,'sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'status':'rendered_unreviewed'}
    (root/'working/design-receipts').mkdir(parents=True,exist_ok=True)
    (root/'working/design-receipts'/f"{spec['id']}.json").write_text(json.dumps(receipt,indent=2))
    (root/'working/design-receipts'/f"{spec['id']}.composite.json").write_text(json.dumps({'agent':brand.slug,'size':[W,H],'safe_zone':spec['safe_zone'],'colors':brand.colors,'elements':audit,'warnings':[]},indent=2))
    return str(out)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('manifest');p.add_argument('--only');a=p.parse_args()
    inputs=Inputs();mp=Path(a.manifest);data=json.loads(inputs.read(mp));root=Path(data['root'])
    for item in data['designs']:
        if not a.only or item['id']==a.only: print(render(item,root,inputs))
    inputs.finish()
