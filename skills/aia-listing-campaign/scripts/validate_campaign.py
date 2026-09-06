#!/usr/bin/env python3
"""Fail-closed evidence/rights/completion gate; never substitutes for human playback."""
import argparse, json
from pathlib import Path

def validate(run, final=False, root=None):
    errors = []
    sources = {s['id']: s for s in run.get('sources', [])}
    claims = {c['id']: c for c in run.get('claims', [])}
    media = {m['id']: m for m in run.get('media', [])}
    if not run.get('client_slug') or not run.get('brand'):
        errors.append('Client and brand are required')
    for d in run.get('deliverables', []):
        label = d['id']
        for cid in d.get('claim_ids', []):
            c = claims.get(cid)
            if not c or c.get('status') != 'verified' or not c.get('source_ids') or any(s not in sources for s in c.get('source_ids', [])):
                errors.append(f'{label}: unsupported claim {cid}')
        for mid in d.get('media_ids', []):
            m = media.get(mid)
            if not m or m.get('rights') not in ('authorized', 'licensed', 'original') or not m.get('rights_basis'):
                errors.append(f'{label}: unresolved rights {mid}')
            elif m.get('rights') == 'licensed' and (not m.get('commercial_use') or not m.get('license_evidence')):
                errors.append(f'{label}: commercial license not established {mid}')
        if final and d.get('required') and d.get('status') != 'complete':
            errors.append(f'{label}: required deliverable incomplete')
        if d.get('status') == 'complete':
            path = d.get('path')
            if not path or (root is not None and not (Path(root) / path).is_file()):
                errors.append(f'{label}: missing output')
            review = d.get('review', {})
            if d.get('kind') == 'video' and not all(review.get(k) for k in ('full_sound', 'full_muted', 'fidelity', 'reviewer', 'reviewed_at')):
                errors.append(f'{label}: missing complete video review')
    return errors

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('run'); p.add_argument('--final', action='store_true')
    a = p.parse_args(); path = Path(a.run)
    errors = validate(json.loads(path.read_text()), a.final, path.parent)
    print(json.dumps({'pass': not errors, 'errors': errors}, indent=2))
    raise SystemExit(bool(errors))
