#!/usr/bin/env python3
"""Create delivery masters from source video and separately rights-cleared sound."""
import argparse,json,subprocess,hashlib,shutil
from PIL import Image,ImageDraw,ImageFont
from pathlib import Path

def main():
    p=argparse.ArgumentParser();p.add_argument('run');a=p.parse_args();r=Path(a.run)
    music=json.loads((r/'context/music-review.json').read_text());voice=json.loads((r/'context/local-narration.json').read_text())
    if music.get('rights')!='licensed' or not music.get('license_url') or not voice.get('commercial_use'):raise SystemExit('Audio rights gate failed')
    receipts=[]
    for job in json.loads((r/'working/render-manifest.json').read_text()):
        src=Path(job['output']);props=json.loads(Path(job['props']).read_text());dst=r/'delivery'/src.relative_to(r/'output');dst.parent.mkdir(parents=True,exist_ok=True)
        if not src.exists():raise RuntimeError('Missing visual export: '+job['id'])
        narration=r/'assets/local-narration'/(job['id']+'.wav');spoken=any(s.get('voice') for s in props['scenes'])
        if spoken and not narration.exists():raise RuntimeError('Missing licensed narration: '+job['id'])
        duration=float(job['duration']);cmd=['ffmpeg','-v','error','-y','-i',str(src),'-i',str(r/music['path'])]
        if spoken:cmd += ['-i',str(narration)]
        repair=props.get('header_repair_ranges',[])
        if repair:
            im=Image.new('RGBA',(1000,45));draw=ImageDraw.Draw(im);font=ImageFont.truetype(str(r/'working/inter-700.ttf'),23);x=0
            for ch in props['brand']['name'].upper():draw.text((x,0),ch,font=font,fill='white');x+=draw.textlength(ch,font=font)+3
            overlay=r/'working/header-repair.png';im.save(overlay);cmd+=['-i',str(overlay)]
        level=-29 if spoken else -20
        filt=f'[1:a]atrim=0:{duration},asetpts=PTS-STARTPTS,loudnorm=I={level}:TP=-3:LRA=9,afade=t=in:st=0:d=1.5,afade=t=out:st={max(0,duration-3)}:d=3[m];'
        if spoken:filt+=f'[2:a]loudnorm=I=-17:TP=-2:LRA=9,apad,atrim=0:{duration}[n];[n][m]amix=inputs=2:normalize=0,alimiter=limit=0.891:level=false[a]'
        else:filt+='[m]anull[a]'
        tmp=dst.with_suffix('.partial.mp4')
        video='0:v:0';vcodec=['-c:v','copy']
        if repair:
            idx=3 if spoken else 2;condition='+'.join(f'between(t,{start},{end})' for start,end in repair);filt+=f";[0:v][{idx}:v]overlay=84:66:enable='{condition}'[v]";video='[v]';vcodec=['-c:v','libx264','-preset','ultrafast','-crf','19','-threads','2']
        cmd += ['-filter_complex',filt,'-map',video,'-map','[a]',*vcodec,'-c:a','aac','-b:a','192k','-t',str(duration),'-metadata','comment=AI-generated narrator; not the agent voice. '+music['attribution'],'-movflags','+faststart',str(tmp)]
        subprocess.run(cmd,check=True);tmp.replace(dst)
        for suffix in ['.cover.png','.srt']:
            side=src.with_suffix(suffix)
            if side.exists():shutil.copyfile(side,dst.with_suffix(suffix))
        receipts.append({'id':job['id'],'output':str(dst),'status':'rendered_awaiting_playback_review','source_audio_excluded':True,'narration':str(narration) if spoken else None,'voice':voice['voice'] if spoken else None,'music_license':music['license_url'],'sha256':hashlib.file_digest(dst.open('rb'),'sha256').hexdigest()})
        (r/'working/final-mix-receipts.json').write_text(json.dumps(receipts,indent=2));print('Delivery master '+job['id'],flush=True)

if __name__=='__main__':main()
