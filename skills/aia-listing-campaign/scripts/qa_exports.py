#!/usr/bin/env python3
"""Full stream decode and sampled visual evidence. Never asserts perceptual playback."""
import argparse, hashlib, json, subprocess
from pathlib import Path
from PIL import Image, ImageDraw

def main():
    ap=argparse.ArgumentParser();ap.add_argument('manifest',nargs='?');ap.add_argument('output');ap.add_argument('--audition');ap.add_argument('--start',type=float,default=0);ap.add_argument('--seconds',type=float,default=12);a=ap.parse_args()
    if a.audition:
        if a.start<0 or not 0<a.seconds<=120:ap.error('Audition needs a nonnegative start and 1–120 seconds')
        target=Path(a.output);target.parent.mkdir(parents=True,exist_ok=True)
        subprocess.run(['ffmpeg','-v','error','-nostdin','-y','-ss',str(a.start),'-i',a.audition,'-t',str(a.seconds),'-vn','-ac','1','-ar','24000','-c:a','libmp3lame','-b:a','48k',str(target)],check=True)
        print('Private listening excerpt: '+str(target));return
    if not a.manifest:ap.error('A manifest is required for video QA')
    out=Path(a.output).resolve()
    if any(p.name in ('output','delivery','handoff') for p in (out,*out.parents)):raise ValueError('Technical QA records belong outside client delivery')
    out.mkdir(parents=True,exist_ok=True);results=[]
    for job in json.loads(Path(a.manifest).read_text()):
        p=Path(job['output'])
        if not p.exists():results.append({'id':job['id'],'status':'missing'});continue
        probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_format','-show_streams','-of','json',str(p)]))
        decode=subprocess.run(['ffmpeg','-v','error','-i',str(p),'-f','null','-'],capture_output=True,text=True)
        props=json.loads(Path(job.get('props') or job['config']).read_text()); times=[];start=0
        if 'shots' in props:
            for s in props['shots']:
                seconds=float(s['seconds']);times.append(start+seconds/2);start+=seconds
        elif 'scenes' in props:
            for s in props['scenes']:
                seconds=s['frames']/float(props.get('fps',30));times.append(start+seconds/2);start+=seconds
        else:
            duration=float(probe['format']['duration']);times=[duration*.1,duration*.5,duration*.9]
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
