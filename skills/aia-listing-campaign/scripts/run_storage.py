#!/usr/bin/env python3
"""Persistent AIA runs and exact, hash-verified restoration of originals/dependencies."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def validate_root(value, scope='production'):
    root = Path(value).expanduser().resolve()
    if scope not in ('production', 'test'):
        raise ValueError('Run scope must be production or explicit test')
    temporary = [Path(p).resolve() for p in ('/tmp', '/private/tmp', '/var/tmp', '/private/var/tmp', '/private/var/folders', '/dev/shm', tempfile.gettempdir())]
    if os.environ.get('TMPDIR'):
        temporary.append(Path(os.environ['TMPDIR']).resolve())
    ephemeral = any(root == p or root.is_relative_to(p) for p in temporary)
    if scope == 'production' and ephemeral:
        raise ValueError('Production campaigns require persistent storage; temporary roots are scratch or explicit test fixtures only')
    if scope == 'test' and not ephemeral:
        raise ValueError('Explicit test scope must stay in temporary fixture storage')
    if root == Path(root.anchor) or root == Path.home():
        raise ValueError('Choose a dedicated private run folder')
    return root


def save(path, payload):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.writing')
    temp.write_text(json.dumps(payload, indent=2)); temp.replace(path)


def initialize(root, run_id, scope='production', intake_files=None):
    root = validate_root(root, scope)
    if not run_id or Path(run_id).name != run_id:
        raise ValueError('A plain, nonempty run ID is required')
    marker = root / 'working/run-storage.json'
    if marker.exists():
        existing = json.loads(marker.read_text())
        if existing.get('run_id') != run_id or existing.get('scope') != scope:
            raise ValueError('Existing persistent run identity differs; never relabel it')
        return existing
    intake = {}
    if root.exists() and any(root.iterdir()):
        selected = [(root / value).resolve() for value in (intake_files or [])]
        existing_files = [p.resolve() for p in root.rglob('*') if p.is_file()]
        if set(existing_files) != set(selected) or not selected:
            raise ValueError('Initialize an empty run or name every existing intake manifest explicitly')
        for path in selected:
            if path.is_symlink() or not any(path.is_relative_to(root / folder) for folder in ('working','source')) or path.suffix not in ('.json','.txt','.md'):
                raise ValueError('Only explicitly named private intake manifests or source evidence may precede initialization')
            if path.suffix == '.json':
                json.loads(path.read_text())
            intake[str(path.relative_to(root))] = digest(path)
    for folder in ('source', 'dependencies', 'context', 'assets', 'working', 'output', 'delivery'):
        (root / folder).mkdir(parents=True, exist_ok=True)
    (root / '.gitignore').write_text('*\n!.gitignore\n')
    result = {'run_id': run_id, 'root': str(root), 'scope': scope, 'created_at': datetime.now(timezone.utc).isoformat(), 'storage': 'persistent' if scope == 'production' else 'temporary_test_fixture', 'preexisting_intake_hashes': intake}
    save(marker, result)
    return result


def source_hashes(value):
    source = Path(value).expanduser()
    if source.is_symlink():
        raise ValueError('Select actual source paths, not symbolic links')
    source = source.resolve()
    if not source.exists():
        raise ValueError('Recovery source is absent')
    files = [source] if source.is_file() else sorted(p for p in source.rglob('*') if p.is_file() or p.is_symlink())
    if not files:
        raise ValueError('Recovery source is empty')
    if any(p.is_symlink() for p in files):
        raise ValueError('Recovery source contains symbolic links; select explicit regular-file dependency folders')
    return {'.' if source.is_file() else str(p.relative_to(source)): digest(p) for p in files}


def inventory(source, destination, kind, basis):
    if kind not in ('original', 'dependency') or not basis:
        raise ValueError('Recovery accepts only identified originals or dependencies with a basis')
    return {'source': str(Path(source).expanduser().resolve()), 'destination': destination, 'kind': kind, 'basis': basis, 'hashes': source_hashes(source)}


def restore(plan, receipt_path):
    root = validate_root(plan['root'], plan.get('scope', 'production'))
    marker = json.loads((root / 'working/run-storage.json').read_text())
    if marker.get('run_id') != plan.get('run_id') or marker.get('scope') != plan.get('scope', 'production'):
        raise ValueError('Initialize this exact run before source recovery')
    receipt = Path(receipt_path).resolve()
    if not receipt.is_relative_to(root / 'working'):
        raise ValueError('Recovery receipt stays in private working storage')
    allowed = [Path(p).expanduser().resolve() for p in plan.get('allowed_source_roots', [])]
    if not allowed or not plan.get('authorization') or not plan.get('sources'):
        raise ValueError('Exact allowed roots, recovery authorization and selected sources are required')
    selected = []
    forbidden = {'delivery', 'output', 'handoff', 'film-renders', 'local-narration'}
    for item in plan['sources']:
        item = dict(item)
        if not item.get('hashes') and item.get('sha256'):
            item['hashes'] = {'.': item['sha256']}
        source = Path(item['source']).expanduser().resolve()
        if not any(source == p or source.is_relative_to(p) for p in allowed):
            raise ValueError('Recovery source is outside the selected original/dependency roots')
        if forbidden.intersection(source.parts):
            raise ValueError('Rejected exports and generated film/narration caches cannot be restored as originals')
        if item.get('kind') not in ('original', 'dependency') or not item.get('basis'):
            raise ValueError('Only identified original media or runtime/font dependencies may be recovered')
        dest = (root / item['destination']).resolve()
        base = root / ('source' if item['kind'] == 'original' else 'dependencies')
        if dest == base or not dest.is_relative_to(base):
            raise ValueError('Use a specific source/ or dependencies/ destination matching its kind')
        if any(dest == prior or dest.is_relative_to(prior) or prior.is_relative_to(dest) for _, prior, _ in selected):
            raise ValueError('Recovery destinations overlap')
        if not item.get('hashes') or source_hashes(source) != item['hashes']:
            raise ValueError('Recovery source changed since exact inventory')
        selected.append((source, dest, item))
    result = {'run_id': plan['run_id'], 'root': str(root), 'complete': False, 'restored': []}
    save(receipt, result)
    for source, dest, item in selected:
        for relative, expected in item['hashes'].items():
            src = source if relative == '.' else source / relative
            dst = dest if relative == '.' else dest / relative
            if not dst.resolve().is_relative_to(root):
                raise ValueError('Recovery destination escaped the run')
            dst.parent.mkdir(parents=True, exist_ok=True)
            if dst.exists():
                if not dst.is_file() or digest(dst) != expected:
                    raise ValueError('Recovery will not overwrite conflicting destination bytes')
            else:
                temporary = dst.with_name(dst.name + '.restoring')
                shutil.copy2(src, temporary)
                if digest(temporary) != expected:
                    raise ValueError('Recovered bytes differ from inventoried source')
                temporary.replace(dst)
            if digest(src) != expected or digest(dst) != expected:
                raise ValueError('Recovery source or destination changed during copy')
        result['restored'].append({**item, 'destination': str(dest), 'verified': True})
        if len(result['restored']) % 50 == 0:
            save(receipt, result)
    result['complete'] = True
    result['verified_at'] = datetime.now(timezone.utc).isoformat()
    save(receipt, result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); sub = parser.add_subparsers(dest='action', required=True)
    p = sub.add_parser('init'); p.add_argument('--root', required=True); p.add_argument('--run-id', required=True); p.add_argument('--scope', choices=['production', 'test'], default='production'); p.add_argument('--intake-file', action='append', default=[])
    p = sub.add_parser('inventory-source'); p.add_argument('--source', required=True); p.add_argument('--destination', required=True); p.add_argument('--kind', choices=['original', 'dependency'], required=True); p.add_argument('--basis', required=True); p.add_argument('--output', required=True)
    p = sub.add_parser('restore'); p.add_argument('plan'); p.add_argument('--receipt', required=True)
    args = parser.parse_args()
    if args.action == 'init':
        print(json.dumps(initialize(args.root, args.run_id, args.scope, args.intake_file), indent=2))
    elif args.action == 'inventory-source':
        item = inventory(args.source, args.destination, args.kind, args.basis); save(args.output, item)
        print(f"Inventoried {len(item['hashes'])} exact original/dependency files")
    else:
        result = restore(json.loads(Path(args.plan).read_text()), args.receipt)
        print(f"Restored and verified {len(result['restored'])} selected sources; complete={result['complete']}")
