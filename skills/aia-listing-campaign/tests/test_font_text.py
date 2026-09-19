import importlib.util
from pathlib import Path
import unittest
spec=importlib.util.spec_from_file_location('font_text',Path(__file__).parents[1]/'scripts/font_text.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
class FontTextTest(unittest.TestCase):
    def test_subset_apostrophe_is_readable(self):
        glyphs=set(map(ord,'Don t'))|{0x2019}
        self.assertEqual(module.supported_text("Don't",glyphs),'Don\u2019t')
    def test_complete_font_preserves_source(self):
        text="Don't\nstop";self.assertEqual(module.supported_text(text,set(map(ord,text))),text)
    def test_no_supported_substitute_fails(self):
        with self.assertRaisesRegex(ValueError,'U\\+0027'):module.supported_text("Don't",set(map(ord,'Dont')))
    def test_other_missing_glyph_fails(self):
        with self.assertRaisesRegex(ValueError,'U\\+2605'):module.supported_text('\u2605',set())
if __name__=='__main__':unittest.main()
