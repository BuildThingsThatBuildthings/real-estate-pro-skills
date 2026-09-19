#!/usr/bin/env python3
"""Explicit, recoverable Drive reset. Private receipts never enter delivery.

Inventory a selected parent, select exact children in the resulting private plan,
then execute. Never removes the selected parent or guesses ownership.
"""
import argparse
import datetime
import json
import subprocess
import hashlib
import shutil
from pathlib import Path, PurePosixPath

def file_hash(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def tree_hashes(path):
    path=Path(path)
    if path.is_file():return {'.':file_hash(path)}
    return {str(p.relative_to(path)):file_hash(p) for p in sorted(path.rglob('*')) if p.is_file()}

def execute_local(plan, receipt_path):
    """Preserve exact originals/dependencies, verify bytes, then move old run roots to Trash."""
    if not plan.get('authorization'):raise ValueError('Explicit local reset authorization required')
    parent=Path(plan['allowed_parent']).resolve();root=Path(plan['run_root']).resolve()
    targets=[Path(p).resolve() for p in plan['targets']]
    if not targets or len(set(targets))!=len(targets):raise ValueError('Explicit unique old run roots required')
    for target in targets:
        if target.parent!=parent or not target.is_dir() or target==root or root.is_relative_to(target):raise ValueError('Only existing old direct-child run folders can be reset')
        if (target/'.git').exists() or (target/'skills').is_dir():raise ValueError('Never delete a skill repository as campaign output')
    trash=Path(plan.get('trash_root',str(Path.home()/'.Trash'))).resolve()
    if any(trash==t or trash.is_relative_to(t) for t in targets):raise ValueError('Trash cannot be inside removed work')
    receipt_path=Path(receipt_path).resolve()
    if not receipt_path.is_relative_to(root/'working'):raise ValueError('Local reset receipt must remain private in the fresh run')
    receipt={'complete':False,'authorization':plan['authorization'],'preserved':[],'removed':[],'trash_root':str(trash)}
    def write():receipt_path.parent.mkdir(parents=True,exist_ok=True);receipt_path.write_text(json.dumps(receipt,indent=2))
    write()
    try:
        for item in plan.get('preserve',[]):
            source=Path(item['source']).resolve();destination=(root/item['destination']).resolve()
            if item.get('kind') not in ('original','dependency') or not item.get('basis'):raise ValueError('Preservation requires original/dependency evidence')
            if not any(source.is_relative_to(t) for t in targets) or not (destination.is_relative_to(root/'source') or destination.is_relative_to(root/'dependencies')):raise ValueError('Preserve only identified source/dependency assets to the fresh run')
            before=tree_hashes(source)
            if not before:raise ValueError('Missing or empty preservation source')
            if destination.exists():
                if tree_hashes(destination)!=before:raise ValueError('Conflicting preserved destination')
            else:
                destination.parent.mkdir(parents=True,exist_ok=True)
                if source.is_dir():shutil.copytree(source,destination,symlinks=False)
                else:shutil.copy2(source,destination)
            if tree_hashes(destination)!=before:raise ValueError('Preserved bytes did not verify')
            receipt['preserved'].append({**item,'destination':str(destination),'hashes':before});write()
        if not receipt['preserved']:raise ValueError('Identify supplied originals before resetting local campaigns')
        trash.mkdir(parents=True,exist_ok=True)
        stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        for target in targets:
            destination=trash/(target.name+'--aia-reset-'+stamp)
            if destination.exists():raise ValueError('Trash collision')
            count=sum(1 for p in target.rglob('*') if p.is_file())
            shutil.move(str(target),str(destination))
            if target.exists() or not destination.is_dir():raise RuntimeError('Local trash move not verified')
            receipt['removed'].append({'source':str(target),'trash_path':str(destination),'files':count,'source_absent':True});write()
        receipt['complete']=all(not p.exists() for p in targets)
        receipt['verified_at']=datetime.datetime.now(datetime.timezone.utc).isoformat();write();return receipt
    except Exception as exc:
        receipt['error']=str(exc);write();raise


def trash_rejected(plan, receipt_path):
    """Remove exact rejected generated files, with byte checks and recoverable Trash."""
    if not plan.get('authorization'):raise ValueError('Explicit rejection/reset authorization required')
    root=Path(plan['run_root']).resolve();receipt_path=Path(receipt_path).resolve()
    if not receipt_path.is_relative_to(root/'working'):raise ValueError('Receipt must remain private')
    selected=[]
    for item in plan['targets']:
        path=(root/item['path']).resolve()
        if not any(path.is_relative_to(root/d) for d in ('delivery','output','working/maps')):raise ValueError('Only generated output files may be rejected')
        if not path.is_file() or path.is_symlink() or path.suffix.lower() not in ('.mp4','.png','.jpg','.jpeg','.pdf') or file_hash(path)!=item['sha256']:raise ValueError('Rejected output missing, changed or invalid')
        if not item.get('rejection_reason'):raise ValueError('Rejection reason required')
        if path in selected:raise ValueError('Duplicate rejected output')
        selected.append(path)
    if not selected:raise ValueError('Exact rejected outputs required')
    trash=Path.home()/'.Trash';trash.mkdir(exist_ok=True)
    stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    receipt={'complete':False,'removed':[]}
    receipt_path.parent.mkdir(parents=True,exist_ok=True)
    for index,path in enumerate(selected):
        destination=trash/(path.stem+'--aia-rejected-'+stamp+f'-{index}'+path.suffix)
        if destination.exists():raise ValueError('Trash collision')
        before=file_hash(path);shutil.move(str(path),str(destination))
        if path.exists() or file_hash(destination)!=before:raise RuntimeError('Rejected file move did not verify')
        receipt['removed'].append({'path':str(path),'trash_path':str(destination),'sha256':before})
        receipt_path.write_text(json.dumps(receipt,indent=2))
    receipt['complete']=True;receipt_path.write_text(json.dumps(receipt,indent=2));return receipt


def purge_rejected_exports(plan, receipt_path):
    """Permanently remove explicitly selected rejected exports already in Trash."""
    if not plan.get('authorization') or not plan.get('permanent_delete_authorized'):raise ValueError('Explicit permanent deletion authorization required')
    root=Path(plan['run_root']).resolve();receipt_path=Path(receipt_path).resolve()
    if not receipt_path.is_relative_to(root/'working'):raise ValueError('Receipt must remain private')
    previous=json.loads(Path(plan['local_reset_receipt']).read_text())
    if not previous.get('complete'):raise ValueError('Prior recoverable cleanup must be verified')
    for item in previous['preserved']:
        if tree_hashes(item['destination'])!=item['hashes']:raise ValueError('Preserved original/dependency changed')
    allowed={Path(x['trash_path']).resolve() for x in previous['removed']}
    targets=[]
    for item in plan['targets']:
        path=Path(item['path']).resolve()
        if not any(path.is_relative_to(base/folder) for base in allowed for folder in ('delivery','output')) or not path.is_file() or path.is_symlink() or path.suffix.lower() not in ('.mp4','.png','.jpg','.jpeg'):raise ValueError('Only exact previously rejected video/image files in Trash; documents excluded')
        if file_hash(path)!=item['sha256']:raise ValueError('Rejected media changed')
        targets.append(path)
    if not targets or len(set(targets))!=len(targets):raise ValueError('Unique exact export folders required')
    receipt={'complete':False,'permanently_removed':[]};receipt_path.parent.mkdir(parents=True,exist_ok=True)
    for path in targets:
        path.unlink()
        if path.exists():raise RuntimeError('Rejected media removal failed')
        receipt['permanently_removed'].append(str(path))
        print('Removed rejected media: '+str(path),flush=True)
        try:receipt_path.write_text(json.dumps(receipt,indent=2))
        except OSError as error:
            if error.errno!=28:raise
            print('Disk-full receipt write deferred until remaining exact media cleanup frees space',flush=True)
    receipt['complete']=True;receipt_path.write_text(json.dumps(receipt,indent=2));return receipt


def call(argv):
    result = subprocess.run(argv, capture_output=True, text=True, timeout=60)
    if result.returncode or 'ERROR :' in result.stderr or 'Skipping unexportable' in result.stderr:
        raise RuntimeError(result.stderr[-2000:])
    return result.stdout


def flags(parent):
    if not parent or parent in ('root', '/') or '/' in parent:
        raise ValueError('Explicit Drive parent ID required')
    return ['--drive-root-folder-id', parent, '--drive-use-trash=true', '--drive-show-all-gdocs=true',
            '--contimeout', '10s', '--timeout', '20s', '--retries', '1',
            '--low-level-retries', '1', '--tpslimit', '2']


def inventory(remote, parent, runner=call):
    if not remote.endswith(':') or '/' in remote:
        raise ValueError('Use a configured remote name, not a path')
    items = json.loads(runner(['rclone', 'lsjson', remote, '--max-depth', '1'] + flags(parent)))
    return [{'id': x['ID'], 'path': x['Path'], 'directory': x['IsDir']} for x in items]


def validate_targets(plan):
    if not plan.get('authorization'):
        raise ValueError('Record the explicit user reset instruction')
    ids, names = set(), set()
    for item in plan['targets']:
        name = item['path']
        if not name or name in ('.', '..') or len(PurePosixPath(name).parts) != 1 or '/' in name or '\\' in name:
            raise ValueError('Only exact direct children may be reset')
        if not item.get('id') or item['id'] in ids or name in names:
            raise ValueError('Duplicate or missing target identity')
        ids.add(item['id']); names.add(name)


def execute(plan, receipt_path, runner=call):
    validate_targets(plan)
    remote, parent = plan['remote'], plan['parent_id']
    current = inventory(remote, parent, runner)
    by_name = {}
    for row in current:
        by_name.setdefault(row['path'], []).append(row)
    for target in plan['targets']:
        if by_name.get(target['path']) != [target]:
            raise ValueError('Target changed, absent, or ambiguous: ' + target['path'])
    receipt = {'parent_id': parent, 'removed': [], 'complete': False}
    path = Path(receipt_path); path.parent.mkdir(parents=True, exist_ok=True)
    def save():
        path.write_text(json.dumps(receipt, indent=2))
    save()
    try:
        for target in plan['targets']:
            # Each operation targets a direct child. The framework parent survives.
            operation = 'purge' if target['directory'] else 'deletefile'
            runner(['rclone', operation, remote + target['path']] + flags(parent))
            remaining = inventory(remote, parent, runner)
            if any(x['id'] == target['id'] for x in remaining):
                raise RuntimeError('Removal not verified: ' + target['path'])
            receipt['removed'].append(target)
            save()
        remaining = inventory(remote, parent, runner)
        receipt['remaining'] = remaining
        receipt['complete'] = not remaining if plan.get('require_empty') else True
        receipt['verified_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        if not receipt['complete']:
            raise RuntimeError('Parent is not empty after requested full reset')
        return receipt
    except Exception as exc:
        receipt['error'] = str(exc)
        raise
    finally:
        save()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='action', required=True)
    scan = sub.add_parser('inventory')
    scan.add_argument('--remote', required=True); scan.add_argument('--parent-id', required=True)
    scan.add_argument('--output', required=True)
    reset = sub.add_parser('execute')
    reset.add_argument('plan'); reset.add_argument('--receipt', required=True)
    local = sub.add_parser('local-execute')
    local.add_argument('plan');local.add_argument('--receipt',required=True)
    rejected=sub.add_parser('rejected-execute');rejected.add_argument('plan');rejected.add_argument('--receipt',required=True)
    purge=sub.add_parser('purge-rejected-exports');purge.add_argument('plan');purge.add_argument('--receipt',required=True)
    args = parser.parse_args()
    if args.action == 'inventory':
        rows = inventory(args.remote, args.parent_id)
        Path(args.output).write_text(json.dumps({'remote': args.remote, 'parent_id': args.parent_id,
            'authorization': '', 'targets': rows, 'require_empty': False}, indent=2))
        print(f'{len(rows)} direct children inventoried; no changes made')
    elif args.action == 'purge-rejected-exports':
        result=purge_rejected_exports(json.loads(Path(args.plan).read_text()),args.receipt)
        print(f"Permanently removed {len(result['permanently_removed'])} exact rejected video/image files; preserved originals verified")
    elif args.action == 'rejected-execute':
        result=trash_rejected(json.loads(Path(args.plan).read_text()),args.receipt)
        print(f"Moved {len(result['removed'])} rejected outputs to recoverable Trash")
    elif args.action == 'local-execute':
        result=execute_local(json.loads(Path(args.plan).read_text()),args.receipt)
        print(f"Local reset verified: {len(result['removed'])} old roots moved to recoverable Trash; complete={result['complete']}")
    else:
        result = execute(json.loads(Path(args.plan).read_text()), args.receipt)
        print(f"Removed and verified {len(result['removed'])} items; complete={result['complete']}")
