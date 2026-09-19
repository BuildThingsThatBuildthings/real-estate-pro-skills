import copy
import hashlib
import math
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from render_panorama_clip import validate, view_at, command_text, render


class PanoramaTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        image = Image.new('RGB', (512, 256))
        draw = ImageDraw.Draw(image)
        for x in range(512):
            draw.line((x, 0, x, 255), fill=(x % 256, (x * 3) % 256, 110))
        draw.rectangle((240, 95, 285, 160), fill='white')
        self.source = self.root / 'original.png'
        image.save(self.source)
        vfov = math.degrees(2 * math.atan(math.tan(math.radians(75 / 2)) * 144 / 256))
        self.c = {'root': str(self.root), 'run_id': 'fictional-panorama-test',
                  'source': 'original.png', 'source_sha256': hashlib.sha256(self.source.read_bytes()).hexdigest(),
                  'source_identity': 'synthetic calibration pattern, never client media',
                  'room_identity': 'fictional test viewport', 'projection': 'equirectangular',
                  'geometry': [512, 256], 'rights': 'original', 'rights_basis': 'test fixture created by test',
                  'width': 256, 'height': 144, 'fps': 24, 'seconds': 1,
                  'start': {'yaw': -30, 'pitch': -4, 'h_fov': 75, 'v_fov': vfov},
                  'end': {'yaw': 30, 'pitch': 4, 'h_fov': 75, 'v_fov': vfov},
                  'working': 'working/viewport-test', 'output': 'working/clips/test.mp4'}

    def tearDown(self):
        self.tmp.cleanup()

    def test_flat_photo_is_rejected(self):
        with self.assertRaises(ValueError):
            validate(self.c, (512, 300), self.c['run_id'])

    def test_distorted_fov_is_rejected(self):
        self.c['end']['v_fov'] = 75
        with self.assertRaises(ValueError):
            validate(self.c, (512, 256), self.c['run_id'])

    def test_unresolved_rights_are_rejected(self):
        self.c['rights'] = 'unresolved'
        with self.assertRaises(ValueError):
            validate(self.c, (512, 256), self.c['run_id'])

    def test_output_cannot_be_client_media(self):
        self.c['output'] = 'output/client.mp4'
        with self.assertRaises(ValueError):
            validate(self.c, (512, 256), self.c['run_id'])

    def test_rotation_uses_short_path_across_seam(self):
        self.c['start']['yaw'] = 170
        self.c['end']['yaw'] = -170
        self.assertAlmostEqual(view_at(self.c, 12, 25)['yaw'], -180)

    def test_per_frame_commands_reach_endpoints(self):
        commands = command_text(self.c, 24)
        self.assertEqual(len(commands.splitlines()), 24)
        self.assertIn('yaw -30.000000000', commands.splitlines()[0])
        self.assertIn('yaw 30.000000000', commands.splitlines()[-1])

    @unittest.skipUnless(shutil.which('ffmpeg'), 'FFmpeg is required for renderer integration')
    def test_actual_avif_demux_and_filter_loop(self):
        avif = self.root / 'original.avif'
        Image.open(self.source).save(avif, format='AVIF')
        self.source = avif
        self.c['source'] = avif.name
        self.c['source_sha256'] = hashlib.sha256(avif.read_bytes()).hexdigest()
        self.test_actual_ffmpeg_runtime_commands_change_viewport()

    @unittest.skipUnless(shutil.which('ffmpeg'), 'FFmpeg is required for renderer integration')
    def test_actual_ffmpeg_runtime_commands_change_viewport(self):
        class FixtureInputs:
            run_id = 'fictional-panorama-test'
            def read(inner, p): return Path(p).read_bytes()
            def finish(inner): pass
        render(self.c, FixtureInputs())
        output = self.root / self.c['output']
        md5 = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(output), '-f', 'framemd5', '-'], text=True)
        frames = [x.rsplit(',', 1)[-1].strip() for x in md5.splitlines() if not x.startswith('#')]
        self.assertEqual(len(frames), 24)
        self.assertNotEqual(frames[0], frames[-1])
        self.assertGreater(len(set(frames)), 20)


    @unittest.skipUnless(shutil.which('ffmpeg'), 'FFmpeg required')
    def test_rendered_frames_match_absolute_planned_views(self):
        import numpy as np
        class FixtureInputs:
            run_id='fictional-panorama-test'
            def read(inner,p):return Path(p).read_bytes()
            def finish(inner):pass
        render(self.c,FixtureInputs())
        decoded=subprocess.check_output(['ffmpeg','-v','error','-i',str(self.root/self.c['output']),'-f','rawvideo','-pix_fmt','rgb24','-'])
        frames=np.frombuffer(decoded,dtype=np.uint8).reshape(24,144,256,3)
        for n in (0,12,23):
            v=view_at(self.c,n,24)
            vf='v360=input=equirect:output=flat:w=256:h=144:interp=cubic:'+':'.join(f'{k}={x}' for k,x in v.items())
            raw=subprocess.check_output(['ffmpeg','-v','error','-i',str(self.source),'-vf',vf,'-frames:v','1','-f','rawvideo','-pix_fmt','rgb24','-'])
            expected=np.frombuffer(raw,dtype=np.uint8).reshape(144,256,3)
            error=np.abs(frames[n].astype(float)-expected.astype(float)).mean()
            self.assertLess(error,5.0,f'Frame{n} drifts from authored camera: {error}')


if __name__ == '__main__':
    unittest.main()
