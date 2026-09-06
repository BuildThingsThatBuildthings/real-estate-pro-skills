#!/usr/bin/env python3
"""Remove all rejected audio and attach a rights-cleared score to visual REVIEW cuts."""
import argparse,json,subprocess,hashlib
from pathlib import Path

def main():
    p=argparse.ArgumentParser();p.add_argument('run');a=p.parse_args();r=Path(a.run)
    spec=json.loads((r/'context/music-review.json').read_text())
    if spec.get('rights')!='licensed' or not spec.get('license_url') or not spec.get('attribution'):raise SystemExit('Music rights evidence missing')
    receipts=[]
    for job in json.loads((r/'working/render-manifest.json').read_text()):
        src=Path(job['output']);dst=src.with_name(src.stem+'--visual-review.mp4')
        if not src.exists():continue
        duration=float(job['duration']);tmp=dst.with_suffix('.partial.mp4')
        # Map video only from the evaluation export. Never carry its audio into delivery.
        subprocess.run(['ffmpeg','-v','error','-y','-i',str(src),'-i',str(r/spec['path']),'-map','0:v:0','-map','1:a:0','-c:v','copy','-af',f"atrim=0:{duration},asetpts=PTS-STARTPTS,loudnorm=I=-24:TP=-2:LRA=9,afade=t=in:st=0:d=1.5,afade=t=out:st={max(0,duration-3)}:d=3",'-c:a','aac','-b:a','192k','-t',str(duration),'-movflags','+faststart',str(tmp)],check=True)
        tmp.replace(dst)
        receipts.append({'id':job['id'],'output':str(dst),'status':'visual_review_awaiting_narration','source_audio_removed':True,'music_source':spec['path'],'license_url':spec['license_url'],'attribution':spec['attribution'],'sha256':hashlib.file_digest(dst.open('rb'),'sha256').hexdigest()})
        print('Music-only visual review: '+job['id'],flush=True)
    (r/'working/music-review-receipts.json').write_text(json.dumps(receipts,indent=2))

if __name__=='__main__':main()
