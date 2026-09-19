#!/usr/bin/env python3
"""Run installed AIA operations with observed source receipts; execution is not approval."""
import argparse
import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

from run_storage import validate_root

BUNDLE = Path(__file__).resolve().parents[3]
MEDIA_DOCUMENTS = {'.mp4', '.mov', '.webm', '.png', '.jpg', '.jpeg', '.pdf', '.docx'}
SUCCESS = {'executed', 'externally_verified'}


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def resolve_skill(name):
    if not isinstance(name, str) or not re.fullmatch(r'[a-z0-9-]+', name):
        raise ValueError('Use one installed AIA skill name per task')
    folder = (BUNDLE / ('content-machine' if name == 'content-machine' else 'skills/' + name)).resolve()
    if not (folder / 'SKILL.md').is_file():
        raise ValueError('Installed AIA skill missing: ' + name)
    return folder


def inside(root, value):
    path = (root / value).resolve()
    if not path.is_relative_to(root) or path == root:
        raise ValueError('Output must remain within this run')
    return path


def entrypoint(command, folder, root):
    if not isinstance(command, list) or not command or not all(isinstance(a, str) for a in command):
        raise ValueError('Use a nonempty argv array')
    first = Path(command[0]).name
    suffixes = {'.py'} if re.fullmatch(r'python(?:3(?:\.\d+)?)?', first) else (
        {'.js', '.mjs'} if first == 'node' else {'.sh'} if first in ('bash', 'sh', 'zsh') else set())
    if suffixes:
        located = shutil.which(command[0])
        trusted = {Path(sys.executable).resolve()}
        if shutil.which(first):
            trusted.add(Path(shutil.which(first)).resolve())
        if not located or Path(located).resolve() not in trusted:
            raise ValueError('Interpreter must resolve to the installed runtime, not a lookalike executable')
        if len(command) < 2 or command[1].startswith('-'):
            raise ValueError('Interpreter must be followed immediately by the AIA script')
        script = (root / command[1]).resolve()
        if script.suffix not in suffixes:
            raise ValueError('Interpreter and AIA script extension do not match')
    else:
        script = (root / command[0]).resolve()
        if not os.access(script, os.X_OK):
            raise ValueError('Use a supported interpreter or executable AIA script')
    if not script.is_file() or not script.is_relative_to(folder / 'scripts'):
        raise ValueError('Command must execute the governing AIA skill script')
    return script


def receipt_path(task, root):
    value = task.get('production_receipt')
    if not value:
        raise ValueError('Production task requires an observed-input receipt')
    path = inside(root, value)
    if not path.is_relative_to(root / 'working'):
        raise ValueError('Production receipt belongs in private working storage')
    return path


def inputs_for(task, flow, root, ready):
    inputs, seen = [], set()
    tasks = {t['id']: t for t in flow['tasks']}
    for source in task.get('inputs', []):
        item = dict(source)
        path = (root / item['path']).resolve()
        item['path'] = str(path)
        if path in seen:
            raise ValueError('Duplicate declared input')
        seen.add(path)
        if item.get('origin') == 'generated':
            producer = tasks.get(item.get('producer_task'))
            if item.get('run_id') != flow['run_id'] or not path.is_relative_to(root):
                raise ValueError('Prior generated input cannot enter fresh run')
            if not producer or producer['id'] not in task.get('depends_on', []) or producer.get('kind', 'production') not in ('production', 'external'):
                raise ValueError('Generated input requires a production dependency')
            output = next((o for o in producer.get('outputs', []) if inside(root, o) == path), None)
            if output is None:
                raise ValueError('Generated input is not a declared producer output')
            if not ready:
                inputs.append(item)
                continue
            if producer.get('status') not in SUCCESS or producer.get('run_id') != flow['run_id'] or producer.get('freshness') != 'verified':
                raise ValueError('Generated source producer has no verified execution')
            expected = producer.get('hashes', {}).get(output)
            if not expected or (item.get('sha256') and item['sha256'] != expected):
                raise ValueError('Generated input does not match producer output hash')
            item['sha256'] = expected
        elif item.get('origin') != 'original' or not item.get('source_id'):
            raise ValueError('Input requires original source identity or current-run producer evidence')
        if not path.is_file() or digest(path) != item.get('sha256'):
            raise ValueError('Input source changed or missing')
        inputs.append(item)
    return inputs


