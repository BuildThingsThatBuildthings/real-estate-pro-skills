"""Record bytes actually read by AIA renderers; identity comes from the runner."""
import hashlib
import json
import os
from pathlib import Path


class Inputs:
    def __init__(self):
        self.run_id = os.environ.get('AIA_RUN_ID')
        if not self.run_id or not os.environ.get('AIA_PRODUCTION_RECEIPT'):
            raise ValueError('Production must run through the AIA workflow runner')
        self.receipt = Path(os.environ['AIA_PRODUCTION_RECEIPT']).resolve()
        self.declared = {str(Path(item['path']).resolve()): item for item in json.loads(os.environ.get('AIA_TASK_INPUTS_JSON', '[]'))}
        self.consumed = {}

    def read(self, path):
        path = Path(path).resolve(); key = str(path)
        if key not in self.declared:
            raise ValueError('Renderer read an undeclared input: '+key)
        data = path.read_bytes(); digest = hashlib.sha256(data).hexdigest()
        declaration = self.declared[key]
        if declaration.get('sha256') != digest:
            raise ValueError('Renderer input hash changed: '+key)
        self.consumed[key] = {**declaration, 'path': key, 'sha256': digest}
        return data

    def finish(self):
        if set(self.consumed) != set(self.declared):
            raise ValueError('Declared inputs were not actually consumed: '+str(sorted(set(self.declared)-set(self.consumed))))
        if any(part in ('output', 'delivery') for part in self.receipt.parts):
            raise ValueError('Production receipt must stay in private working storage')
        self.receipt.parent.mkdir(parents=True, exist_ok=True)
        self.receipt.write_text(json.dumps({'run_id': self.run_id, 'consumed': list(self.consumed.values())}, indent=2))
