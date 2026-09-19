#!/usr/bin/env python3
"""Record an AIA tool/agent operation honestly; evidence is inspected, not cryptographic proof."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

from run_storage import validate_root

BUNDLE = Path(__file__).resolve().parents[3]

def digest(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def now():return datetime.now(timezone.utc).isoformat()

def stamp(value):
    dt=datetime.fromisoformat(value.replace('Z','+00:00'))
    if dt.tzinfo is None:raise ValueError('Evidence times must include timezone')
    return dt.timestamp()

def private(root,path):
    path=(root/path).resolve()
    if not path.is_relative_to(root/'working'):raise ValueError('External operation records stay in private working storage')
    return path

def output_path(root,path):
    result=(root/path).resolve()
    if not result.is_relative_to(root) or result==root:raise ValueError('External output must remain inside fresh run')
    return result

def skill_file(name):
    if not re.fullmatch(r'[a-z0-9-]+',name):raise ValueError('Invalid installed skill name')
    path=BUNDLE/('content-machine' if name=='content-machine' else 'skills/'+name)/'SKILL.md'
    if not path.is_file():raise ValueError('Installed AIA skill missing')
    return path

def save(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(data,indent=2));temp.replace(path)

def begin(spec,record_path):
    if not spec.get('run_id') or not re.fullmatch(r'[A-Za-z0-9_-]+',spec.get('task_id','')):
        raise ValueError('Current run and simple task ID required')
    if spec.get('operation') not in ('agent_authoring','provider_generation'):
        raise ValueError('Unsupported external AIA operation')
    root=validate_root(spec['root'],spec.get('scope','production'));record_path=private(root,record_path)
    if record_path.exists():raise ValueError('External operation already began; do not reset provenance')
    if not spec.get('inputs') or not spec.get('outputs'):raise ValueError('Declared sources and outputs required')
    inputs=[];seen=set()
    for item in spec['inputs']:
        item=dict(item);path=(root/item['path']).resolve()
        if path in seen:raise ValueError('Duplicate external source')
        seen.add(path)
        if not path.is_file() or digest(path)!=item.get('sha256'):raise ValueError('Source missing or changed before operation')
        if item.get('origin')=='generated':
            if item.get('run_id')!=spec['run_id'] or not item.get('producer_task'):raise ValueError('Generated source needs current-run producer identity')
        elif item.get('origin')!='original' or not item.get('source_id'):raise ValueError('Original source identity required')
        inputs.append({**item,'path':str(path)})
    outputs=[]
    for value in spec['outputs']:
        path=output_path(root,value)
        if path==record_path:raise ValueError('Operation record cannot also be a generated output')
        if path.exists():raise ValueError('Output already exists before external operation')
        value=str(path.relative_to(root))
        if value in outputs:raise ValueError('Duplicate external output')
        outputs.append(value)
    record={'scope':spec.get('scope','production'),'run_id':spec['run_id'],'task_id':spec['task_id'],'skill':spec['skill'],'skill_sha256':digest(skill_file(spec['skill'])),'verifier_sha256':digest(__file__),'operation':spec['operation'],'root':str(root),'inputs':inputs,'outputs':outputs,'started_at':now(),'status':'awaiting_external_action','output_absence_checked':True}
    save(record_path,record);return record

def inspect_evidence(record,evidence_path):
    root=Path(record['root']).resolve();evidence_path=private(root,evidence_path)
    evidence=json.loads(evidence_path.read_text());start=stamp(record['started_at'])
    if evidence.get('run_id')!=record['run_id'] or evidence.get('task_id')!=record['task_id']:raise ValueError('External evidence belongs to another run/task')
    if not evidence.get('tool') or not evidence.get('action_id'):raise ValueError('Concrete external tool action evidence required')
    if not start<=stamp(evidence['recorded_at'])<=datetime.now(timezone.utc).timestamp()+5:raise ValueError('Evidence predates operation or is future-dated')
    review=evidence.get('inspection',{})
    if not review.get('reviewer') or review.get('outcome')!='accepted' or not start<=stamp(review['reviewed_at'])<=datetime.now(timezone.utc).timestamp()+5:
        raise ValueError('Actual tool/output inspection required; metadata alone is insufficient')
    if record['operation']=='provider_generation':
        provider=evidence.get('provider',{})
        if not provider.get('job_id'):raise ValueError('Provider generation requires submitted job ID')
        if not start<=stamp(provider['submitted_at'])<=stamp(provider['completed_at'])<=min(stamp(evidence['recorded_at']),stamp(review['reviewed_at'])):raise ValueError('Provider job did not complete before evidence and inspection')
    expected={i['path']:i['sha256'] for i in record['inputs']}
    supplied={str((root/p).resolve()):h for p,h in evidence.get('source_hashes',{}).items()}
    if expected!=supplied:raise ValueError('External action source hashes differ')
    for path,value in expected.items():
        if digest(path)!=value:raise ValueError('External source changed during operation')
    artifacts={}
    for item in evidence.get('outputs',[]):
        path=output_path(root,item['path']);relative=str(path.relative_to(root))
        if relative in artifacts:raise ValueError('Duplicate evidenced artifact')
        if not path.is_file() or path.stat().st_mtime < start-2 or digest(path)!=item.get('sha256'):raise ValueError('External artifact missing, stale or altered')
        artifacts[relative]=item['sha256']
    if set(artifacts)!=set(record['outputs']):raise ValueError('External result does not match expected outputs')
    files={}
    for value in evidence.get('evidence_files',[]):
        path=private(root,value)
        if not path.is_file() or path.stat().st_size==0 or path==evidence_path or path.stat().st_mtime < start-2:raise ValueError('Fresh actual tool response/job evidence file required')
        files[str(path)]=digest(path)
    if not files:raise ValueError('No concrete tool response, transcript or job screenshot supplied')
    return {'consumed':record['inputs'],'hashes':artifacts,'evidence_path':str(evidence_path),'evidence_sha256':digest(evidence_path),'evidence_files':files,'provider_job_id':evidence.get('provider',{}).get('job_id'),'inspection':review,'verification_limit':'Inspected tool evidence and matching bytes; metadata cannot cryptographically prove external-service execution.'}

def complete(record_path,evidence_path):
    record_path=Path(record_path).resolve();record=json.loads(record_path.read_text())
    private(validate_root(record['root'],record.get('scope','production')),record_path)
    if record.get('status')!='awaiting_external_action' or not record.get('output_absence_checked'):raise ValueError('Begin must precede action; completed records cannot be replaced')
    if digest(skill_file(record['skill']))!=record['skill_sha256']:raise ValueError('Governing AIA skill changed during operation')
    if digest(__file__)!=record.get('verifier_sha256'):raise ValueError('External verifier changed during operation')
    result=inspect_evidence(record,evidence_path)
    record.update(result,status='externally_verified',verified_at=now())
    save(record_path,record);return record

def verify(record_path,expected_run_id=None):
    record_path=Path(record_path).resolve();record=json.loads(record_path.read_text())
    private(validate_root(record['root'],record.get('scope','production')),record_path)
    if record.get('status')!='externally_verified' or not record.get('output_absence_checked'):raise ValueError('External operation is not verified')
    if expected_run_id and record['run_id']!=expected_run_id:raise ValueError('External operation belongs to another run')
    if digest(skill_file(record['skill']))!=record['skill_sha256']:raise ValueError('External skill revision changed')
    if digest(__file__)!=record.get('verifier_sha256'):raise ValueError('External verifier changed after operation')
    result=inspect_evidence(record,record['evidence_path'])
    for key in ('consumed','hashes','evidence_sha256','evidence_files'):
        if result[key]!=record.get(key):raise ValueError('External evidence or output changed after verification')
    return record

if __name__=='__main__':
    parser=argparse.ArgumentParser();sub=parser.add_subparsers(dest='action',required=True)
    p=sub.add_parser('begin');p.add_argument('spec');p.add_argument('record')
    p=sub.add_parser('complete');p.add_argument('record');p.add_argument('evidence')
    p=sub.add_parser('verify');p.add_argument('record');p.add_argument('--run-id')
    args=parser.parse_args()
    result=begin(json.loads(Path(args.spec).read_text()),args.record) if args.action=='begin' else complete(args.record,args.evidence) if args.action=='complete' else verify(args.record,args.run_id)
    print(json.dumps({'task_id':result['task_id'],'status':result['status']},indent=2))