def observed_inputs(task, flow, root, expected):
    path = receipt_path(task, root)
    if not path.is_file():
        raise ValueError('Production receipt was not created')
    receipt = json.loads(path.read_text())
    if receipt.get('run_id') != flow['run_id'] or not isinstance(receipt.get('consumed'), list):
        raise ValueError('Production receipt has no current-run consumed sources')
    def normalize(items):
        result = {}
        for item in items:
            path = (root / item['path']).resolve()
            if str(path) in result:
                raise ValueError('Duplicate consumed source')
            keys = ('sha256', 'origin', 'source_id') if item.get('origin') == 'original' else (
                'sha256', 'origin', 'run_id', 'producer_task')
            result[str(path)] = {key: item.get(key) for key in keys}
        return result
    if not expected or normalize(receipt['consumed']) != normalize(expected):
        raise ValueError('Actual consumed inputs differ from declared production sources')
    # Check bytes again after the process; observed hashes cannot bless changed inputs.
    for item in expected:
        if digest(item['path']) != item['sha256']:
            raise ValueError('Production input changed during execution')
    return digest(path)


def verify_external(task, flow, root, inputs):
    record = inside(root, task['external_record'])
    script = BUNDLE / 'skills/aia-listing-campaign/scripts/external_operation.py'
    spec = importlib.util.spec_from_file_location('aia_external_operation', script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    receipt = module.verify(record, expected_run_id=flow['run_id'])
    if receipt.get('scope', 'production') != flow.get('scope', 'production'):
        raise ValueError('Test fixture evidence cannot become production evidence')
    if receipt.get('task_id') != task['id'] or receipt.get('skill') != task['skill'] or Path(receipt['root']).resolve() != root:
        raise ValueError('External operation identity does not match workflow task')
    if set(receipt.get('hashes', {})) != set(task['outputs']):
        raise ValueError('External operation output set differs from workflow')
    # Use the same observed-source check as local production; the verified record
    # is the private production receipt, never a status supplied by the caller.
    checker = {**task, 'production_receipt': task['external_record']}
    observed_inputs(checker, flow, root, inputs)
    return receipt, digest(script), digest(record)


def check_task(task, flow, root, ready=False):
    if not re.fullmatch(r'[a-zA-Z0-9_-]+', task.get('id', '')):
        raise ValueError('Use a simple task ID')
    folder = resolve_skill(task.get('skill'))
    kind = task.get('kind', 'production')
    if kind == 'external':
        if task.get('command') or not task.get('outputs') or not task.get('inputs'):
            raise ValueError('External operations need declared inputs/outputs and no fabricated local command')
        record = inside(root, task['external_record'])
        if not record.is_relative_to(root / 'working'):
            raise ValueError('External operation record must remain private')
        for output in task['outputs']:
            inside(root, output)
        inputs = inputs_for(task, flow, root, ready or task.get('status') == 'externally_verified')
        skill_hash = digest(folder / 'SKILL.md')
        if task.get('status') == 'executed':
            raise ValueError('External operation cannot be mislabeled locally executed')
        if task.get('status') == 'externally_verified':
            receipt, script_hash, record_hash = verify_external(task, flow, root, inputs)
            if task.get('entrypoint_sha256') != script_hash or task.get('receipt_sha256') != record_hash or task.get('skill_sha256') != skill_hash or task.get('hashes') != receipt['hashes']:
                raise ValueError('External operation evidence changed since verification')
        return skill_hash, None, inputs
    if kind not in ('production', 'check'):
        raise ValueError('Task kind must be production, external or check')
    script = entrypoint(task.get('command'), folder, root)
    skill_hash, script_hash = digest(folder / 'SKILL.md'), digest(script)
    outputs = task.get('outputs', [])
    if not outputs and kind == 'production':
        raise ValueError('Task requires an expected output')
    if kind == 'check' and (task.get('deliverables') or any(Path(o).suffix.lower() in MEDIA_DOCUMENTS for o in outputs)):
        raise ValueError('Check tasks cannot produce or count media/document deliverables')
    for output in outputs:
        path = inside(root, output)
        if task.get('status', 'pending') == 'pending' and path.exists():
            raise ValueError('Fresh task output already exists: ' + output)
    if kind == 'production':
        private_receipt = receipt_path(task, root)
        if task.get('status', 'pending') == 'pending' and private_receipt.exists():
            raise ValueError('Fresh production receipt already exists')
        if not task.get('inputs'):
            raise ValueError('Production requires declared source inputs')
    executed = task.get('status') == 'executed'
    inputs = inputs_for(task, flow, root, ready or executed)
    if executed:
        if task.get('run_id') != flow['run_id'] or task.get('skill_sha256') != skill_hash or task.get('entrypoint_sha256') != script_hash:
            raise ValueError('Stale execution or changed skill/script revision: ' + task['id'])
        if set(task.get('hashes', {})) != set(outputs) or any(not inside(root, p).is_file() or digest(inside(root, p)) != h for p, h in task['hashes'].items()):
            raise ValueError('Executed output is missing or changed: ' + task['id'])
        if kind == 'production' and (task.get('freshness') != 'verified' or observed_inputs(task, flow, root, inputs) != task.get('receipt_sha256')):
            raise ValueError('Fresh production evidence changed or missing')
    return skill_hash, script_hash, inputs


def save(path, data):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(data, indent=2))
    temp.replace(path)


