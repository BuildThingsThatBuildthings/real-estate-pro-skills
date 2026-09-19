#!/usr/bin/env python3
"""Copy the exact full-campaign inventory into a clean client handoff.

Run through run_workflow.py. Every source must be a declared same-run producer
output. No directory glob or implicit source-folder upload is supported.
"""
import argparse
import hashlib
import json
from pathlib import Path
from production_inputs import Inputs
from validate_campaign import FULL_INVENTORY
from delivery_gate import relative, validate_delivery


def selection(spec, root):
    root = Path(root).resolve()
    items = spec['items']
    ids = [x['id'] for x in items]
    if len(set(ids)) != len(ids) or set(ids) != set(FULL_INVENTORY):
        raise ValueError('Select every canonical campaign ID exactly once')
    paths = set()
    for item in items:
        dest = relative(item['destination']).as_posix()
        if dest in paths:
            raise ValueError('Duplicate handoff destination')
        paths.add(dest)
        original = root / item['source']
        source = original.resolve()
        if not source.is_relative_to(root) or original.is_symlink() or not source.is_file():
            raise ValueError('Handoff sources must be current run files')
        kind = FULL_INVENTORY[item['id']]
        suffix = Path(dest).suffix.lower()
        allowed = {'.mp4'} if kind == 'video' else {'.pdf'} if kind == 'document' else {'.png', '.jpg', '.jpeg'}
        if suffix not in allowed or suffix != source.suffix.lower():
            raise ValueError('Selected file type does not match its deliverable')
        if not item.get('producer_task') or not item.get('sha256'):
            raise ValueError('Every selected file needs its producer and exact hash')
    return items


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('manifest')
    args = parser.parse_args()
    inputs = Inputs()
    spec = json.loads(inputs.read(Path(args.manifest).resolve()))
    root = Path(spec['root']).resolve()
    if spec.get('run_id') != inputs.run_id:
        raise ValueError('Selection belongs to another run')
    destination = (root / spec['destination_root']).resolve()
    if not destination.is_relative_to(root) or destination == root or destination.exists():
        raise ValueError('A fresh handoff subfolder is required')
    items = selection(spec, root)
    for item in items:
        source = (root / item['source']).resolve()
        declared = inputs.declared.get(str(source))
        if not declared or declared.get('origin') != 'generated' or declared.get('producer_task') != item['producer_task']:
            raise ValueError('Selected source must match its verified production dependency')
        data = inputs.read(source)
        if hashlib.sha256(data).hexdigest() != item['sha256']:
            raise ValueError('Selected source bytes changed')
        target = destination / relative(item['destination'])
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    docs = [x['destination'] for x in items if FULL_INVENTORY[x['id']] == 'document']
    folders = sorted({str(Path(p).parent) for p in docs})
    validate_delivery(destination, folders, docs)
    inputs.finish()
    print(f'Copied and validated {len(items)} exact client deliverables; creative approval remains separate.')


if __name__ == '__main__':
    main()
