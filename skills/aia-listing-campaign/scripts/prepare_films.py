#!/usr/bin/env python3
"""Prepare brand-driven film props, time-aligned captions, and reusable narrated cutdowns."""
import argparse,copy,json,math,re,shutil,subprocess
from pathlib import Path

def words(t):return re.findall(r"[\w’']+",t.lower())
def clean(ts):return [w for w in ts if not w['word'].startswith('<')]
def boundaries(film,meta):
    ts=clean(meta['word_timestamps']); starts=[]; cursor=0
    # Match each new sentence start in the provider transcript, allowing contractions/tokenization.
    for scene in film['scenes']:
        target=words(scene['voice'])[:5]; found=None
        for i in range(cursor,len(ts)):
            candidate=words(' '.join(w['word'] for w in ts[i:i+8]))
            if candidate[:len(target)]==target:found=i;break
        if found is None:raise ValueError('Cannot align scene: '+scene['voice'])
        starts.append(max(0,ts[found]['start']-.2));cursor=found+1
    starts[0]=0;return starts+[meta['duration']]
def srt_time(t):
    ms=round(t*1000);h,ms=divmod(ms,3600000);m,ms=divmod(ms,60000);s,ms=divmod(ms,1000);return f'{h:02}:{m:02}:{s:02},{ms:03}'
def captions(ts):
    lines=[];group=[]
    for word in clean(ts):
        group.append(word)
        if len(group)>=6 or word['word'].endswith(('.','?','!')):
            lines.append({'start':group[0]['start'],'end':group[-1]['end']+.1,'text':' '.join(w['word'] for w in group)});group=[]
    if group:lines.append({'start':group[0]['start'],'end':group[-1]['end']+.1,'text':' '.join(w['word'] for w in group)})
    return lines
def main():
    ap=argparse.ArgumentParser();ap.add_argument('run');ap.add_argument('engine');a=ap.parse_args();r=Path(a.run);e=Path(a.engine)
    films=json.loads((r/'context/films.json').read_text());brand=json.loads((r/'context/brand.json').read_text());by={f['id']:f for f in films}
    metas={f['id']:json.loads((r/'working'/f"{f['id']}-voice.json").read_text()) for f in films}
    cuts=json.loads((r/'context/cutdowns.json').read_text())
    for fid,spec in cuts.items():
        source=by[spec['source']];meta=metas[spec['source']];bounds=boundaries(source,meta);target=by[fid];new_ts=[];new_scenes=[];offset=0;parts=[]
        for j,idx in enumerate(spec['scenes']):
            begin,end=bounds[idx],bounds[idx+1];out=r/'working'/f'{fid}-{j}.wav'
            subprocess.run(['ffmpeg','-v','error','-y','-ss',str(begin),'-to',str(end),'-i',str(r/'assets'/f"{source['id']}.wav"),'-ar','24000','-ac','1',str(out)],check=True)
            parts.append(out);new_scenes.append(copy.deepcopy(source['scenes'][idx]))
            for w in clean(meta['word_timestamps']):
                if w['start']>=begin and w['end']<=end:new_ts.append({**w,'start':w['start']-begin+offset,'end':w['end']-begin+offset})
            offset+=end-begin
        concat=r/'working'/f'{fid}-concat.txt';concat.write_text('\n'.join(f"file '{p}'" for p in parts))
        subprocess.run(['ffmpeg','-v','error','-y','-f','concat','-safe','0','-i',str(concat),'-c','copy',str(r/'assets'/f'{fid}.wav')],check=True)
        target['scenes']=new_scenes;metas[fid]={'duration':offset,'word_timestamps':new_ts,'provenance':'Edited from '+spec['source']}
    public=e/'public/job';public.mkdir(parents=True,exist_ok=True);shutil.copytree(r/'assets',public,dirs_exist_ok=True)
    mapdata=json.loads((r/'context/map.json').read_text());render=[]
    for film in films:
        meta=metas[film['id']];bounds=boundaries(film,meta);minimum=75 if film['id'] in ('property-film','neighborhood-story') else 45 if film['id']=='launch-reel' else 25
        total=max(minimum,math.ceil(meta['duration']+3)); scenes=[]
        for i,s in enumerate(film['scenes']):
            end=bounds[i+1] if i<len(film['scenes'])-1 else total
            q={**s,'frames':round(end*30)-round(bounds[i]*30)}
            if 'photo' in q:q['photo']=f"job/photos/photo-{q['photo']:02}.webp"
            scenes.append(q)
        caps=captions(meta['word_timestamps']);w,h=(1920,1080) if film['aspect']=='16:9' else (1080,1920)
        props={'width':w,'height':h,'duration':total*30,'brand':brand,'scenes':scenes,'captions':caps,'audio':f"job/{film['id']}.wav",'music':'job/music.wav','map':mapdata}
        out=r/'output'/film['folder'];out.mkdir(parents=True,exist_ok=True)
        p=r/'working'/f"{film['id']}.json";p.write_text(json.dumps(props,indent=2));render.append({'id':film['id'],'props':str(p),'output':str(out/f"{film['id']}.mp4"),'duration':total})
        (out/f"{film['id']}.srt").write_text('\n\n'.join(f"{i+1}\n{srt_time(c['start'])} --> {srt_time(c['end'])}\n{c['text']}" for i,c in enumerate(caps))+'\n')
        (r/'working'/f"{film['id']}-timed-script.json").write_text(json.dumps({'scenes':film['scenes'],'starts':bounds,'meta':meta},indent=2))
        if film['id']=='neighborhood-story':
            pp=copy.deepcopy(props);pp.update(width=1920,height=1080);pp['scenes'][0]['photo']='job/photos/photo-35.webp';pp['scenes'][3]['photo']='job/photos/photo-36.webp';pp['scenes'][8]['photo']='job/photos/photo-06.webp'
            p=r/'working/neighborhood-story-horizontal.json';p.write_text(json.dumps(pp,indent=2));render.append({'id':'neighborhood-story-horizontal','props':str(p),'output':str(out/'neighborhood-story-horizontal.mp4'),'duration':total});shutil.copyfile(out/'neighborhood-story.srt',out/'neighborhood-story-horizontal.srt')
    (r/'working/render-manifest.json').write_text(json.dumps(render,indent=2));print(json.dumps(render,indent=2))
if __name__=='__main__':main()