def execute(path):
    path = Path(path)
    flow = json.loads(path.read_text())
    root = validate_root(flow['root'], flow.get('scope', 'production'))
    if not flow.get('run_id'):
        raise ValueError('Fresh run_id is required; legacy runs cannot be relabeled')
    tasks = flow['tasks']
    ids = {t['id']: t for t in tasks}
    if len(ids) != len(tasks):
        raise ValueError('Duplicate task IDs')
    output_owners = set()
    receipt_owners = set()
    for task in tasks:
        if any(d not in ids for d in task.get('depends_on', [])):
            raise ValueError('Unknown dependency: ' + task['id'])
        if task['id'] in task.get('depends_on', []):
            raise ValueError('Self dependency')
        for out in task.get('outputs', []):
            normalized = inside(root, out)
            if normalized in output_owners:
                raise ValueError('Two tasks cannot own the same output')
            output_owners.add(normalized)
        if task.get('kind', 'production') in ('production', 'external'):
            private_receipt = receipt_path(task, root) if task.get('kind', 'production') == 'production' else inside(root, task['external_record'])
            if private_receipt in receipt_owners:
                raise ValueError('Each production task requires its own receipt')
            receipt_owners.add(private_receipt)
        check_task(task, flow, root)
    logs = root / 'working/workflow-logs'
    logs.mkdir(parents=True, exist_ok=True)
    progress = True
    while progress:
        progress = False
        for task in tasks:
            if task.get('status', 'pending') != 'pending':
                continue
            if any(ids[d].get('status') not in SUCCESS for d in task.get('depends_on', [])):
                continue
            if task.get('kind') == 'external':
                record = inside(root, task['external_record'])
                if not record.is_file() or json.loads(record.read_text()).get('status') != 'externally_verified':
                    continue
                skill_hash, _, inputs = check_task(task, flow, root, ready=True)
                receipt, script_hash, record_hash = verify_external(task, flow, root, inputs)
                task.update(status='externally_verified', freshness='verified', run_id=flow['run_id'],
                            skill_sha256=skill_hash, entrypoint_sha256=script_hash, receipt_sha256=record_hash,
                            hashes=receipt['hashes'], inputs=inputs)
                save(path, flow)
                print(task['id'] + ': externally_verified', flush=True)
                progress = True
                continue
            skill_hash, script_hash, inputs = check_task(task, flow, root, ready=True)
            task['inputs'] = inputs
            task['status'] = 'running'
            save(path, flow)
            env = os.environ.copy()
            env['AIA_RUN_ID'] = flow['run_id']
            env['AIA_TASK_INPUTS_JSON'] = json.dumps(inputs)
            if task.get('kind', 'production') == 'production':
                env['AIA_PRODUCTION_RECEIPT'] = str(receipt_path(task, root))
            else:
                env.pop('AIA_PRODUCTION_RECEIPT', None)
            result = subprocess.run(task['command'], cwd=root, env=env, text=True, capture_output=True)
            (logs / (task['id'] + '.log')).write_text(result.stdout + '\n' + result.stderr)
            missing = [p for p in task['outputs'] if not inside(root, p).is_file()]
            task.update(status='executed' if result.returncode == 0 and not missing else 'failed',
                        exit_code=result.returncode, missing_outputs=missing,
                        executed_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                        run_id=flow['run_id'], skill_sha256=skill_hash, entrypoint_sha256=script_hash,
                        freshness='not_proven')
            if task['status'] == 'executed':
                try:
                    folder = resolve_skill(task['skill'])
                    if digest(folder / 'SKILL.md') != skill_hash or digest(entrypoint(task['command'], folder, root)) != script_hash:
                        raise ValueError('Skill or script changed during execution')
                    if task.get('kind', 'production') == 'production':
                        task['receipt_sha256'] = observed_inputs(task, flow, root, inputs)
                        task['freshness'] = 'verified'
                    else:
                        task['freshness'] = 'not_applicable_check'
                    task['hashes'] = {p: digest(inside(root, p)) for p in task['outputs']}
                except (ValueError, OSError, KeyError, TypeError) as exc:
                    task['status'] = 'failed'
                    task['provenance_error'] = str(exc)
            save(path, flow)
            print(task['id'] + ': ' + task['status'], flush=True)
            progress = True
    flow['execution_summary'] = {
        'unfinished': [t['id'] for t in tasks if t.get('status') not in SUCCESS],
        'fresh_production_tasks': [t['id'] for t in tasks if t.get('status') in SUCCESS and t.get('freshness') == 'verified'],
        'creative_acceptance': 'separate required review; execution is not approval',
    }
    save(path, flow)
    return flow


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('workflow')
    args = parser.parse_args()
    print(json.dumps(execute(args.workflow)['execution_summary'], indent=2))
