#!/usr/bin/env python3
"""Install the audited four-skill starter without overwriting existing files."""
import argparse, hashlib, json, shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def digest_tree(path):
    result={}
    for p in sorted(path.rglob('*')):
        if p.is_symlink(): raise ValueError('Skill package contains a symlink: '+str(p))
        if p.is_file(): result[str(p.relative_to(path))]=hashlib.sha256(p.read_bytes()).hexdigest()
    return result

def install(root, target, apply=False):
    manifest=json.loads((root/'starter/manifest.json').read_text())
    target=target.expanduser().absolute()
    if target.is_symlink() or target.parent.is_symlink(): raise ValueError('Use a destination without symlinked parents.')
    operations=[]
    for skill in manifest['skills']:
        name=skill['name']
        if not name.startswith('aia-') or '/' in name or '..' in name: raise ValueError('Invalid skill name.')
        src=root/'skills'/name
        if src.resolve().parent != (root/'skills').resolve() or not (src/'SKILL.md').is_file(): raise ValueError('Invalid skill source.')
        expected=digest_tree(src);dest=target/name
        if dest.is_symlink(): state='conflict'
        elif dest.exists(): state='unchanged' if dest.is_dir() and digest_tree(dest)==expected else 'conflict'
        else: state='install'
        operations.append({'name':name,'state':state,'destination':str(dest),'files':expected})
    if apply and any(o['state']=='conflict' for o in operations): raise ValueError('Existing skills differ. Nothing was changed. Review or back up those folders before reinstalling.')
    created=[]
    if apply:
        target.mkdir(parents=True,exist_ok=True)
        try:
            for o in operations:
                if o['state']=='install':
                    dest=Path(o['destination']);shutil.copytree(root/'skills'/o['name'],dest);created.append(dest)
                    if digest_tree(dest)!=o['files']: raise ValueError('Readback verification failed.')
        except Exception:
            for dest in created: shutil.rmtree(dest)
            raise
    return {'schema':'aia-skill-install-receipt/v1','version':manifest['version'],'applied':apply,
            'verification':'files-read-back' if apply else 'dry-run-only','skills':operations,
            'next':'Restart or refresh skill discovery in your AI if required, then invoke one skill and run the fictional practice task. File verification does not prove the host loaded the skill.'}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--agent',choices=['claude','codex'],required=True)
    p.add_argument('--workspace',type=Path,required=True,help='Existing project/workspace chosen by the member.')
    p.add_argument('--apply',action='store_true',help='Install after reviewing the default dry-run.')
    p.add_argument('--receipt',type=Path)
    args=p.parse_args()
    if not args.workspace.is_dir(): p.error('Choose an existing workspace.')
    target=args.workspace/('.claude/skills' if args.agent=='claude' else '.agents/skills')
    try: result=install(ROOT,target,args.apply)
    except (ValueError,OSError) as e: p.exit(1,str(e)+'\n')
    output=json.dumps(result,indent=2)+'\n'
    if args.receipt:
        with args.receipt.open('x') as file: file.write(output)
    print(output,end='')
if __name__=='__main__':main()
