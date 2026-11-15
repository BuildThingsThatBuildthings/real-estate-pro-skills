"""Validate glyph coverage and visible ink before drawing text with subset fonts."""
import copy
import io
from functools import lru_cache

_PROBE_SIZE = 48


def _source(font):
    # Accept verified bytes so renderers can validate the same input they consume.
    return io.BytesIO(font) if isinstance(font, bytes) else font


@lru_cache(maxsize=16)
def coverage(font_path):
    from fontTools.ttLib import TTFont
    with TTFont(_source(font_path)) as font:
        return frozenset(code for code, name in (font.getBestCmap() or {}).items()
                         if font.getGlyphID(name) != 0)


def _mask_key(mask):
    return mask.size, bytes(mask)


@lru_cache(maxsize=16)
def _probe(font_path):
    """Return a rasterizer and its missing-glyph mask, or refuse validation."""
    from PIL import ImageFont
    # Private-use characters can be mapped. Pick a codepoint absent from this font.
    glyphs = coverage(font_path)
    sentinel = next(chr(code) for code in range(0x10ffff, -1, -1) if code not in glyphs)
    try:
        pil = ImageFont.truetype(_source(font_path), _PROBE_SIZE)
        return pil, _mask_key(pil.getmask(sentinel))
    except Exception as exc:
        raise ValueError('Cannot rasterize chosen font to verify glyph ink') from exc


@lru_cache(maxsize=4096)
def draws_ink(font_path, char):
    """Reject empty outlines and missing-glyph substitutes, even with an advance."""
    if char.isspace():
        return True
    pil, notdef = _probe(font_path)
    try:
        mask = pil.getmask(char)
        return mask.getbbox() is not None and _mask_key(mask) != notdef
    except Exception as exc:
        raise ValueError(f'Cannot verify glyph ink for U+{ord(char):04X}') from exc


def supported_text(text, glyphs, font_path=None):
    result = []
    for char in text:
        if char in '\n\r\t' or ord(char) in glyphs:
            result.append(char)
        elif char == "'" and 0x2019 in glyphs:
            result.append('\u2019')
        else:
            raise ValueError(f'Chosen font is missing U+{ord(char):04X}; use a licensed font containing the required glyph')
    out = ''.join(result)
    if font_path is not None:
        blank = sorted({char for char in out if not draws_ink(font_path, char)})
        if blank:
            listed = ', '.join(f'{char!r} U+{ord(char):04X}' for char in blank)
            raise ValueError(f'Chosen font maps but cannot draw {listed}; use a font with visible glyph outlines')
    return out


def prepare_text(config):
    c = copy.deepcopy(config)
    entries = c.get('captions', []) + c.get('brand_text', [])
    entries += [item for shot in c.get('shots', []) for item in shot.get('text', [])]
    overlays = c.get('overlays', []) or []
    if entries or any(overlay.get('lines') for overlay in overlays):
        glyphs = coverage(c['font'])
        def check(text):
            return supported_text(text, glyphs, c['font'])
        for item in entries:
            item['text'] = check(item['text'])
        for overlay in overlays:
            lines = []
            for line in overlay.get('lines', []) or []:
                if isinstance(line, str):
                    line = check(line)
                elif isinstance(line, dict) and isinstance(line.get('text'), str):
                    line['text'] = check(line['text'])
                elif isinstance(line, (list, tuple)) and line and isinstance(line[0], str):
                    values = [check(line[0]), *line[1:]]
                    line = tuple(values) if isinstance(line, tuple) else values
                else:
                    raise ValueError('Overlay lines require text')
                lines.append(line)
            overlay['lines'] = lines
    return c
