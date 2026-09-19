import copy
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path
import sys
import shutil
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).parents[1]/'scripts'))
SPEC = importlib.util.spec_from_file_location('workflow', Path(__file__).parents[1] / 'scripts/run_workflow.py')
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)

PRODUCTION = '''import os,json,hashlib
from pathlib import Path
inputs=json.loads(os.environ['AIA_TASK_INPUTS_JSON'])
consumed=[]
for item in inputs:
    body=Path(item['path']).read_bytes()
    consumed.append({**item,'sha256':hashlib.sha256(body).hexdigest()})
Path(OUTPUT).write_text('new output')
p=Path(os.environ['AIA_PRODUCTION_RECEIPT']);p.parent.mkdir(parents=True,exist_ok=True)
p.write_text(json.dumps({'run_id':os.environ['AIA_RUN_ID'],'consumed':consumed}))
'''


class WorkflowTests(unittest.TestCase):
    def setup_flow(self, directory, body=None):
        root = Path(directory)
        folder = root / 'bundle/skills/aia-listing-campaign'
        (folder / 'scripts').mkdir(parents=True)
        (folder / 'SKILL.md').write_text('AIA test skill')
        script = folder / 'scripts/render.py'
        script.write_text(body if body is not None else PRODUCTION.replace('OUTPUT', repr('new.txt')))
        run = root / 'run'
        run.mkdir()
        original = root / 'original.txt'
        original.write_text('original input')
        flow = {'scope': 'test', 'run_id': 'fresh-test', 'root': str(run), 'tasks': [{
            'id': 'render', 'skill': 'aia-listing-campaign', 'command': [sys.executable, str(script)],
            'outputs': ['new.txt'], 'production_receipt': 'working/render-receipt.json',
            'inputs': [{'path': str(original), 'sha256': m.digest(original), 'origin': 'original', 'source_id': 'supplied-original'}],
        }]}
        path = root / 'workflow.json'
        path.write_text(json.dumps(flow))
        return path, flow, root / 'bundle'

    def test_script_runs_and_resume_checks_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            path, flow, bundle = self.setup_flow(directory)
            with patch.object(m, 'BUNDLE', bundle):
                result = m.execute(path)
                self.assertEqual(result['tasks'][0]['freshness'], 'verified')
                m.execute(path)
                (Path(flow['root']) / 'new.txt').write_text('tampered')
                with self.assertRaisesRegex(ValueError, 'missing or changed'):
                    m.execute(path)

    def test_changed_entrypoint_refuses_resume_without_overwriting_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            path, flow, bundle = self.setup_flow(directory)
            with patch.object(m, 'BUNDLE', bundle):
                first = m.execute(path)
                old_hash = first['tasks'][0]['entrypoint_sha256']
                Path(flow['tasks'][0]['command'][1]).write_text('pass')
                with self.assertRaisesRegex(ValueError, 'script revision'):
                    m.execute(path)
                self.assertEqual(json.loads(path.read_text())['tasks'][0]['entrypoint_sha256'], old_hash)

    def test_failed_branch_does_not_stop_independent_script(self):
        with tempfile.TemporaryDirectory() as directory:
            path, flow, bundle = self.setup_flow(directory)
            script = bundle / 'skills/aia-listing-campaign/scripts/fail.py'
            script.write_text('raise SystemExit(1)')
            flow['tasks'].insert(0, {'id': 'failed-check', 'skill': 'aia-listing-campaign', 'kind': 'check',
                                    'command': [sys.executable, str(script)], 'outputs': ['check.txt']})
            path.write_text(json.dumps(flow))
            with patch.object(m, 'BUNDLE', bundle):
                result = m.execute(path)
            self.assertEqual([t['status'] for t in result['tasks']], ['failed', 'executed'])

    def test_zero_exit_without_artifact_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            path, flow, bundle = self.setup_flow(directory, 'pass')
            with patch.object(m, 'BUNDLE', bundle):
                self.assertEqual(m.execute(path)['tasks'][0]['status'], 'failed')

    def test_existing_output_and_unknown_skill_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            path, flow, bundle = self.setup_flow(directory)
            output = Path(flow['root']) / 'new.txt'
            output.write_text('old')
            with patch.object(m, 'BUNDLE', bundle), self.assertRaises(ValueError):
                m.execute(path)
            output.unlink()
            flow['tasks'][0]['skill'] = 'made-up'
            path.write_text(json.dumps(flow))
            with patch.object(m, 'BUNDLE', bundle), self.assertRaises(ValueError):
                m.execute(path)

    def test_prior_generated_source_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            path, flow, bundle = self.setup_flow(directory)
            flow['tasks'][0]['inputs'][0].update(origin='generated', run_id='old-run')
            path.write_text(json.dumps(flow))
            with patch.object(m, 'BUNDLE', bundle), self.assertRaisesRegex(ValueError, 'Prior generated'):
                m.execute(path)

    def test_inline_and_extensionless_decoy_commands_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            path, flow, bundle = self.setup_flow(directory)
            legitimate = flow['tasks'][0]['command'][1]
            attacker = Path(directory) / 'extensionless'
            attacker.write_text("print('wrong program')")
            for command in ([sys.executable, '-c', 'pass', legitimate],
                            [sys.executable, str(attacker), legitimate],
                            ['/bin/echo', legitimate]):
                flow['tasks'][0]['command'] = command
                path.write_text(json.dumps(flow))
                with patch.object(m, 'BUNDLE', bundle), self.assertRaises(ValueError):
                    m.execute(path)

    def test_lookalike_interpreter_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            path, flow, bundle = self.setup_flow(directory)
            fake = Path(directory) / 'python3'
            fake.write_text('#!/bin/sh\nexit 0\n')
            fake.chmod(0o755)
            flow['tasks'][0]['command'][0] = str(fake)
            path.write_text(json.dumps(flow))
            with patch.object(m, 'BUNDLE', bundle), self.assertRaisesRegex(ValueError, 'lookalike'):
                m.execute(path)

    def test_future_generated_input_waits_for_producer(self):
        with tempfile.TemporaryDirectory() as directory:
            path, flow, bundle = self.setup_flow(directory)
            second = bundle / 'skills/aia-listing-campaign/scripts/second.py'
            second.write_text(PRODUCTION.replace('OUTPUT', repr('second.txt')))
            flow['tasks'].append({'id': 'second', 'skill': 'aia-listing-campaign',
                'command': [sys.executable, str(second)], 'outputs': ['second.txt'],
                'depends_on': ['render'], 'production_receipt': 'working/second-receipt.json',
                'inputs': [{'path': str(Path(flow['root']) / 'new.txt'), 'origin': 'generated',
                            'run_id': 'fresh-test', 'producer_task': 'render'}]})
            # Consumer first verifies graph ordering is independent of array ordering.
            flow['tasks'].reverse()
            path.write_text(json.dumps(flow))
            with patch.object(m, 'BUNDLE', bundle):
                result = m.execute(path)
                self.assertTrue(all(t['freshness'] == 'verified' for t in result['tasks']))
                self.assertEqual(result['execution_summary']['unfinished'], [])
                m.execute(path)

    def test_missing_or_forged_production_receipt_cannot_count(self):
        with tempfile.TemporaryDirectory() as directory:
            body = PRODUCTION.replace('OUTPUT', repr('new.txt')).replace("'consumed':consumed", "'consumed':[]")
            path, flow, bundle = self.setup_flow(directory, body)
            with patch.object(m, 'BUNDLE', bundle):
                task = m.execute(path)['tasks'][0]
                self.assertEqual(task['status'], 'failed')
                self.assertEqual(task['freshness'], 'not_proven')
                self.assertIn('consumed inputs', task['provenance_error'])

    def test_extra_actual_source_cannot_hide_behind_declared_input(self):
        with tempfile.TemporaryDirectory() as directory:
            body = PRODUCTION.replace('OUTPUT', repr('new.txt')).replace("'consumed':consumed", "'consumed':consumed+[{'path':'hidden-old.mp4','sha256':'old','origin':'original','source_id':'lie'}]")
            path, flow, bundle = self.setup_flow(directory, body)
            with patch.object(m, 'BUNDLE', bundle):
                self.assertEqual(m.execute(path)['tasks'][0]['status'], 'failed')

    def test_check_cannot_disguise_media_production(self):
        with tempfile.TemporaryDirectory() as directory:
            path, flow, bundle = self.setup_flow(directory)
            flow['tasks'][0].update(kind='check', outputs=['fake.mp4'])
            path.write_text(json.dumps(flow))
            with patch.object(m, 'BUNDLE', bundle), self.assertRaisesRegex(ValueError, 'cannot produce'):
                m.execute(path)

    def test_no_input_or_receipt_production_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path, flow, bundle = self.setup_flow(directory)
            baseline = copy.deepcopy(flow)
            for key in ('inputs', 'production_receipt'):
                flow = copy.deepcopy(baseline)
                del flow['tasks'][0][key]
                path.write_text(json.dumps(flow))
                with patch.object(m, 'BUNDLE', bundle), self.assertRaises(ValueError):
                    m.execute(path)

    def test_external_authoring_requires_evidence_and_feeds_local_producer(self):
        with tempfile.TemporaryDirectory() as directory:
            path, flow, bundle = self.setup_flow(directory)
            external_script = bundle / 'skills/aia-listing-campaign/scripts/external_operation.py'
            shutil.copyfile(Path(m.__file__).with_name('external_operation.py'), external_script)
            external_spec = importlib.util.spec_from_file_location('external_fixture', external_script)
            external = importlib.util.module_from_spec(external_spec)
            external_spec.loader.exec_module(external)
            original_inputs = copy.deepcopy(flow['tasks'][0]['inputs'])
            author = {'id': 'author', 'skill': 'aia-listing-campaign', 'kind': 'external',
                      'external_record': 'working/author.json', 'outputs': ['authored.txt'], 'inputs': original_inputs}
            flow['tasks'][0].update(depends_on=['author'], inputs=[{
                'path': str(Path(flow['root']) / 'authored.txt'), 'origin': 'generated',
                'run_id': flow['run_id'], 'producer_task': 'author'}])
            flow['tasks'].insert(0, author)
            path.write_text(json.dumps(flow))
            with patch.object(m, 'BUNDLE', bundle):
                pending = m.execute(path)
                self.assertEqual(pending['execution_summary']['unfinished'], ['author', 'render'])
                root = Path(flow['root'])
                record_path = root / author['external_record']
                external.begin({'run_id': flow['run_id'], 'task_id': 'author', 'skill': author['skill'],
                    'scope': 'test', 'operation': 'agent_authoring', 'root': str(root), 'inputs': original_inputs,
                    'outputs': author['outputs']}, record_path)
                # A test fixture simulates the external action; it is not production evidence.
                output = root / 'authored.txt'
                output.write_text('new authored fixture')
                action = root / 'working/tool-response.txt'
                action.write_text('simulated tool response for regression fixture')
                now = datetime.now(timezone.utc).isoformat()
                evidence = root / 'working/evidence.json'
                evidence.write_text(json.dumps({'run_id': flow['run_id'], 'task_id': 'author',
                    'tool': 'test-fixture', 'action_id': 'fixture-action', 'recorded_at': now,
                    'inspection': {'reviewer': 'test', 'reviewed_at': now, 'outcome': 'accepted'},
                    'source_hashes': {i['path']: i['sha256'] for i in original_inputs},
                    'outputs': [{'path': 'authored.txt', 'sha256': m.digest(output)}],
                    'evidence_files': [str(action)]}))
                external.complete(record_path, evidence)
                result = m.execute(path)
                self.assertEqual([t['status'] for t in result['tasks']], ['externally_verified', 'executed'])
                self.assertEqual(result['execution_summary']['unfinished'], [])
                m.execute(path)
                action.write_text('changed tool evidence')
                with self.assertRaisesRegex(ValueError, 'evidence or output changed'):
                    m.execute(path)

    def test_external_status_without_begin_and_action_evidence_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path, flow, bundle = self.setup_flow(directory)
            script = bundle / 'skills/aia-listing-campaign/scripts/external_operation.py'
            shutil.copyfile(Path(m.__file__).with_name('external_operation.py'), script)
            task = flow['tasks'][0]
            task.pop('command')
            task.update(kind='external', external_record='working/fake.json')
            record = Path(flow['root']) / 'working/fake.json'
            record.parent.mkdir()
            record.write_text(json.dumps({'status': 'externally_verified', 'root': flow['root']}))
            path.write_text(json.dumps(flow))
            with patch.object(m, 'BUNDLE', bundle), self.assertRaises(ValueError):
                m.execute(path)


if __name__ == '__main__':
    unittest.main()
