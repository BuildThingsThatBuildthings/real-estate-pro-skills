#!/usr/bin/env python3
"""Validate independent footage timelines. No photo renderer or runtime padding."""
import argparse
import json
from pathlib import Path
from edit_camera_sequence import validate
from production_inputs import Inputs

def prepare(root):
    root = Path(root).resolve()
    inputs = Inputs()
    spec = json.loads(inputs.read(root / 'context/film-timelines.json'))
    if inputs.run_id != spec['run_id']:
        raise ValueError('Preparation and workflow run IDs differ')
    timelines = spec['compositions']
    if not timelines:
        raise ValueError('Explicit camera-footage compositions required')
    seen_ids, seen_outputs, prepared = set(), set(), []
    for config in timelines:
        if config['run_id'] != spec['run_id']:
            raise ValueError('Composition belongs to another run')
        cid, output = config['composition_id'], str(Path(config['output']).resolve())
        if cid in seen_ids or output in seen_outputs:
            raise ValueError('Each composition needs its own ID, timeline and export')
        for medium in config.get('shots', []) + [a for a in [config.get('music'), config.get('narration')] if a] + config.get('sfx', []):
            inputs.read(medium['path'])
        duration = validate(config)
        seen_ids.add(cid); seen_outputs.add(output)
        prepared.append((config, duration))
    work = root / 'working/film-timelines'; work.mkdir(parents=True, exist_ok=True)
    jobs = []
    for index, (config, duration) in enumerate(prepared):
        path = work / f'{index:03}.json'; path.write_text(json.dumps(config, indent=2))
        jobs.append({'id': config['composition_id'], 'config': str(path), 'output': config['output'], 'duration': duration, 'run_id': spec['run_id'], 'operation': 'edit_camera_sequence.py'})
    (work / 'prepared.json').write_text(json.dumps(jobs, indent=2))
    inputs.finish()
    return jobs

if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('run'); a = p.parse_args()
    print(json.dumps(prepare(a.run), indent=2))
