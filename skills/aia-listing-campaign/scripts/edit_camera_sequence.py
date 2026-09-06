#!/usr/bin/env python3
"""Exact edits of reviewed source-camera segments. Does not certify final creative QA."""
import argparse,json,pathlib,subprocess
p=argparse.ArgumentParser();p.add_argument('config');a=p.parse_args();c=json.loads(pathlib.Path(a.config).read_text());root=pathlib.Path(c['working']);root.mkdir(parents=True,exist_ok=True)
if not c.get('music_rights') or not c.get('music_attribution'):raise SystemExit('Document music rights and attribution')
clips=[]
for n,s in enumerate(c['shots']):
 if s.get('status')!='review_candidate':raise SystemExit('Every source segment needs an explicit review-candidate decision')
 duration=float(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','csv=p=0',s['path']]).decode())
 if s['in']<0 or s['seconds']<=0 or s['in']+s['seconds']>duration+.03:raise SystemExit('Invalid segment range')
 out=root/f'clip-{n:02}.mp4';filters=[f"scale={c['width']}:{c['height']}:force_original_aspect_ratio=decrease",f"pad={c['width']}:{c['height']}:(ow-iw)/2:(oh-ih)/2",f"fps={c['fps']}"]
 for j,t in enumerate(s.get('text',[])+[{**t,'color':s.get('brand_color',t.get('color','white'))} for t in c.get('brand_text',[])]):
  f=root/f'text-{n}-{j}.txt';f.write_text(t['text']);filters.append(f"drawtext=fontfile='{c['font']}':textfile='{f}':expansion=none:fontcolor={t.get('color','white')}:fontsize={t['size']}:x={t['x']}:y={t['y']}:line_spacing=4:borderw=1:bordercolor=black@0.3:shadowcolor=black@0.45:shadowx=1:shadowy=2")
 subprocess.run(['ffmpeg','-v','error','-y','-ss',str(s['in']),'-i',s['path'],'-t',str(s['seconds']),'-an','-vf',','.join(filters),'-c:v','libx264','-preset','fast','-crf','18','-pix_fmt','yuv420p',str(out)],check=True);clips.append(out)
listing=root/'concat.txt';listing.write_text('\n'.join("file '"+str(x).replace("'","'\\''")+"'" for x in clips));d=sum(s['seconds'] for s in c['shots']);out=pathlib.Path(c['output']);out.parent.mkdir(parents=True,exist_ok=True)
subprocess.run(['ffmpeg','-v','error','-y','-f','concat','-safe','0','-i',str(listing),'-ss',str(c.get('music_in',0)),'-i',c['music'],'-map','0:v','-map','1:a','-c:v','copy','-af',f'loudnorm=I=-18:TP=-1.5:LRA=9,afade=t=in:d=0.15,afade=t=out:st={d-.8}:d=0.8','-t',str(d),'-c:a','aac','-b:a','192k','-movflags','+faststart',str(out)],check=True)
out.with_suffix('.review.json').write_text(json.dumps({'status':'review_cut','duration':d,'source_config':a.config,'audio':'Licensed music only; source generation audio excluded','attribution':c['music_attribution'],'full_listening':'pending','full_muted_review':'pending'},indent=2));print(out)
