import copy
import io
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from test_font_ink import fixture_font
from fontTools.ttLib import TTFont as FontToolsFont
from PIL import Image

try:
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from render_documents import checked_paragraph, checked_text
    DOCUMENTS=True
except ImportError:
    DOCUMENTS=False
import render_photo_designs


@unittest.skipUnless(DOCUMENTS,'ReportLab and qrcode required for document rendering')
class DocumentTextGuards(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.font=fixture_font()
        cls.fonts={'Brand400':cls.font,'Brand700':cls.font}
        for name in cls.fonts:pdfmetrics.registerFont(TTFont(name,io.BytesIO(cls.font)))
        pdfmetrics.registerFontFamily('Brand400',normal='Brand400',bold='Brand700',italic='Brand400',boldItalic='Brand700')
        cls.style=ParagraphStyle('fixture',fontName='Brand400')
    def test_canvas_text_returns_the_validated_substitution(self):
        self.assertEqual(checked_text("A'",self.font),'A’')
    def test_paragraph_checks_visible_text_not_markup_or_link_urls(self):
        p=checked_paragraph('&#65; <b>A\'</b><br/><link href="https://example.com/|">A</link>',self.style,self.fonts)
        self.assertEqual(''.join(f.text for f in p.frags),'A A’A')
    def test_escaped_entity_is_checked_after_decoding(self):
        with self.assertRaisesRegex(ValueError,'U\\+007C'):
            checked_paragraph('A&#124;A',self.style,self.fonts)
        with self.assertRaisesRegex(ValueError,'U\\+003C'):
            checked_paragraph('&lt;A&gt;',self.style,self.fonts)
    def test_bold_fragments_use_bold_font_coverage(self):
        with FontToolsFont(io.BytesIO(self.font)) as font:
            for table in font['cmap'].tables:
                if table.isUnicode():table.cmap[65]='empty'
            out=io.BytesIO();font.save(out)
        fonts={**self.fonts,'Brand700':out.getvalue()}
        checked_paragraph('A',self.style,fonts)
        with self.assertRaisesRegex(ValueError,'cannot draw'):
            checked_paragraph('<b>A</b>',self.style,fonts)


class PhotoTextGuards(unittest.TestCase):
    def test_render_uses_verified_font_bytes_and_preserves_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve();(root/'logo.png').write_bytes(b'placeholder')
            Image.new('RGB',(3,3),'white').save(root/'logo.png')
            font=fixture_font();consumed=[]
            def read(path):
                consumed.append(Path(path).name)
                # No font exists on disk: the guard must use these exact consumed bytes.
                if Path(path).name=='fixture.ttf':return font
                if Path(path).suffix=='.md':return b'fixture'
                return Path(path).read_bytes()
            inputs=SimpleNamespace(run_id='fictional',consumed={},read=read)
            spec={'run_id':'fictional','id':'test','agent':'fixture','size':[160,80],
                  'safe_zone':{},'output':'output/cover.png','layers':[
                      {'type':'logo','path':'logo.png','box':[0,0,3,3],'rights':'original','rights_basis':'test'},
                      {'type':'text','font':'fixture.ttf','size':20,'box':[10,10,150,60],'text':"A'"}]}
            original=copy.deepcopy(spec)
            brand=SimpleNamespace(slug='fixture',colors={},required_strings=lambda:{})
            with patch.object(render_photo_designs,'AgentBrand',return_value=brand):
                result=render_photo_designs.render(spec,root,inputs)
                self.assertTrue(Path(result).is_file())
                self.assertEqual(spec,original)
                self.assertEqual(consumed.count('fixture.ttf'),1)
                spec['layers'][-1]['text']='A|A'
                with self.assertRaisesRegex(ValueError,'cannot draw'):
                    render_photo_designs.render(spec,root,inputs)

if __name__=='__main__':unittest.main()
