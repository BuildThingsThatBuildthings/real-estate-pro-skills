import copy
import importlib.util
import sys
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
SCRIPT=Path(__file__).resolve().parents[1]/'scripts/edit_camera_sequence.py'
spec=importlib.util.spec_from_file_location('camera_editor', SCRIPT)
editor=importlib.util.module_from_spec(spec);spec.loader.exec_module(editor)

class CameraContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.video=self.root/'camera.mp4';self.video.write_bytes(b'camera')
        self.config={'run_id':'fresh','composition_id':'teaser-vertical','kind':'teaser','working':str(self.root/'working'), 'output':str(self.root/'delivery/teaser.mp4'), 'width':1920,'height':1080,'shots':[{'path':str(self.video),'in':0,'seconds':8,'status':'reviewed','origin':'generated','origin_run_id':'fresh','source_sha256':editor.digest(self.video)}], 'music':{'path':'music.wav','rights_basis':'test license','attribution':'Test music'}}
    def tearDown(self):self.tmp.cleanup()
    def probe(self,path):return {'streams':[{'codec_type':'video','width':1920,'height':1080},{'codec_type':'audio'}], 'format':{'duration':'100'}}
    def test_valid_explicit_timeline(self):self.assertEqual(editor.validate(self.config,self.probe),8)
    def test_rejects_old_generation_and_modified_bytes(self):
        for change in [{'origin_run_id':'old'},{'source_sha256':'false'}]:
            with self.subTest(change=change):
                c=copy.deepcopy(self.config);c['shots'][0].update(change)
                with self.assertRaises(ValueError):editor.validate(c,self.probe)
    def test_flagship_requires_narration(self):
        c=copy.deepcopy(self.config);c['kind']='flagship';c['shots'][0]['seconds']=80
        with self.assertRaisesRegex(ValueError,'narration'):editor.validate(c,self.probe)
    def test_rejects_implicit_crop_and_repeated_padding(self):
        c=copy.deepcopy(self.config);c['width']=1080;c['height']=1920
        with self.assertRaisesRegex(ValueError,'crop'):editor.validate(c,self.probe)
        c=copy.deepcopy(self.config);c['shots'].append(copy.deepcopy(c['shots'][0]))
        with self.assertRaisesRegex(ValueError,'Repeated'):editor.validate(c,self.probe)
    def test_rejects_stills_speed_and_bad_caption(self):
        for field,value in [('path','photo.png'),('speed',.5)]:
            c=copy.deepcopy(self.config);c['shots'][0][field]=value
            with self.assertRaises(ValueError):editor.validate(c,self.probe)
        c=copy.deepcopy(self.config);c['captions']=[{'start':0,'end':9,'text':'too long'}]
        with self.assertRaises(ValueError):editor.validate(c,self.probe)
    def test_rejects_working_inside_delivery(self):
        self.config['working']=str(self.root/'delivery/working')
        with self.assertRaisesRegex(ValueError,'internal'):editor.validate(self.config,self.probe)

    @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'),'FFmpeg required')
    def test_real_render_has_video_audio_and_no_sidecars(self):
        font=next((p for p in [Path('/System/Library/Fonts/Supplemental/Arial.ttf'),Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')] if p.exists()),None)
        if not font:self.skipTest('Test font unavailable')
        subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','testsrc2=size=320x180:rate=24','-t','8','-c:v','libx264',str(self.video)],check=True)
        audio=self.root/'sound.wav'
        subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','sine=frequency=220:duration=8','-ar','48000',str(audio)],check=True)
        c=self.config;c.update(width=320,height=180,fps=24,font=str(font),caption_size=12,captions=[{'start':1,'end':3,'text':'Actual rendered subtitle'}],narration={'path':str(audio),'rights_basis':'Original synthetic test tone'},sfx=[{'path':str(audio),'rights_basis':'Original test tone','at':4,'seconds':1,'gain':.1}])
        c['shots'][0]['source_sha256']=editor.digest(self.video);c['music']['path']=str(audio)
        identities=[{'path':str(self.video.resolve()),'origin':'generated','run_id':'fresh','producer_task':'camera-shot'}, {'path':str(audio.resolve()),'origin':'original','source_id':'test-tone'}, {'path':str(font.resolve()),'origin':'original','source_id':'system-font'}]
        task_receipt=self.root/'working/task-receipt.json'
        with patch.dict('os.environ',{'AIA_RUN_ID':'fresh','AIA_TASK_INPUTS_JSON':json.dumps(identities),'AIA_PRODUCTION_RECEIPT':str(task_receipt)}):
            output=editor.render(c)
        meta=editor.probe(output)
        self.assertEqual({s['codec_type'] for s in meta['streams']},{'video','audio'})
        self.assertAlmostEqual(float(meta['format']['duration']),8,delta=.15)
        self.assertEqual([p.name for p in output.parent.iterdir()],['teaser.mp4'])
        receipt=json.loads((self.root/'working/teaser-vertical/render-receipt.json').read_text())
        self.assertFalse(receipt['full_sound']);self.assertEqual(receipt['consumed_sources'][0]['sha256'],editor.digest(self.video))
        self.assertEqual({p['path'] for p in receipt['consumed']},{str(self.video.resolve()),str(audio.resolve()),str(font.resolve())})
        self.assertEqual(json.loads(task_receipt.read_text())['consumed'][0]['producer_task'],'camera-shot')

if __name__=='__main__':unittest.main()
