#!/usr/bin/env python3
"""Verify delivered bytes, caption bounds, brand pixels and layout; not playback."""
import argparse, hashlib, importlib.util, json, re, subprocess, sys
from pathlib import Path
from PIL import Image

def main():
    ap=argparse.ArgumentParser();ap.add_argument('run');a=ap.parse_args();r=Path(a.run)
    out=r/'working/review/handoff';out.mkdir(parents=True,exist_ok=True)
    brand=json.loads((r/'context/brand.json').read_text());errors=[];video=[]
    for j in json.loads((r/'working/delivery-manifest.json').read_text()):
        p=Path(j['output']);props=json.loads(Path(j['props']).read_text())
        duration=float(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','csv=p=0',str(p)]))
        srt=Path(j['subtitles']) if j.get('subtitles') else r/'working/subtitles'/f"{j['id']}.srt";cues=[]
        if any(s.get('voice') for s in props['scenes']) and not j['id'].startswith('teaser'):
            if not srt.exists():errors.append(j['id']+': missing subtitles')
            else:
                blocks=srt.read_text().strip().split('\n\n')
                def seconds(t):
                    h,m,s,ms=map(int,re.split('[:,]',t));return h*3600+m*60+s+ms/1000
                for b in blocks:
                    lines=b.splitlines();start,end=map(seconds,lines[1].split(' --> '));cues.append((start,end,' '.join(lines[2:])))
                    if not 0<=start<end<=duration+0.05:errors.append(j['id']+': caption outside duration')
                normalize=lambda s:re.sub(r'[^a-z0-9]','',s.lower())
                if normalize(' '.join(c[2] for c in cues))!=normalize(' '.join(s.get('voice','') for s in props['scenes'])):errors.append(j['id']+': subtitle/script mismatch')
        overlaps=sum(cues[i][1]>cues[i+1][0] for i in range(len(cues)-1))
        video.append({'id':j['id'],'duration':duration,'subtitle_cues':len(cues),'overlapping_cues':overlaps,'clean_cover_exists':p.with_suffix('.cover.png').exists(),'word_sync_review':'pending full playback'})
    sys.path.insert(0,str(Path(__file__).parents[2]/'content-foundry/scripts'))
    from brand_lint import close,text_pixel_fraction
    from brandkit import hex_to_rgb,contrast_ratio
    graphics=[]
    for g in json.loads((r/'working/graphics-layout-manifest.json').read_text()):
        p=Path(g['path']);im=Image.open(p).convert('RGB');w,h=im.size;footer=g['footer_top'];pad=76
        logo=Image.open(r/g['logo_source']).convert('RGBA');logo.thumbnail((245,62));x=w-pad-logo.width;y=footer+22
        points=[(i,j) for i in range(0,logo.width,max(1,logo.width//20)) for j in range(0,logo.height,max(1,logo.height//8)) if logo.getpixel((i,j))[3]>200]
        expected=Image.new('RGB',logo.size,brand['paper']);expected.paste(logo,(0,0),logo)
        match=sum(close(im.getpixel((x+i,y+j)),expected.getpixel((i,j)),tol=3) for i,j in points)/max(1,len(points))
        checks={'size_matches':list(im.size)==g['dimensions'],'accent_matches':close(im.getpixel((20,4)),hex_to_rgb(brand['red']),tol=0),'logo_pixel_match':match,'body_above_footer':g['text_bottom']<footer-18,'footer_type_present':text_pixel_fraction(im,(pad,footer+20,700,footer+120),hex_to_rgb(brand['dark']))>0.01}
        if not all([checks['size_matches'],checks['accent_matches'],match>0.99,checks['body_above_footer'],checks['footer_type_present']]):errors.append(g['id']+': brand pixel/layout check')
        graphics.append({'id':g['id'],**checks})
    result={'pass':not errors,'errors':errors,'videos':video,'graphics':graphics,'body_contrast':contrast_ratio(hex_to_rgb(brand['dark']),hex_to_rgb(brand['paper'])),'limits':['Brand pixel checks reuse Content Foundry helpers; legal/broker language approval and the legacy Tier-2 composite-manifest gate remain separate.','Caption text and bounds checks do not certify pronunciation or word synchronization.','No perceptual sound or full muted playback assertion.']}
    (out/'handoff-checks.json').write_text(json.dumps(result,indent=2));print(json.dumps({'pass':not errors,'errors':errors,'videos':len(video),'graphics':len(graphics),'overlapping_subtitle_cues':sum(v['overlapping_cues'] for v in video)},indent=2))
    raise SystemExit(bool(errors))
if __name__=='__main__':main()
