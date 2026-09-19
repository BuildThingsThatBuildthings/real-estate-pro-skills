#!/usr/bin/env python3
"""Validate private neighborhood evidence and compositions before the shared film editor."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


def file_at(value, base):
    path = Path(value)
    return path if path.is_absolute() else base / path


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(chunk)
    return value.hexdigest()


def validate(plan, base):
    errors, configs = [], []
    run_id = plan.get('run_id')
    if not run_id:
        errors.append('Missing current run_id')
    narrative = plan.get('narrative', {})
    for field in ('opening', 'discovery', 'payoff', 'place_specificity', 'sound_direction'):
        if not isinstance(narrative.get(field), str) or not narrative[field].strip():
            errors.append(f'Missing narrative.{field}')
    locations = plan.get('locations', {})
    claims = plan.get('claims', {})
    media = plan.get('media', {})
    for claim_id, claim in claims.items():
        if not all(claim.get(k) for k in ('text', 'source', 'checked_at', 'location_id')):
            errors.append(f'{claim_id}: claim needs text, source, checked_at and location_id')
        if claim.get('location_id') not in locations:
            errors.append(f'{claim_id}: unknown location')
        if claim.get('development_status') and claim['development_status'] not in (
                'proposed', 'approved', 'under_construction', 'open'):
            errors.append(f'{claim_id}: invalid development status')
        if claim.get('development_status') and not all(claim.get(k) for k in (
                'proximity_evidence', 'practical_relevance')):
            errors.append(f'{claim_id}: development needs proximity and relevance evidence')
    for media_id, asset in media.items():
        if not all(asset.get(k) for k in ('path', 'rights_basis', 'source', 'location_id', 'sha256')):
            errors.append(f'{media_id}: incomplete media provenance')
            continue
        if asset['location_id'] not in locations:
            errors.append(f'{media_id}: unknown location')
        path = file_at(asset['path'], base)
        if not path.is_file():
            errors.append(f'{media_id}: missing media file')
        elif digest(path) != asset['sha256']:
            errors.append(f'{media_id}: media hash mismatch')
        if asset.get('origin') not in ('original', 'generated'):
            errors.append(f'{media_id}: missing original/generated identity')
        if asset.get('origin') == 'generated' and asset.get('run_id') != run_id:
            errors.append(f'{media_id}: generated media belongs to another run')
    films = plan.get('films', {})
    if set(films) != {'vertical', 'horizontal'}:
        errors.append('Both vertical and horizontal compositions are required')
    composition_ids, outputs = set(), set()
    for orientation, config_name in films.items():
        config_path = file_at(config_name, base).resolve()
        if not config_path.is_file():
            errors.append(f'{orientation}: missing editor config')
            continue
        config = json.loads(config_path.read_text())
        configs.append(config_path)
        if config.get('run_id') != run_id or config.get('kind') != 'neighborhood':
            errors.append(f'{orientation}: config must be this run and kind neighborhood')
        cid = config.get('composition_id')
        if not cid or cid in composition_ids:
            errors.append(f'{orientation}: independently identified composition required')
        composition_ids.add(cid)
        out = config.get('output')
        if not out or out in outputs or Path(out).suffix.lower() != '.mp4':
            errors.append(f'{orientation}: distinct MP4 output required')
        outputs.add(out)
        width, height = config.get('width', 0), config.get('height', 0)
        if min(width, height) <= 0 or (orientation == 'vertical' and width >= height) or (
                orientation == 'horizontal' and height >= width):
            errors.append(f'{orientation}: incorrect composition dimensions')
        if not config.get('narration') or not config.get('captions'):
            errors.append(f'{orientation}: narration and embedded captions required')
        used_claims, beats, seen_locations = set(), [], set()
        for n, shot in enumerate(config.get('shots', [])):
            prefix = f'{orientation} shot {n + 1}'
            asset = media.get(shot.get('media_id'))
            if not asset:
                errors.append(f'{prefix}: media_id missing from rights inventory')
                continue
            if not asset.get('path') or file_at(shot.get('path', ''), config_path.parent).resolve() != file_at(asset['path'], base).resolve():
                errors.append(f'{prefix}: shot path does not match inventoried media')
            if shot.get('source_sha256') != asset.get('sha256') or shot.get('origin') != asset.get('origin'):
                errors.append(f'{prefix}: source identity must match rights inventory')
            if shot.get('location_id') != asset.get('location_id'):
                errors.append(f'{prefix}: cannot present footage as another location')
            seen_locations.add(asset.get('location_id'))
            if not shot.get('framing_note'):
                errors.append(f'{prefix}: composition-specific framing_note required')
            if shot.get('narrative_beat'):
                beats.append(shot['narrative_beat'])
            for claim_id in shot.get('claim_ids', []):
                claim = claims.get(claim_id)
                used_claims.add(claim_id)
                if not claim:
                    errors.append(f'{prefix}: unknown claim {claim_id}')
                    continue
                if claim.get('development_status') in ('proposed', 'approved', 'under_construction'):
                    label = claim.get('screen_label')
                    onscreen = ' '.join(t.get('text', '') for t in shot.get('text', []))
                    if not label or label.lower() not in onscreen.lower():
                        errors.append(f'{prefix}: future project needs its explicit screen label')
                    spoken = shot.get('spoken_status', '')
                    status_words = claim['development_status'].replace('_', ' ')
                    if not isinstance(spoken, str) or status_words not in spoken.lower():
                        errors.append(f'{prefix}: future project status must also be spoken')
        if not beats or beats[0] != 'opening' or 'discovery' not in beats or beats[-1] != 'payoff':
            errors.append(f'{orientation}: opening, discovery and final payoff required')
        if len(seen_locations) < 2:
            errors.append(f'{orientation}: story needs home and actual surrounding-place coverage')
        if not used_claims:
            errors.append(f'{orientation}: neighborhood story has no linked factual evidence')
    return errors, configs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('plan', type=Path)
    parser.add_argument('--render', action='store_true', help='Render both validated compositions through the AIA campaign editor')
    args = parser.parse_args()
    errors, configs = validate(json.loads(args.plan.read_text()), args.plan.resolve().parent)
    if errors:
        print('\n'.join(errors), file=sys.stderr)
        return 1
    if args.render:
        editor = Path(__file__).resolve().parents[2] / 'aia-listing-campaign/scripts/edit_camera_sequence.py'
        receipt_name = os.environ.get('AIA_PRODUCTION_RECEIPT')
        consumed = {}
        for config in configs:
            subprocess.run([sys.executable, str(editor), str(config)], check=True)
            if receipt_name:
                for item in json.loads(Path(receipt_name).read_text())['consumed']:
                    consumed[item['path']] = item
        if receipt_name:
            declared = {str(Path(item['path']).resolve()): item for item in json.loads(os.environ.get('AIA_TASK_INPUTS_JSON', '[]'))}
            # Validation itself reads the plan and every inventoried media file.
            plan = json.loads(args.plan.read_text())
            read_paths = [args.plan.resolve()] + [file_at(item['path'], args.plan.resolve().parent).resolve() for item in plan['media'].values()]
            for source in read_paths:
                if str(source) not in declared:
                    raise ValueError('Undeclared neighborhood production input: ' + str(source))
                consumed[str(source)] = {**declared[str(source)], 'path': str(source), 'sha256': digest(source)}
            Path(receipt_name).write_text(json.dumps({'run_id': plan['run_id'], 'consumed': list(consumed.values()), 'status': 'rendered_awaiting_full_playback'}, indent=2))
    print('Evidence and composition structure checked; full sound/muted creative review is still required.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
