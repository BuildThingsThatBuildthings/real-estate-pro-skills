#!/usr/bin/env python3
"""Execute ready local production steps; a failed branch never stops unrelated work.

Private workflow JSON holds argv arrays, dependencies and expected output paths.
External account agreements, publishing and full creative reviews stay manual.
Command success establishes execution only, never creative acceptance.
"""
import argparse, datetime, hashlib, json, subprocess
from pathlib import Path

def save(path, data):
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(data,indent=2));temp.replace(path)

def execute(path):
    path=Path(path);flow=json.loads(path.read_text());root=Path(flow['root']).resolve()
    tasks=flow['tasks'];ids={t['id']:t for t in tasks}
    if len(ids)!=len(tasks):raise ValueError('Duplicate task IDs')
    for t in tasks:
        if any(d not in ids for d in t.get('depends_on',[])):raise ValueError('Unknown dependency: '+t['id'])
        if t.get('command') and (not isinstance(t['command'],list) or not all(isinstance(a,str) for a in t['command'])):raise ValueError('Use argv arrays, not shell command text')
        if not t.get('skill'):raise ValueError('Task must name its governing AIA skill')
    logs=root/'working/workflow-logs';logs.mkdir(parents=True,exist_ok=True)
    progress=True
    while progress:
        progress=False
        for t in tasks:
            if t.get('status','pending')!='pending' or not t.get('command'):continue
            if any(ids[d].get('status')!='executed' for d in t.get('depends_on',[])):continue
            t['status']='running';save(path,flow)
            result=subprocess.run(t['command'],cwd=root,text=True,capture_output=True)
            (logs/(t['id']+'.log')).write_text(result.stdout+'\n'+result.stderr)
            missing=[p for p in t.get('outputs',[]) if not (root/p).is_file()]
            t['status']='executed' if result.returncode==0 and not missing else 'failed'
            t['exit_code']=result.returncode;t['missing_outputs']=missing
            t['executed_at']=datetime.datetime.now(datetime.timezone.utc).isoformat()
            if t['status']=='executed':
                t['hashes']={p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in t.get('outputs',[])}
            save(path,flow);print(t['id']+': '+t['status'],flush=True);progress=True
    unfinished=[t['id'] for t in tasks if t.get('status')!='executed']
    flow['execution_summary']={'unfinished':unfinished,'creative_acceptance':'separate required review; execution is not approval'};save(path,flow)
    return flow

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('workflow');a=p.parse_args();f=execute(a.workflow)
    print(json.dumps(f['execution_summary'],indent=2))
