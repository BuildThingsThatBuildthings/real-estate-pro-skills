"""Fail before rendering missing glyphs; preserve readable apostrophes in subset fonts."""
import copy
from functools import lru_cache

@lru_cache(maxsize=16)
def coverage(font_path):
    from fontTools.ttLib import TTFont
    with TTFont(font_path) as font:
        return frozenset(font.getBestCmap() or {})

def supported_text(text, glyphs):
    result = []
    for char in text:
        if char in '\n\r\t' or ord(char) in glyphs:
            result.append(char)
        elif char == "'" and 0x2019 in glyphs:
            result.append('\u2019')
        else:
            raise ValueError(f'Chosen font is missing U+{ord(char):04X}; use a licensed font containing the required glyph')
    return ''.join(result)

def prepare_text(config):
    c = copy.deepcopy(config)
    entries = c.get('captions', []) + c.get('brand_text', [])
    entries += [item for shot in c.get('shots', []) for item in shot.get('text', [])]
    if entries:
        glyphs = coverage(c['font'])
        for item in entries:
            item['text'] = supported_text(item['text'], glyphs)
    return c
