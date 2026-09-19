"""Validate real panorama lineage and varied full-film coverage before editing."""
import hashlib
import json
from pathlib import Path


def digest(path):
    with Path(path).open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def panorama_inputs(shot, run_id):
    """Return inspected parent configuration and original, never reclassify a clip."""
    config_path = Path(shot['panorama_config']).resolve()
    config = json.loads(config_path.read_text())
    root = Path(config['root']).resolve()
    original = (root / config['source']).resolve()
    if shot.get('origin') != 'generated' or config.get('run_id') != run_id:
        raise ValueError('Panorama viewport requires its same-run generated producer')
    if config.get('projection') != 'equirectangular' or not config.get('source_identity'):
        raise ValueError('Panorama parent must identify an original equirectangular capture')
    if (root / config['output']).resolve() != Path(shot['path']).resolve():
        raise ValueError('Panorama parent output differs from the actual clip')
    if not config.get('room_identity') or shot.get('room_identity') != config['room_identity']:
        raise ValueError('Reviewed room identity differs from the panorama parent')
    if config.get('rights') not in ('authorized', 'licensed', 'original') or not config.get('rights_basis'):
        raise ValueError('Panorama original has no reuse authority')
    if not original.is_relative_to(root) or digest(original) != config.get('source_sha256'):
        raise ValueError('Panorama original is missing, changed or outside the run')
    return config_path, original, config


def validate_coverage(config, photo_frames, total):
    if config.get('mode') != 'panorama_photo_edit':
        return
    panoramas = [s for s in config['shots'] if s.get('panorama_config')]
    parents = [panorama_inputs(s, config['run_id'])[2] for s in panoramas]
    if config['kind'] == 'flagship':
        if len({p['source_sha256'] for p in parents}) < 5:
            raise ValueError('Panorama flagship requires at least five distinct real capture positions')
        if len({p['room_identity'] for p in parents}) < 4:
            raise ValueError('Panorama flagship requires at least four actual rooms or outdoor spaces')
        if sum(s['seconds'] for s in panoramas) < total * .35:
            raise ValueError('Panoramic movement must carry at least35percent of the flagship')
        if len(photo_frames) < 8 or len(config['shots']) < 15:
            raise ValueError('Mixed flagship needs varied original-photo details and a complete visual progression')
    if not panoramas:
        raise ValueError('Panorama mode cannot silently produce an all-photo edit')
