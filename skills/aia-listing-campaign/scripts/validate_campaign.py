#!/usr/bin/env python3
"""Evidence/rights/completion gate. Probes never certify human playback or taste."""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'content-foundry/scripts'))
from delivery_gate import check_document, check_media, MEDIA, DOCUMENTS

FILMS = {
    'property-film-horizontal': (75, 90, '16:9'),
    'launch-film-vertical': (45, 60, '9:16'),
    'neighborhood-story-vertical': (75, 100, '9:16'),
    'neighborhood-story-horizontal': (75, 100, '16:9'),
    'office-reel': (None, None, '9:16'), 'patio-reel': (None, None, '9:16'),
    'flow-reel': (None, None, '9:16'), 'practical-details-reel': (None, None, '9:16'),
    'local-outing-reel': (25, 45, '9:16'),
    'launch-alternate-opening': (45, 60, '9:16'),
    'neighborhood-alternate-opening': (75, 100, '9:16'),
    'teaser-01-office': (8, 12, '9:16'), 'teaser-02-patio': (8, 12, '9:16'),
    'teaser-03-flow': (8, 12, '9:16'),
}
FULL_INVENTORY = {key: 'video' for key in FILMS}
for prefix, count in [('property-flow', 5), ('neighborhood-guide', 5), ('feed-property', 2), ('feed-neighborhood', 2), ('story-property', 6), ('story-neighborhood', 6)]:
    FULL_INVENTORY.update({f'{prefix}-{i:02}': 'graphic' for i in range(1, count + 1)})
FULL_INVENTORY.update({f'{key}-cover': 'graphic' for key in FILMS})
FULL_INVENTORY['listing-qr'] = 'graphic'
FULL_INVENTORY.update({key: 'document' for key in ['agent-recording-kit', 'campaign-calendar', 'listing-copy-and-outreach', 'platform-captions', 'listing-flyer']})


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def probe_film(path, expected=None):
    check_media(path)
    result = subprocess.run(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(path)], capture_output=True, text=True, check=True, timeout=30)
    data = json.loads(result.stdout); duration = float(data['format']['duration'])
    video = next(s for s in data['streams'] if s['codec_type'] == 'video')
    if not any(s.get('codec_type') == 'audio' for s in data['streams']):
        raise ValueError('finished film needs its final audio stream; presence is not proof of listening')
    if expected:
        low, high, aspect = expected
        if low is not None and high is not None and not low - .2 <= duration <= high + .2:
            raise ValueError(f'duration {duration:.2f}s outside required {low}–{high}s')
        numerator, denominator = map(int, aspect.split(':'))
        if abs(video['width'] / video['height'] - numerator / denominator) > .02:
            raise ValueError(f'composition must be {aspect}')
    return duration


def validate(run, final=False, root=None):
    errors = []
    sources = {s['id']: s for s in run.get('sources', [])}
    claims = {c['id']: c for c in run.get('claims', [])}
    media = {m['id']: m for m in run.get('media', [])}
    full = run.get('profile') == 'full-listing-campaign'
    deliverables = run.get('deliverables', [])
    if not run.get('client_slug') or not run.get('brand'):
        errors.append('Client and brand are required')
    ids = [d['id'] for d in deliverables]
    if len(set(ids)) != len(ids): errors.append('Duplicate deliverable IDs')
    if full:
        by_id = {d['id']: d for d in deliverables}
        for identifier, kind in FULL_INVENTORY.items():
            d = by_id.get(identifier)
            if not d: errors.append(f'{identifier}: missing full campaign deliverable')
            elif d.get('kind') != kind or not d.get('required'):
                errors.append(f'{identifier}: required {kind} cannot be downgraded or substituted')
    for d in deliverables:
        label = d['id']; kind = d.get('kind')
        if kind not in ('video', 'graphic', 'image', 'document'):
            errors.append(f'{label}: technical or unknown deliverable kind')
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
        path_value = d.get('path')
        path = (Path(root) / path_value).resolve() if root is not None and path_value else None
        if path_value:
            suffix = Path(path_value).suffix.lower()
            allowed = {'.mp4'} if kind == 'video' else DOCUMENTS if kind == 'document' else MEDIA - {'.mp4'}
            if suffix not in allowed: errors.append(f'{label}: file type does not match useful deliverable kind')
        if d.get('status') != 'complete': continue
        if not path_value or (root is not None and (not path.is_file() or not path.is_relative_to(Path(root).resolve()))):
            errors.append(f'{label}: missing output or path outside run')
        if path is not None and path.is_file() and path.is_relative_to(Path(root).resolve()):
            try:
                if kind == 'video': probe_film(path, FILMS.get(label) if full else None)
                elif kind in ('graphic', 'image'): check_media(path)
                elif kind == 'document': check_document(path)
            except Exception as error: errors.append(f'{label}: invalid finished file: {error}')
        review = d.get('review', {})
        if kind == 'video':
            if not all(review.get(k) for k in ('full_sound', 'full_muted', 'fidelity', 'reviewer', 'reviewed_at')):
                errors.append(f'{label}: missing complete video review')
            if full:
                if path is None or not path.is_file() or review.get('output_sha256') != sha(path):
                    errors.append(f'{label}: review must identify the exact finished video hash')
                for mode in ('sound', 'muted'):
                    evidence = review.get('evidence', {}).get(mode, {})
                    proof = (Path(root) / evidence['path']).resolve() if root is not None and evidence.get('path') else None
                    if proof is None or not proof.is_file() or not proof.is_relative_to(Path(root).resolve()) or not proof.stat().st_size or evidence.get('sha256') != sha(proof):
                        errors.append(f'{label}: missing private {mode} review evidence; booleans and probes are not playback proof')
    return errors

if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('run'); parser.add_argument('--final', action='store_true')
    args = parser.parse_args(); path = Path(args.run)
    errors = validate(json.loads(path.read_text()), args.final, path.parent)
    print(json.dumps({'pass': not errors, 'errors': errors}, indent=2)); raise SystemExit(bool(errors))
