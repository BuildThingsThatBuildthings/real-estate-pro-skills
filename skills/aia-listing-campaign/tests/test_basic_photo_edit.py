import importlib.util
import sys
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from PIL import Image, ImageDraw

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
SCRIPT=Path(__file__).resolve().parents[1]/'scripts/edit_camera_sequence.py';spec=importlib.util.spec_from_file_location('basic_editor',SCRIPT);editor=importlib.util.module_from_spec(spec);spec.loader.exec_module(editor)

class BasicPhotoEditTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.shots=[]
        for n in range(2):
            p=self.root/f'original{n}.png';im=Image.new('RGB',(640,360),'#efb87c');draw=ImageDraw.Draw(im)
            for x in range(0,640,16):draw.rectangle((x,0,x+8,360),fill=(x%255,80+n*80,100))
            im.save(p);self.shots.append({'path':str(p),'seconds':4,'status':'reviewed','origin':'original','source_id':f'original-{n}','source_sha256':editor.digest(p),'motion':{'start':{'x':0,'y':0,'width':600,'height':337.5},'end':{'x':80,'y':40,'width':480,'height':270}}})
        self.c={'run_id':'new','composition_id':'photo-edit','kind':'teaser','mode':'basic_photo_edit','width':320,'height':180,'fps':24,'working':str(self.root/'working'),'output':str(self.root/'delivery/film.mp4'),'shots':self.shots,'music':{'path':str(self.root/'music.wav'),'rights_basis':'Original synthetic tone','attribution':'Unit test tone'}}
    def tearDown(self):self.tmp.cleanup()
    def probe(self,path):return {'streams':[{'codec_type':'audio'}],'format':{'duration':'8'}}
    def test_explicit_authored_source_windows_valid(self):self.assertEqual(editor.validate(self.c,self.probe),8)
    def test_implicit_static_or_out_of_bounds_rejected(self):
        self.c.pop('mode')
        with self.assertRaisesRegex(ValueError,'explicitly'):editor.validate(self.c,self.probe)
        self.c['mode']='basic_photo_edit';self.shots[0]['motion']['end']['x']=1000
        with self.assertRaisesRegex(ValueError,'boundaries'):editor.validate(self.c,self.probe)
    def test_generated_images_cannot_enter_original_edit(self):
        self.shots[0].update(origin='generated',run_id='new')
        with self.assertRaisesRegex(ValueError,'originals'):editor.validate(self.c,self.probe)
    def test_narration_edits_reject_overlap_and_outside_picture(self):
        self.c['narration']={'path':self.c['music']['path'],'rights_basis':'Test tone','segments':[{'in':0,'seconds':2,'at':0},{'in':3,'seconds':2,'at':4}]}
        self.assertEqual(editor.validate(self.c,self.probe),8)
        self.c['narration']['segments'][1]['at']=1
        with self.assertRaisesRegex(ValueError,'overlaps'):editor.validate(self.c,self.probe)
    @unittest.skipUnless(shutil.which('ffmpeg'),'FFmpeg required')
    def test_real_editor_renders_moving_fullframe_pictures(self):
        subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','sine=frequency=220:duration=8',self.c['music']['path']],check=True)
        self.c['narration']={'path':self.c['music']['path'],'rights_basis':'Test tone','segments':[{'in':0,'seconds':1,'at':0},{'in':3,'seconds':1,'at':4}]}
        output=editor.render(self.c);meta=editor.probe(output);video=next(s for s in meta['streams'] if s['codec_type']=='video')
        self.assertEqual((video['width'],video['height']),(320,180));self.assertAlmostEqual(float(meta['format']['duration']),8,delta=.1)
        frames=[]
        for time in (0,3.8):frames.append(subprocess.check_output(['ffmpeg','-v','error','-ss',str(time),'-i',str(output),'-frames:v','1','-f','rawvideo','-pix_fmt','rgb24','-']))
        self.assertNotEqual(frames[0],frames[1]);self.assertEqual([p.suffix for p in output.parent.iterdir()],['.mp4'])
    @unittest.skipUnless(shutil.which('ffmpeg'),'FFmpeg required')
    def test_portrait_honors_full_authored_source_height(self):
        self.c.update(width=180,height=320)
        for shot in self.shots:
            im=Image.new('RGB',(640,360),'red');draw=ImageDraw.Draw(im);draw.rectangle((0,120,640,240),fill='green');draw.rectangle((0,240,640,360),fill='blue');im.save(shot['path'])
            shot['source_sha256']=editor.digest(shot['path']);shot['motion']={'start':{'x':100,'y':0,'width':202.5,'height':360},'end':{'x':120,'y':20,'width':180,'height':320}}
        # Give second source distinct bytes without changing the tested first shot.
        im=Image.open(self.shots[1]['path']);im.putpixel((0,0),(2,3,4));im.save(self.shots[1]['path']);self.shots[1]['source_sha256']=editor.digest(self.shots[1]['path'])
        subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','sine=frequency=220:duration=8',self.c['music']['path']],check=True)
        output=editor.render(self.c)
        raw=subprocess.check_output(['ffmpeg','-v','error','-i',str(output),'-frames:v','1','-f','rawvideo','-pix_fmt','rgb24','-'])
        frame=Image.frombytes('RGB',(180,320),raw)
        top=frame.getpixel((90,20));bottom=frame.getpixel((90,300))
        self.assertGreater(top[0],200);self.assertGreater(bottom[2],200);self.assertLess(bottom[0],30)

if __name__=='__main__':unittest.main()
