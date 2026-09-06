#!/usr/bin/env python3
"""Quota-independent narration from a verified Apache-licensed model; scene-aligned output."""
import argparse,json,hashlib,subprocess
from pathlib import Path
import numpy as np
import soundfile as sf
import onnxruntime as ort
from kokoro_onnx import Kokoro

def main():
    ap=argparse.ArgumentParser();ap.add_argument('run');ap.add_argument('--limit',type=int);a=ap.parse_args();r=Path(a.run)
    spec=json.loads((r/'context/local-narration.json').read_text())
    if not spec.get('commercial_use') or not spec.get('license_url'):raise SystemExit('Model/voice rights not established')
    options=ort.SessionOptions();options.intra_op_num_threads=2;options.inter_op_num_threads=1
    session=ort.InferenceSession(str(r/spec['model']),sess_options=options,providers=['CPUExecutionProvider'])
    kokoro=Kokoro.from_session(session,str(r/spec['voices']))
    root=r/'assets/local-narration';root.mkdir(parents=True,exist_ok=True);segments={};jobs=json.loads((r/'working/render-manifest.json').read_text())
    for job in jobs:
        for scene in json.loads(Path(job['props']).read_text())['scenes']:
            if scene.get('voice'):
                text=scene['voice'];id=hashlib.sha256(text.encode()).hexdigest()[:16];segments[id]=text
    receipts=[]
    for id,text in list(segments.items())[:a.limit]:
        path=root/(id+'.wav')
        if not path.exists():
            audio,rate=kokoro.create(text,voice=spec['voice'],speed=spec.get('speed',1.05),lang='en-us')
            sf.write(path,audio,rate)
        info=sf.info(path);receipts.append({'id':id,'text':text,'duration':info.duration,'sample_rate':info.samplerate,'voice':spec['voice'],'sha256':hashlib.file_digest(path.open('rb'),'sha256').hexdigest()})
        print('Local narration '+id,flush=True)
        (root/'receipts.json').write_text(json.dumps(receipts,indent=2))
    if a.limit:return
    aligned=[]
    for job in jobs:
        props=json.loads(Path(job['props']).read_text());pieces=[];details=[]
        for i,s in enumerate(props['scenes']):
            duration=s['frames']/30
            if not s.get('voice'):pieces.append(np.zeros(round(duration*24000),dtype=np.float32));continue
            id=hashlib.sha256(s['voice'].encode()).hexdigest()[:16];src=root/(id+'.wav');rawdur=sf.info(src).duration
            target=max(1,duration-(1.4 if i<len(props['scenes'])-1 else 3.5));tempo=rawdur/target
            # Cap speed changes; never silently truncate a spoken line.
            if tempo>1.45:raise RuntimeError(f'{job["id"]} scene {i+1}: narration too long; rewrite or retime scene')
            tempo=max(.8,tempo);piece=root/f'{job["id"]}-{i:02}-fit.wav'
            subprocess.run(['ffmpeg','-v','error','-y','-i',str(src),'-af',f'atempo={tempo},apad,atrim=duration={duration}','-ar','24000','-ac','1',str(piece)],check=True)
            audio,rate=sf.read(piece,dtype='float32');pieces.append(audio);details.append({'scene':i+1,'source_duration':rawdur,'scene_duration':duration,'tempo':tempo,'caption_review':'Scene aligned; word-level sync requires complete playback review'})
        if any(s.get('voice') for s in props['scenes']):sf.write(root/(job['id']+'.wav'),np.concatenate(pieces),24000)
        aligned.append({'id':job['id'],'scenes':details})
    (root/'alignment.json').write_text(json.dumps(aligned,indent=2));print('Local narration masters assembled')

if __name__=='__main__':main()
