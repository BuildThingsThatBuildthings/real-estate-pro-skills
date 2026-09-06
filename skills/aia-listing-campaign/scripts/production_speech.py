#!/usr/bin/env python3
"""Generate reusable licensed-service scene narration; no identity cloning or hidden purchase."""
import argparse,hashlib,json,subprocess,urllib.request,urllib.error,concurrent.futures
from pathlib import Path

def main():
    p=argparse.ArgumentParser();p.add_argument('run');p.add_argument('--env-file',required=True);p.add_argument('--limit',type=int);a=p.parse_args();r=Path(a.run)
    env={line.split('=',1)[0].strip():line.split('=',1)[1].strip().strip('\"').strip("'") for line in Path(a.env_file).read_text().splitlines() if '=' in line and not line.lstrip().startswith('#')}
    key=env['OPENAI_API_KEY'];spec=json.loads((r/'context/audio-production.json').read_text());out=r/'assets/production-voice';out.mkdir(parents=True,exist_ok=True)
    if not spec.get('commercial_use') or not spec.get('rights_source'):
        raise SystemExit('Commercial audio rights must be verified before generating')
    segments={}
    for job in json.loads((r/'working/render-manifest.json').read_text()):
        for s in json.loads(Path(job['props']).read_text())['scenes']:
            if s.get('voice'):
                text=s['voice'];id=hashlib.sha256(text.encode()).hexdigest()[:16];segments[id]=text
    def generate(item):
        id,text=item;path=out/(id+'.wav')
        if path.exists():return {'id':id,'status':'existing','text':text}
        body={'model':spec['model'],'voice':spec['voice'],'input':text,'instructions':spec['direction'],'response_format':'wav'}
        req=urllib.request.Request('https://api.openai.com/v1/audio/speech',data=json.dumps(body).encode(),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'})
        try:
            with urllib.request.urlopen(req,timeout=120) as f:data=f.read()
            path.write_bytes(data);print('Generated scene '+id,flush=True);return {'id':id,'status':'generated','text':text,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
        except urllib.error.HTTPError as e:
            return {'id':id,'status':'failed','http':e.code,'error':e.read().decode()[:300]}
    items=list(segments.items())[:a.limit];results=[]
    # Bounded service calls; terminal quota errors are recorded, never retried or charged via another account.
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        for result in pool.map(generate,items):
            results.append(result);(out/'generation-receipts.json').write_text(json.dumps(results,indent=2))
    if any(x['status']=='failed' for x in results):raise SystemExit('Speech generation has failures; inspect receipts before proceeding')
    print(f'{len(results)} scene narrations available')

if __name__=='__main__':main()
