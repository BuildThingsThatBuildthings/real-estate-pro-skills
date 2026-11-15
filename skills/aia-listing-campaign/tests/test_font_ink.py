"""Synthetic fonts exercise visible ink independently of system fonts or providers."""
import copy
import io
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import font_text
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen


def fixture_font():
    def shape(width=300):
        pen=TTGlyphPen(None)
        if width:
            pen.moveTo((40,0));pen.lineTo((width,0));pen.lineTo((width,650));pen.lineTo((40,650));pen.closePath()
        return pen.glyph()
    fb=FontBuilder(1000,isTTF=True)
    fb.setupGlyphOrder(['.notdef','space','a','quote','empty','alias','private'])
    fb.setupCharacterMap({32:'space',65:'a',0x2019:'quote',124:'empty',63:'alias',0xE83F:'private',33:'.notdef'})
    fb.setupGlyf({'.notdef':shape(550),'space':shape(0),'a':shape(300),'quote':shape(100),'empty':shape(0),'alias':shape(550),'private':shape(250)})
    fb.setupHorizontalMetrics({name:(600,0) for name in fb.font.getGlyphOrder()})
    fb.setupHorizontalHeader(ascent=800,descent=-200)
    fb.setupNameTable({'familyName':'Glyph Guard Fixture','styleName':'Regular','uniqueFontIdentifier':'glyph-guard-fixture','fullName':'Glyph Guard Fixture','psName':'GlyphGuardFixture'})
    fb.setupOS2(sTypoAscender=800,sTypoDescender=-200,usWinAscent=800,usWinDescent=200)
    fb.setupPost();out=io.BytesIO();fb.save(out);return out.getvalue()


class InkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.font=fixture_font();cls.glyphs=font_text.coverage(cls.font)
    def test_visible_text_and_spaces_pass(self):
        self.assertEqual(font_text.supported_text("A A'\n",self.glyphs,self.font),'A A’\n')
    def test_cmap_with_empty_outline_refuses(self):
        self.assertIn(ord('|'),self.glyphs)
        with self.assertRaisesRegex(ValueError,'cannot draw.*U\\+007C'):
            font_text.supported_text('A|A',self.glyphs,self.font)
    def test_notdef_mapping_and_outline_alias_refuse(self):
        self.assertNotIn(ord('!'),self.glyphs)
        with self.assertRaisesRegex(ValueError,'missing'):
            font_text.supported_text('!',self.glyphs,self.font)
        with self.assertRaisesRegex(ValueError,'cannot draw'):
            font_text.supported_text('?',self.glyphs,self.font)
    def test_mapped_private_use_codepoint_is_not_assumed_missing(self):
        self.assertEqual(font_text.supported_text('\ue83f',self.glyphs,self.font),'\ue83f')
    def test_unavailable_probe_refuses_instead_of_passing(self):
        font_text._probe.cache_clear()
        with patch('PIL.ImageFont.truetype',side_effect=OSError('broken renderer')):
            with self.assertRaisesRegex(ValueError,'Cannot rasterize'):font_text._probe(self.font)
    def test_bad_mask_refuses_instead_of_passing(self):
        with patch.object(font_text,'_probe') as probe:
            from unittest.mock import Mock
            pil=Mock();pil.getmask.side_effect=OSError('bad glyph');probe.return_value=(pil,None)
            with self.assertRaisesRegex(ValueError,'Cannot verify'):font_text.draws_ink(b'uncached','A')
    def test_all_text_locations_are_normalized_without_mutating_source(self):
        config={'font':self.font,'captions':[{'text':"A'"}],'brand_text':[{'text':"A'"}],
                'shots':[{'text':[{'text':"A'"}]}],
                'overlays':[{'lines':["A'",{'text':"A'",'size':18},["A'",12],("A'",24)]}]}
        original=copy.deepcopy(config);result=font_text.prepare_text(config)
        self.assertEqual(config,original)
        self.assertEqual(result['captions'][0]['text'],'A’')
        self.assertEqual(result['brand_text'][0]['text'],'A’')
        self.assertEqual(result['shots'][0]['text'][0]['text'],'A’')
        self.assertEqual(result['overlays'][0]['lines'],['A’',{'text':'A’','size':18},['A’',12],('A’',24)])
    def test_overlay_only_text_is_checked(self):
        with self.assertRaisesRegex(ValueError,'cannot draw'):
            font_text.prepare_text({'font':self.font,'overlays':[{'lines':['A|A']}]})
    def test_unknown_overlay_shape_refuses(self):
        with self.assertRaisesRegex(ValueError,'Overlay lines'):
            font_text.prepare_text({'font':self.font,'overlays':[{'lines':[{'label':'A'}]}]})

if __name__=='__main__':unittest.main()
