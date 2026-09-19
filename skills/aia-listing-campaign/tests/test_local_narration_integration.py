"""Opt-in real model test. Dependencies stay external; temporary generated audio is removed."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT=Path(__file__).resolve().parents[1]/'scripts/local_narration.py'

@unittest.skipUnless(os.environ.get('AIA_KOKORO_MODEL') and os.environ.get('AIA_KOKORO_VOICES'), 'Set licensed model and voice paths for real narration test')
class RealNarrationTests(unittest.TestCase):
    def test_fresh_independent_speech_and_consumed_inputs(self):
        import numpy as np
        import soundfile as sf
        model=Path(os.environ['AIA_KOKORO_MODEL']).resolve(); voices=Path(os.environ['AIA_KOKORO_VOICES']).resolve()
        if not model.is_file() or not voices.is_file():self.fail('Configured licensed model assets are absent')
        with tempfile.TemporaryDirectory(prefix='aia-fictional-narration-') as directory:
            root=Path(directory);(root/'context').mkdir();(root/'working').mkdir()
            config=root/'context/local-narration.json'
            config.write_text(json.dumps({'run_id':'fictional-audio-test','model':str(model),'voices':str(voices),'voice':'af_heart','speed':1.04,'commercial_use':True,'license_url':'https://huggingface.co/hexgrad/Kokoro-82M','narrations':[{'composition_id':'fictional-test','segments':[{'text':'This is a fictional home.','pause_after':.25},{'text':'The story returns to the garden.','pause_after':.4}]}]}))
            records=[]
            for label,path in [('script',config),('licensed-model',model),('licensed-voices',voices)]:
                with path.open('rb') as source:digest=hashlib.file_digest(source,'sha256').hexdigest()
                records.append({'path':str(path.resolve()),'sha256':digest,'origin':'original','source_id':label})
            receipt=root/'working/production-receipt.json'
            env={**os.environ,'AIA_RUN_ID':'fictional-audio-test','AIA_TASK_INPUTS_JSON':json.dumps(records),'AIA_PRODUCTION_RECEIPT':str(receipt)}
            result=subprocess.run([sys.executable,str(SCRIPT),str(root)],env=env,text=True,capture_output=True,timeout=180)
            self.assertEqual(result.returncode,0,result.stdout+'\n'+result.stderr)
            audio,rate=sf.read(root/'assets/local-narration/fictional-test.wav')
            self.assertEqual(rate,24000);self.assertGreater(len(audio)/rate,2);self.assertGreater(float(np.max(np.abs(audio))),.01)
            timeline=json.loads((root/'assets/local-narration/narration-timelines.json').read_text())[0]
            self.assertEqual(len(timeline['speech_segments']),2)
            self.assertAlmostEqual(timeline['duration'],len(audio)/rate,delta=.002)
            self.assertEqual({r['path'] for r in json.loads(receipt.read_text())['consumed']},{str(p.resolve()) for p in (config,model,voices)})
            self.assertFalse((root/'delivery').exists());self.assertFalse((root/'output').exists())

if __name__=='__main__':unittest.main()
