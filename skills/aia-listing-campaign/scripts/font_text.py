"""Fail before rendering missing glyphs; preserve readable apostrophes in subset fonts.

A cmap entry is not proof of ink. A font can map a codepoint to an empty outline that
reserves an advance and paints nothing, and Pillow, reportlab and ffmpeg's drawtext all
render that as a silent hole -- no exception, no warning. That is how the AIA compliance
line

    Vanessa Sisemore CalRE #02221256 | Pam Wojciechowski Team | Coldwell Banker Realty

lost both separators to an 85-glyph Inter subset and nearly shipped. So every character
is checked three ways: mapped in the cmap, not falling through to .notdef, and carrying
a real outline.
"""
import copy
from functools import lru_cache

# Private Use Area. No text font maps this, so what it renders IS this font's .notdef,
# which gives a reference mask to compare suspect characters against. This catches fonts
# whose .notdef is a visible box, where an ink test alone would pass while drawing the
# wrong character.
_SENTINEL = ''
_PROBE_SIZE = 48

@lru_cache(maxsize=16)
def coverage(font_path):
    from fontTools.ttLib import TTFont
    with TTFont(font_path) as font:
        return frozenset(font.getBestCmap() or {})

@lru_cache(maxsize=16)
def _probe(font_path):
    """(pillow font, .notdef mask) for ink testing, or (None, None) if unrasterizable."""
    try:
        from PIL import ImageFont
        pil = ImageFont.truetype(font_path, _PROBE_SIZE)
    except Exception:
        return None, None
    try:
        return pil, pil.getmask(_SENTINEL).tobytes()
    except Exception:
        return pil, None

@lru_cache(maxsize=4096)
def draws_ink(font_path, char):
    """True if `char` actually puts ink on the page in this font."""
    if char in ' \n\r\t ':
        return True
    pil, notdef = _probe(font_path)
    if pil is None:
        return True                     # cannot rasterize here; cmap check still applies
    try:
        if notdef is not None and pil.getmask(char).tobytes() == notdef:
            return False                # fell through to .notdef
        box = pil.getbbox(char)
    except Exception:
        return True
    return box is not None and (box[3] - box[1]) > 0

def supported_text(text, glyphs, font_path=None):
    result = []
    for char in text:
        if char in '\n\r\t' or ord(char) in glyphs:
            result.append(char)
        elif char == "'" and 0x2019 in glyphs:
            result.append('’')
        else:
            raise ValueError(f'Chosen font is missing U+{ord(char):04X}; use a licensed font containing the required glyph')
    out = ''.join(result)
    if font_path:
        blank = sorted({c for c in out if not draws_ink(font_path, c)})
        if blank:
            listed = ', '.join(f'{c!r} U+{ord(c):04X}' for c in blank)
            raise ValueError(
                f'Chosen font maps but cannot draw {listed} -- it would render as a silent '
                f'gap in {out!r}; use a font whose outlines for those characters have ink')
    return out

def _overlay_strings(overlay):
    """Text out of an overlay, whose lines may be strings, [text, ...] or {'text': ...}."""
    for line in overlay.get('lines', []) or []:
        if isinstance(line, str):
            yield line
        elif isinstance(line, dict) and isinstance(line.get('text'), str):
            yield line['text']
        elif isinstance(line, (list, tuple)) and line and isinstance(line[0], str):
            yield line[0]

def prepare_text(config):
    c = copy.deepcopy(config)
    entries = c.get('captions', []) + c.get('brand_text', [])
    entries += [item for shot in c.get('shots', []) for item in shot.get('text', [])]
    # Overlays are burned in by the caller rather than by this module, but they are
    # declared against the same font, so check them here too. Not doing so is exactly
    # how the 164 Southwind films bypassed this guard entirely.
    overlay_text = [s for o in c.get('overlays', []) or [] for s in _overlay_strings(o)]
    if entries or overlay_text:
        glyphs = coverage(c['font'])
        for item in entries:
            item['text'] = supported_text(item['text'], glyphs, c['font'])
        for s in overlay_text:
            supported_text(s, glyphs, c['font'])
    return c
