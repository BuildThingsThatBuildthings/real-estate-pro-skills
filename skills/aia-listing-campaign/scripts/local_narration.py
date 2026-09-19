#!/usr/bin/env python3
"""Quota-independent narration from a verified Apache-licensed model; scene-aligned output."""
import argparse,json,hashlib,subprocess
from pathlib import Path
import numpy as np
import soundfile as sf
import onnxruntime as ort
from kokoro_onnx import Kokoro
from production_inputs import Inputs

def main():
    ap=argparse.ArgumentParser();ap.add_argument('run');ap.add_argument('--limit',type=int);ap.add_argument('--spec',action='append',help='Repeat for independently authored narration specs with identical model/voice/run');a=ap.parse_args();r=Path(a.run)
    inputs=Inputs()
    specs=[json.loads(inputs.read(path)) for path in (a.spec or [r/'context/local-narration.json'])]
    spec=dict(specs[0])
    if len(specs)>1:
        common=('run_id','model','voices','voice','speed','commercial_use','license_url')
        if any(any(item.get(key)!=spec.get(key) for key in common) for item in specs[1:]):raise ValueError('Narration specs must share exact run, model, voice, speed and license')
        if any(not item.get('narrations') for item in specs):raise ValueError('Multi-spec generation requires independent narration segments')
        spec['narrations']=[film for item in specs for film in item['narrations']]
    if spec.get('narrations') and len({film['composition_id'] for film in spec['narrations']})!=len(spec['narrations']):raise ValueError('Duplicate narration composition ID')
    if not spec.get('commercial_use') or not spec.get('license_url'):raise SystemExit('Model/voice rights not established')
    if not spec.get('run_id'):raise SystemExit('Fresh narration run ID required')
    if inputs.run_id != spec['run_id']:raise SystemExit('Narration and workflow run IDs differ')
    identity = {'run_id':spec['run_id'], 'model_sha256':hashlib.sha256(inputs.read(r/spec['model'])).hexdigest(), 'voices_sha256':hashlib.sha256(inputs.read(r/spec['voices'])).hexdigest(), 'voice':spec['voice'], 'speed':spec.get('speed',1.05), 'language':'en-us'}
    def segment_id(text):return hashlib.sha256(json.dumps({**identity,'text':text},sort_keys=True).encode()).hexdigest()[:24]
    options=ort.SessionOptions();options.intra_op_num_threads=2;options.inter_op_num_threads=1
    session=ort.InferenceSession(str(r/spec['model']),sess_options=options,providers=['CPUExecutionProvider'])
    kokoro=Kokoro.from_session(session,str(r/spec['voices']))
    root=r/'assets/local-narration';root.mkdir(parents=True,exist_ok=True);segments={};jobs=[] if spec.get('narrations') else json.loads(inputs.read(r/'working/render-manifest.json'))
    receipt_path=root/'identity.json'
    if receipt_path.exists() and json.loads(receipt_path.read_text()) != identity:raise SystemExit('Narration directory belongs to different run/model/voice settings')
    if not receipt_path.exists() and any(root.iterdir()):raise SystemExit('Existing unproven narration cache cannot enter fresh run')
    receipt_path.write_text(json.dumps(identity,indent=2))
    for film in spec.get('narrations',[]):
        for scene in film['segments']:
            text=scene['text'];segments[segment_id(text)]=text
    for job in jobs:
        for scene in json.loads(inputs.read(job['props']))['scenes']:
            if scene.get('voice'):
                text=scene['voice'];id=segment_id(text);segments[id]=text
    receipts=[]
    for id,text in list(segments.items())[:a.limit]:
        path=root/(id+'.wav')
        if not path.exists():
            audio,rate=kokoro.create(text,voice=spec['voice'],speed=spec.get('speed',1.05),lang='en-us')
            sf.write(path,audio,rate)
        info=sf.info(path);receipts.append({'id':id,'text':text,'duration':info.duration,'sample_rate':info.samplerate,'voice':spec['voice'],'sha256':hashlib.file_digest(path.open('rb'),'sha256').hexdigest()})
        print('Local narration '+id,flush=True)
        (root/'receipts.json').write_text(json.dumps(receipts,indent=2))
    if a.limit:inputs.finish();return
    if spec.get('narrations'):
        masters=[]
        for film in spec['narrations']:
            cid=film['composition_id']
            if Path(cid).name != cid or cid in ('.','..'):raise ValueError('Invalid composition ID')
            pieces=[];timing=[];offset=0
            for scene in film['segments']:
                audio,rate=sf.read(root/(segment_id(scene['text'])+'.wav'),dtype='float32')
                if rate != 24000:raise ValueError('Unexpected narration sample rate')
                pause=float(scene.get('pause_after',.4))
                if not 0 <= pause <= 10:raise ValueError('Invalid authored speech pause')
                seconds=len(audio)/rate;pieces.extend([audio,np.zeros(round(pause*rate),dtype=np.float32)])
                timing.append({'start':offset,'end':offset+seconds,'text':scene['text']});offset+=seconds+pause
            if not pieces:raise ValueError('Narration segments required')
            output=root/(cid+'.wav');sf.write(output,np.concatenate(pieces),24000)
            master={'composition_id':cid,'path':str(output),'duration':offset,'speech_segments':timing,'run_id':spec['run_id'],'caption_review':'Sentence timing only; split long text into readable authored caption cues and review playback'}
            (root/(cid+'.timing.json')).write_text(json.dumps(master,indent=2));masters.append(master)
        (root/'narration-timelines.json').write_text(json.dumps(masters,indent=2));inputs.finish();print('Fresh narration timelines assembled without speed fitting');return
    aligned=[]
    for job in jobs:
        props=json.loads(inputs.read(job['props']));pieces=[];details=[]
        for i,s in enumerate(props['scenes']):
            duration=s['frames']/30
            if not s.get('voice'):pieces.append(np.zeros(round(duration*24000),dtype=np.float32));continue
            id=segment_id(s['voice']);src=root/(id+'.wav');rawdur=sf.info(src).duration
            target=max(1,duration-(1.4 if i<len(props['scenes'])-1 else 3.5));tempo=rawdur/target
            # Cap speed changes; never silently truncate a spoken line.
            if tempo>1.45:raise RuntimeError(f'{job["id"]} scene {i+1}: narration too long; rewrite or retime scene')
            tempo=max(.8,tempo);piece=root/f'{job["id"]}-{i:02}-fit.wav'
            subprocess.run(['ffmpeg','-v','error','-y','-i',str(src),'-af',f'atempo={tempo},apad,atrim=duration={duration}','-ar','24000','-ac','1',str(piece)],check=True)
            audio,rate=sf.read(piece,dtype='float32');pieces.append(audio);details.append({'scene':i+1,'source_duration':rawdur,'scene_duration':duration,'tempo':tempo,'caption_review':'Scene aligned; word-level sync requires complete playback review'})
        if any(s.get('voice') for s in props['scenes']):sf.write(root/(job['id']+'.wav'),np.concatenate(pieces),24000)
        aligned.append({'id':job['id'],'scenes':details})
    (root/'alignment.json').write_text(json.dumps(aligned,indent=2));inputs.finish();print('Local narration masters assembled')

if __name__=='__main__':main()
