#!/usr/bin/env python3
"""Render explicitly sourced compositions; keep logs and provenance private."""
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
from production_inputs import Inputs


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def valid(path, seconds):
    if not path.exists(): return False
    try:
        data = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'json', str(path)]))
        return abs(float(data['format']['duration']) - seconds) < .15
    except (subprocess.CalledProcessError, KeyError, ValueError): return False


def provenance(job, inputs=None):
    if not job.get('run_id') or not re.fullmatch(r'[A-Za-z0-9_-]+', job['id']):
        raise ValueError('Safe composition id and current run_id required')
    sources = job.get('source_paths', [])
    if not sources:
        raise ValueError('Explicit source_paths required; old rendered files are not provenance')
    def fingerprint(path):
        return hashlib.sha256(inputs.read(path)).hexdigest() if inputs else sha(path)
    return {'run_id': job['run_id'], 'props_sha256': fingerprint(job['props']),
            'sources': [{'path': str(Path(path).resolve()), 'sha256': fingerprint(path)} for path in sources]}


def reusable(path, receipt, evidence, seconds):
    if not path.exists() or not receipt.exists(): return False
    record = json.loads(receipt.read_text())
    return record.get('inputs') == evidence and record.get('output_sha256') == sha(path) and valid(path, seconds)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('manifest'); parser.add_argument('engine')
    parser.add_argument('--working-dir', required=True, help='private directory outside public output')
    parser.add_argument('--covers-only', action='store_true')
    args = parser.parse_args(); engine = Path(args.engine).resolve(); work = Path(args.working_dir).resolve()
    inputs = Inputs(); failures = []
    for job in json.loads(inputs.read(args.manifest)):
        out = Path(job['output']).resolve()
        # Reject work storage anywhere within the run's output tree, not just next to this film.
        public_roots = [p for p in (out.parent, *out.parents) if p.name in ('output', 'delivery')]
        if work.is_relative_to(out.parent) or any(work.is_relative_to(p) for p in public_roots):
            raise ValueError('Render logs and receipts must stay outside public output')
        if job.get('run_id') != inputs.run_id: raise ValueError('Composition run does not match active workflow')
        evidence = provenance(job, inputs)
        work.mkdir(parents=True, exist_ok=True); out.parent.mkdir(parents=True, exist_ok=True)
        receipt = work / f"{job['id']}.render.json"
        log = work / f"{job['id']}.render.log"
        with log.open('a') as stream:
            if not args.covers_only and not reusable(out, receipt, evidence, float(job['duration'])):
                temp = work / f"{job['id']}.partial.mp4"
                subprocess.run([str(engine/'node_modules/.bin/remotion'), 'render', 'src/index.ts', 'CampaignFilm', str(temp), '--props='+job['props'], '--codec=h264', '--crf=19', '--concurrency=2', '--timeout=60000', '--log=error'], cwd=engine, stdout=stream, stderr=subprocess.STDOUT, check=True)
                if not valid(temp, float(job['duration'])): raise RuntimeError('Incomplete video: '+job['id'])
                if provenance(job) != evidence: raise RuntimeError('Source inputs changed during render')
                temp.replace(out)
                receipt.write_text(json.dumps({'inputs': evidence, 'output_sha256': sha(out), 'status': 'rendered_unreviewed'}, indent=2))
            props = json.loads(Path(job['props']).read_text()); props.update(captions=[], audio=None, music=None)
            coverprops = work / f"{job['id']}.cover-props.json"; coverprops.write_text(json.dumps(props))
            try:
                subprocess.run([str(engine/'node_modules/.bin/remotion'), 'still', 'src/index.ts', 'CampaignFilm', str(out.with_suffix('.cover.png')), '--props='+str(coverprops), '--frame=40', '--timeout=60000', '--log=error'], cwd=engine, stdout=stream, stderr=subprocess.STDOUT, check=True)
            except subprocess.CalledProcessError: failures.append(job['id'])
        print('Rendered '+job['id'], flush=True)
    inputs.finish()
    if failures: print('Pending covers: '+', '.join(failures))

if __name__ == '__main__': main()
