#!/usr/bin/env python3
"""Full stream decode and sampled visual evidence. Never asserts perceptual playback."""
import argparse, hashlib, json, subprocess
from pathlib import Path
from PIL import Image, ImageDraw

def main():
    ap=argparse.ArgumentParser();ap.add_argument('manifest');ap.add_argument('output');a=ap.parse_args()
    out=Path(a.output);out.mkdir(parents=True,exist_ok=True);results=[]
    for job in json.loads(Path(a.manifest).read_text()):
        p=Path(job['output'])
        if not p.exists():results.append({'id':job['id'],'status':'missing'});continue
        probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_format','-show_streams','-of','json',str(p)]))
        decode=subprocess.run(['ffmpeg','-v','error','-i',str(p),'-f','null','-'],capture_output=True,text=True)
        props=json.loads(Path(job['props']).read_text()); times=[];start=0
        for s in props['scenes']:
            times.append((start+s['frames']/2)/30);start+=s['frames']
        columns=4;cellw=320;cellh=210 if props['width']>props['height'] else 590
        sheet=Image.new('RGB',(columns*cellw,((len(times)+columns-1)//columns)*cellh),'#eeeeee');draw=ImageDraw.Draw(sheet)
        for i,t in enumerate(times):
            frame=out/f"{job['id']}-{i+1:02}.jpg"
            subprocess.run(['ffmpeg','-v','error','-y','-ss',str(t),'-i',str(p),'-frames:v','1','-vf',f'scale={cellw}:-1',str(frame)],check=True)
            im=Image.open(frame);x=(i%columns)*cellw;y=(i//columns)*cellh;sheet.paste(im,(x,y));draw.text((x+8,y+im.height+5),f'Scene {i+1} / {t:.1f}s',fill='black')
        sheet.save(out/f"{job['id']}-scene-sheet.jpg")
        sound=subprocess.run(['ffmpeg','-hide_banner','-i',str(p),'-af','ebur128=peak=true','-f','null','-'],capture_output=True,text=True)
        (out/f"{job['id']}-audio-meter.txt").write_text(sound.stderr[-1800:])
        result={'id':job['id'],'bytes':p.stat().st_size,'sha256':hashlib.file_digest(p.open('rb'),'sha256').hexdigest(),'format':probe['format'],'streams':probe['streams'],'full_decode_pass':decode.returncode==0 and not decode.stderr.strip(),'decode_errors':decode.stderr,'sampled_scene_count':len(times),'full_sound_review':False,'full_muted_review':False}
        results.append(result);(out/'technical-review.json').write_text(json.dumps(results,indent=2));print('Checked '+job['id'],flush=True)
    (out/'technical-review.json').write_text(json.dumps(results,indent=2))

if __name__=='__main__':main()
