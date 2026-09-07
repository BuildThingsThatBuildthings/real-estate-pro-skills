#!/usr/bin/env python3
"""Verify uploaded review bytes, without equating transfer with creative approval."""
import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def verify(local, remote, folder_id, destination, receipt):
    local = Path(local).resolve()
    receipt = Path(receipt).resolve()
    if not local.is_dir() or not any(p.is_file() for p in local.rglob('*')):
        raise ValueError('A nonempty local delivery directory is required')
    if receipt.is_relative_to(local):
        raise ValueError('Receipt must be outside the checked delivery directory')
    if not folder_id or not remote.endswith(':') or not destination.strip('/'):
        raise ValueError('Explicit remote, folder ID and destination are required')
    target = remote + destination.strip('/')
    command = ['rclone', 'check', str(local), target,
               '--drive-root-folder-id', folder_id, '--one-way', '--download']
    result = subprocess.run(command, capture_output=True, text=True)
    files = [{'path': str(p.relative_to(local)), 'bytes': p.stat().st_size,
              'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
             for p in sorted(local.rglob('*')) if p.is_file()]
    record = {'checked_at': datetime.now(timezone.utc).isoformat(),
              'remote': target, 'parent_folder_id': folder_id,
              'downloaded_bytes_match': result.returncode == 0,
              'exit_code': result.returncode, 'files': files,
              'check_output': result.stderr[-12000:],
              'playback_review': 'separate; not verified by byte comparison',
              'creative_acceptance': 'separate; not verified by byte comparison'}
    receipt.parent.mkdir(parents=True, exist_ok=True)
    receipt.write_text(json.dumps(record, indent=2) + '\n')
    return result.returncode


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('local')
    parser.add_argument('--remote', required=True)
    parser.add_argument('--folder-id', required=True)
    parser.add_argument('--destination', required=True)
    parser.add_argument('--receipt', required=True)
    args = parser.parse_args()
    raise SystemExit(verify(args.local, args.remote, args.folder_id,
                            args.destination, args.receipt))
