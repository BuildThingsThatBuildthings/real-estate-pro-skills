#!/usr/bin/env python3
"""Stage 7 — COMPOSITE. Deterministically layer brand truth onto base imagery.

This is the architectural core: the generative model never produces the logo, the
exact brand hex, the license number, or the disclosure. Those are placed here,
from files on disk, at channel-spec coordinates.

Emits composite-manifest.json recording exactly what was drawn where, so
brand_lint.py verifies the same facts composite.py claims — not a re-guess.

Usage:
    python composite.py --base <img> --agent <agent-dir> --channel ig \\
        --headline "..." [--subhead "..."] --out <path>

Exit codes: 0 = composited, 1 = blocked (brand fact missing/illegible), 2 = usage
"""

import argparse
import json
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont, ImageStat
except ImportError:
    print("STOP: Pillow required. pip install Pillow", file=sys.stderr)
    sys.exit(1)

from brandkit import (AgentBrand, BrandError, contrast_ratio, hex_to_rgb,
                      relative_luminance)

# Channel geometry. Mirrors references/channel-specs.md — that file is the
# human source of truth; keep them in sync when platforms drift.
CHANNELS = {
    "ig":  {"size": (1080, 1350), "safe": (60, 60, 60, 120)},
    "igs": {"size": (1080, 1920), "safe": (60, 108, 120, 320)},
    "fb":  {"size": (1200, 630),  "safe": (40, 40, 40, 40)},
    "li":  {"size": (1200, 1200), "safe": (64, 64, 64, 64)},
    "tt":  {"size": (1080, 1920), "safe": (60, 130, 140, 480)},
    "yt":  {"size": (1280, 720),  "safe": (60, 60, 60, 60)},
    "x":   {"size": (1600, 900),  "safe": (48, 48, 48, 48)},
}

MIN_CONTRAST = 4.5           # WCAG AA
MIN_COMPLIANCE_PX = 14       # floor for legibility of legal text


BUNDLED_FONTS = Path(__file__).resolve().parent.parent / "assets" / "fonts"
BUNDLED = {"display": BUNDLED_FONTS / "PlayfairDisplay.ttf",
           "sans": BUNDLED_FONTS / "SourceSans3.ttf",
           "body": BUNDLED_FONTS / "SourceSans3.ttf"}
# OS font fallbacks, cross-platform (macOS, Linux, Windows).
SYSTEM_FONTS = [
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "C:\\Windows\\Fonts\\arial.ttf",
]


def _truetype(path, size):
    ft = ImageFont.truetype(str(path), size)
    try:  # variable fonts (bundled OFL files) default oddly; pin Regular
        ft.set_variation_by_name("Regular")
    except (OSError, AttributeError):
        pass
    return ft


def load_font(path_or_name, size, kind="display"):
    """Resolve a font: agent-declared → bundled OFL default → OS → PIL bitmap.

    Returns (font, fell_back) where fell_back means "the agent DECLARED a font
    and we could not honor it" — that is a brand deviation the manifest must
    record. Using the bundled default when nothing was declared is not a
    fallback; it IS the default.
    """
    declared = bool(path_or_name)
    if declared:
        p = Path(path_or_name)
        if p.exists():
            try:
                return _truetype(p, size), False
            except OSError:
                pass
        # A bare family name (no path) that matches a bundled font resolves
        # cleanly — "PlayfairDisplay" is the bundled default, not a deviation.
        name = str(path_or_name).lower().replace(" ", "")
        for b in BUNDLED.values():
            if b.exists() and b.stem.lower().replace(" ", "") == name:
                try:
                    return _truetype(b, size), False
                except OSError:
                    pass
    bundled = BUNDLED.get(kind, BUNDLED["display"])
    if bundled.exists():
        try:
            return _truetype(bundled, size), declared
        except OSError:
            pass
    for candidate in SYSTEM_FONTS:
        if Path(candidate).exists():
            try:
                return ImageFont.truetype(candidate, size), True
            except OSError:
                continue
    return ImageFont.load_default(), True


def wrap(draw, text, font, max_width):
    """Greedy wrap using real font metrics.

    PIL's getlength() gives exact advance widths, so line breaks here are
    deterministic rather than character-count guesses.
    """
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = f"{cur} {w}".strip()
        if draw.textlength(trial, font=font) <= max_width or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def fit_text(draw, text, font_path, max_width, max_lines, start_size, min_size, kind="display"):
    """Shrink until the text fits max_lines. Returns None if it can't.

    Returning None is correct behavior: the caller sends the brief back for
    shorter copy rather than rendering type below legibility.
    """
    size = start_size
    while size >= min_size:
        font, fell_back = load_font(font_path, size, kind=kind)
        lines = wrap(draw, text, font, max_width)
        if len(lines) <= max_lines:
            return font, lines, size, fell_back
        size -= 2
    return None


def cover_crop(img, target):
    """Scale-and-center-crop to exactly target dims. Never distorts aspect."""
    tw, th = target
    sw, sh = img.size
    scale = max(tw / sw, th / sh)
    nw, nh = max(tw, int(round(sw * scale))), max(th, int(round(sh * scale)))
    img = img.resize((nw, nh), Image.Resampling.LANCZOS)
    return img.crop(((nw - tw) // 2, (nh - th) // 2,
                     (nw - tw) // 2 + tw, (nh - th) // 2 + th))


def region_mean(img, box):
    r = img.crop(box).convert("RGB").resize((16, 16), Image.Resampling.BILINEAR)
    return tuple(int(v) for v in ImageStat.Stat(r).mean[:3])


def region_worst(img, box, text_rgb, pct=0.85):
    """Worst-case background behind text, not the average.

    A mean hides local failure: a gradient scrim is near-opaque at the bottom and
    near-clear at the top, so averaging the whole band reports comfortable
    contrast while the headline sits on bare photograph. Light text fails against
    the BRIGHTEST pixels, dark text against the DARKEST — so sample the tail that
    actually breaks, at `pct` of the distribution.
    """
    r = img.crop(box).convert("RGB").resize((48, 48), Image.Resampling.BILINEAR)
    px = [r.getpixel((x, y)) for y in range(r.height) for x in range(r.width)]
    light_text = relative_luminance(text_rgb) > 0.5
    # Sort WORST-CASE FIRST: brightest pixels break light text, darkest break
    # dark text. Then step `1 - pct` in from that end so one stray pixel doesn't
    # drive the whole decision.
    px.sort(key=relative_luminance, reverse=light_text)
    idx = min(len(px) - 1, int(len(px) * (1.0 - pct)))
    return px[idx]


def main():
    ap = argparse.ArgumentParser(description="Content Foundry Stage 7 — COMPOSITE")
    ap.add_argument("--base", required=True, help="generated or real base image")
    ap.add_argument("--agent", required=True, help="path to agents/{slug}/")
    ap.add_argument("--channel", required=True, choices=sorted(CHANNELS))
    ap.add_argument("--headline", required=True)
    ap.add_argument("--subhead", default=None)
    ap.add_argument("--treatment", choices=["auto", "panel"], default="auto",
                    help="auto = contrast-driven scrim/panel; panel = brief-directed solid panel")
    ap.add_argument("--allow-demo", action="store_true",
                    help="permit a demo/fixture agent to produce output (samples of the pipeline itself only)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--manifest", default=None)
    args = ap.parse_args()

    try:
        brand = AgentBrand(args.agent)
        colors = brand.colors
        required = brand.required_strings()
    except BrandError as e:
        print(f"STOP: {e}", file=sys.stderr)
        return 1

    if brand.demo and not args.allow_demo:
        print(f"STOP: {brand.slug} is a DEMO persona. Listing content runs under "
              f"the listing's presenting agent. Run prospect research / setup to "
              f"build their folder, or pass --allow-demo for pipeline-demo "
              f"output only.", file=sys.stderr)
        return 1

    design = brand.design
    display_kind = "sans" if design.get("display_type") == "sans" else "display"

    # Compliance gate BEFORE spending work: never composite a production asset
    # with a PENDING legal string. Blocked is recoverable; published is not.
    missing = [k for k, v in required.items() if v is None]
    if missing:
        print(f"STOP: {brand.slug}: compliance strings not filled: "
              f"{', '.join(missing)}.\n"
              f"      Request exact wording from the brokerage and fill "
              f"brand-context-compliance.md.\n"
              f"      Content Foundry enforces placement; it never drafts legal "
              f"wording.", file=sys.stderr)
        return 1

    spec = CHANNELS[args.channel]
    W, H = spec["size"]
    sl, st, sr, sb = spec["safe"]

    base = Image.open(args.base).convert("RGB")
    canvas = cover_crop(base, (W, H))
    draw = ImageDraw.Draw(canvas, "RGBA")

    headline_font_path = brand.headline_font  # from brand-context-visual.md
    manifest = {
        "agent": brand.slug, "channel": args.channel, "size": [W, H],
        "design": design,
        "safe_zone": {"left": sl, "top": st, "right": sr, "bottom": sb},
        "colors": colors, "elements": [], "warnings": [],
    }

    text_w = W - sl - sr

    # --- headline ---------------------------------------------------------
    bold_family = design.get("layout_family") == "full-bleed-bold"
    start_sz = int(H * (0.085 if bold_family else 0.075))
    fitted = fit_text(draw, args.headline, headline_font_path,
                      text_w, max_lines=3, start_size=start_sz,
                      min_size=int(H * 0.030), kind=display_kind)
    if not fitted:
        print(f"STOP: headline does not fit {args.channel} safe zone above "
              f"legible size ({len(args.headline)} chars, max "
              f"{brand.max_headline_chars}).\n"
              f"      Send the brief back for shorter copy — do not shrink type "
              f"below legibility.", file=sys.stderr)
        return 1
    hfont, hlines, hsize, fell_back = fitted
    if fell_back:
        manifest["warnings"].append(
            "headline font fell back to a system font — brand font not resolved")

    line_h = int(hsize * 1.18)
    block_h = line_h * len(hlines)
    comp_size = max(MIN_COMPLIANCE_PX, int(H * 0.0145))
    cfont, _cfb = load_font(None, comp_size, kind="body")
    comp_line_h = int(comp_size * 1.35)
    # Wrap every compliance string to the safe width. Legal text running off
    # the frame edge is a truncated disclosure — a compliance failure, not a
    # styling nit. Wrapped height is reserved in the layout like any block.
    comp_wrapped = []
    for _label, _txt in (("license", required["license"]),
                         ("disclosure", required["disclosure"]),
                         ("fair_housing", required["fair_housing"])):
        if _txt:
            comp_wrapped.append((_label, _txt, wrap(draw, _txt, cfont, W - sl - sr)))
    comp_h = comp_line_h * sum(len(w[2]) for w in comp_wrapped)

    # --- subhead (optional) ----------------------------------------------
    # Fitted BEFORE the headline position is set so the layout reserves room.
    # An earlier version parsed --subhead and rendered it nowhere; silently
    # dropping copy is the one failure this pipeline exists to prevent.
    sub_font = None; sub_lines = []; sub_lh = 0; sub_h = 0; sub_gap = 0
    if args.subhead:
        sfit = fit_text(draw, args.subhead, None, text_w, max_lines=3,
                        start_size=max(int(hsize * 0.38), int(H * 0.021)),
                        min_size=int(H * 0.015), kind="sans")
        if not sfit:
            print(f"STOP: subhead does not fit {args.channel} below the "
                  f"headline at legible size. Send the brief back for shorter "
                  f"copy — do not drop it silently.", file=sys.stderr)
            return 1
        sub_font, sub_lines, sub_size, _sfb = sfit
        sub_lh = int(sub_size * 1.4)
        sub_h = sub_lh * len(sub_lines)
        sub_gap = int(H * 0.02)

    # Headline sits above subhead + compliance block, inside the safe zone.
    h_top = H - sb - comp_h - int(H * 0.035) - sub_h - sub_gap - block_h
    h_box = (sl, h_top, W - sr, h_top + block_h)

    # --- scrim (conditional) ---------------------------------------------
    text_rgb = hex_to_rgb(colors.get("text-on-dark", "#ffffff"))
    # Measure on the HEADLINE BOX with worst-case sampling — not the whole lower
    # region, and not the mean. The text only has to survive where it sits.
    measure_box = (sl, max(0, h_top - 8), W - sr, h_top + block_h + sub_gap + sub_h + 8)
    ratio = contrast_ratio(text_rgb, region_worst(canvas, measure_box, text_rgb))
    force_panel = args.treatment == "panel"
    if not force_panel and ratio < MIN_CONTRAST:
        scrim_rgb = hex_to_rgb(colors["primary"])
        # Ramp from fully transparent well above the text so there is no seam.
        top = max(0, h_top - int(H * 0.22))
        # Escalate opacity until the headline actually clears AA. A single fixed
        # ramp passes on calm photos and silently fails on busy ones.
        applied = (0, canvas, ratio)
        for peak in (200, 228, 244, 252, 255):
            layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            ld = ImageDraw.Draw(layer)
            for y in range(top, H):
                t = (y - top) / max(1, H - top)
                ld.line([(0, y), (W, y)], fill=(*scrim_rgb, int(peak * (t ** 1.1))))
            trial = Image.alpha_composite(canvas.convert("RGBA"), layer).convert("RGB")
            after = contrast_ratio(text_rgb, region_worst(trial, measure_box, text_rgb))
            applied = (peak, trial, after)
            if after >= MIN_CONTRAST:
                break
        peak, canvas, after = applied
        draw = ImageDraw.Draw(canvas, "RGBA")
        el = {"type": "scrim", "reason": f"headline contrast {ratio:.2f} < {MIN_CONTRAST}",
              "color": colors["primary"], "box": [0, top, W, H], "peak_alpha": peak,
              "measure": "worst-case p85 over headline box",
              "contrast_before": round(ratio, 2), "contrast_after": round(after, 2)}
        manifest["elements"].append(el)

        need_panel = after < MIN_CONTRAST
    else:
        need_panel = force_panel

    if need_panel:
        # The solid brand panel — a real design treatment, not a hack, and the
        # same move the reference open-house assets use. Reached two ways: the
        # gradient scrim couldn't clear AA on a busy base, or the brief forced
        # it (--treatment panel) as a deliberate composition choice. Guarantees
        # legibility because the background is a known brand color.
        pad = int(H * 0.022)
        # Extend to the bottom edge — a panel that stops short of the frame
        # leaves a sliver of photograph under the compliance block and reads
        # as a rendering fault rather than a design choice.
        panel = (0, max(0, h_top - pad), W, H)
        draw.rectangle(panel, fill=(*hex_to_rgb(colors["primary"]), 255))
        accent = hex_to_rgb(colors.get("accent", colors["primary"]))
        if design.get("accent_treatment") == "block":
            # bold family: a solid accent block bleeding off the left edge
            draw.rectangle([0, panel[1], int(W * 0.028), H], fill=(*accent, 255))
        else:
            draw.rectangle([sl, panel[1], sl + int(W * 0.09), panel[1] + max(3, H // 300)],
                           fill=(*accent, 255))
        panel_ratio = contrast_ratio(text_rgb, hex_to_rgb(colors["primary"]))
        manifest["elements"].append({
            "type": "panel",
            "reason": ("brief-directed treatment" if force_panel
                       else "gradient scrim could not clear AA"),
            "color": colors["primary"], "accent_rule": colors.get("accent"),
            "box": list(panel), "contrast": round(panel_ratio, 2),
        })
        if panel_ratio < MIN_CONTRAST:
            # The brand's own colors can't carry its text. Real problem —
            # say it plainly rather than shipping illegible type.
            manifest["warnings"].append(
                f"brand primary vs text contrast {panel_ratio:.2f} < "
                f"{MIN_CONTRAST} — text-on-dark color is wrong for this brand")

    # --- headline type ----------------------------------------------------
    y = h_top
    for ln in hlines:
        draw.text((sl, y), ln, font=hfont, fill=text_rgb)
        y += line_h
    manifest["elements"].append({
        "type": "headline", "text": args.headline, "lines": hlines,
        "font_size": hsize, "box": list(h_box), "color": colors.get("text-on-dark", "#ffffff"),
    })

    # --- subhead type -----------------------------------------------------
    if sub_lines:
        sy = h_top + block_h + sub_gap
        for ln in sub_lines:
            draw.text((sl, sy), ln, font=sub_font, fill=text_rgb)
            sy += sub_lh
        manifest["elements"].append({
            "type": "subhead", "text": args.subhead, "lines": sub_lines,
            "font_size": sub_lh, "box": [sl, h_top + block_h + sub_gap, W - sr, sy],
            "color": colors.get("text-on-dark", "#ffffff"),
        })

    # --- logo -------------------------------------------------------------
    # Open one variant first purely for geometry (variants share aspect); the
    # light/dark choice happens AFTER the final position is known, because
    # collision fallback can move the logo from the dark panel onto bare photo.
    try:
        logo = Image.open(brand.logo_path("light")).convert("RGBA")
    except BrandError as e:
        print(f"STOP: {e}", file=sys.stderr)
        return 1

    target_w = max(brand.logo_min_width, int(W * 0.16))
    avail_w = W - sl - sr - 2 * brand.logo_clear_space
    if target_w > avail_w:
        print(f"STOP: logo minimum width ({brand.logo_min_width}px) does not fit "
              f"the {args.channel} safe zone.\n"
              f"      Refusing to shrink the logo below its declared legibility "
              f"floor.", file=sys.stderr)
        return 1
    logo = logo.resize((target_w, max(1, int(logo.height * target_w / logo.width))),
                       Image.Resampling.LANCZOS)
    cs = brand.logo_clear_space

    def logo_xy(placement):
        x = sl + cs if "left" in placement else W - sr - cs - logo.width
        y = (st + cs if "top" in placement
             else H - sb - comp_h - cs - logo.height)
        return x, y

    def overlaps(a, b):
        return not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])

    # On short canvases the bottom band can't hold headline + logo + compliance
    # in one corner. Resolve deterministically: preferred corner → opposite
    # horizontal side → above the headline on the preferred side. Every fallback
    # is recorded so the choice is auditable, never silent.
    placement = brand.logo_placement
    candidates = [placement,
                  placement.replace("left", "right") if "left" in placement
                  else placement.replace("right", "left")]
    pos = None
    placed_via = placement
    # The occupied block runs from the headline top to the subhead bottom.
    text_block = (h_box[0], h_box[1], h_box[2], h_box[3] + sub_gap + sub_h)
    for cand in candidates:
        x, y = logo_xy(cand)
        if not overlaps((x, y, x + logo.width, y + logo.height), text_block):
            pos, placed_via = (x, y), cand
            break
    if pos is None:
        x = sl + cs if "left" in placement else W - sr - cs - logo.width
        y = h_top - cs - logo.height
        if y < st:
            print(f"STOP: no collision-free position for the logo on "
                  f"{args.channel} ({W}x{H}) — headline block leaves no room. "
                  f"Shorten the headline or use a taller format.",
                  file=sys.stderr)
            return 1
        pos, placed_via = (x, y), f"above-headline ({placement} side)"
    lx, ly = pos
    if placed_via != placement:
        manifest["warnings"].append(
            f"logo moved from '{placement}' to '{placed_via}' to avoid the "
            f"text block on this format")

    # Variant selection at the FINAL box, by WORST-CASE contrast — a mean over a
    # mixed background (white railing + dark pavilion) picks confidently and
    # wrongly. brand-context-visual.md keys name the BACKGROUND a variant is
    # FOR: "dark background" -> light ink.
    final_box = (lx, ly, lx + logo.width, ly + logo.height)
    white_ink = (255, 255, 255)
    dark_ink = hex_to_rgb(colors.get("text-on-light", colors["primary"]))
    wc_white = contrast_ratio(white_ink, region_worst(canvas, final_box, white_ink))
    wc_dark = contrast_ratio(dark_ink, region_worst(canvas, final_box, dark_ink))
    bg_is_dark = wc_white >= wc_dark
    LOGO_MIN_CONTRAST = 3.0  # WCAG bar for graphical objects
    if max(wc_white, wc_dark) < LOGO_MIN_CONTRAST:
        # Neither ink survives this background — put a brand chip under the
        # logo so legibility comes from a known color, not from luck.
        cs2 = brand.logo_clear_space
        chip = (lx - cs2, ly - cs2, lx + logo.width + cs2, ly + logo.height + cs2)
        draw.rectangle(chip, fill=(*hex_to_rgb(colors["primary"]), 255))
        bg_is_dark = True  # chip is brand primary -> light-ink variant
        manifest["elements"].append({
            "type": "logo-chip",
            "reason": f"both logo variants below {LOGO_MIN_CONTRAST}:1 on this "
                      f"background (white {wc_white:.2f}, dark {wc_dark:.2f})",
            "color": colors["primary"], "box": list(chip),
        })
    try:
        logo_p = brand.logo_path("dark" if bg_is_dark else "light")
    except BrandError as e:
        print(f"STOP: {e}", file=sys.stderr)
        return 1
    logo = Image.open(logo_p).convert("RGBA").resize(logo.size,
                                                     Image.Resampling.LANCZOS)
    canvas.paste(logo, (lx, ly), logo)
    manifest["elements"].append({
        "type": "logo", "source": str(logo_p),
        "variant_for_background": "dark" if bg_is_dark else "light",
        "placement": placed_via,
        "contrast_worst_case": round(max(wc_white, wc_dark), 2),
        "box": list(final_box),
        "width": logo.width, "min_width": brand.logo_min_width,
    })

    # --- compliance block -------------------------------------------------
    # cfont was resolved above, at layout time, so wrapping and drawing agree.
    cy = H - sb - comp_h

    # The compliance block gets the same guarantee as the headline: if any
    # line's worst-case background contrast is below AA, draw a brand-primary
    # backing strip under the whole block BEFORE drawing text. Legal text is
    # the one place "almost legible" is a failure by definition.
    comp_top = cy - int(comp_size * 0.5)
    comp_block = (0, comp_top, W, min(H, cy + comp_h + int(comp_size * 0.6)))
    worst = min(
        (contrast_ratio(text_rgb, region_worst(
            canvas, (sl, y0, W - sr, y0 + int(comp_size * 1.35)), text_rgb))
         for y0 in range(cy, cy + comp_h, int(comp_size * 1.35))),
        default=99)
    if worst < MIN_CONTRAST:
        strip = Image.new("RGBA", (W, comp_block[3] - comp_block[1]),
                          (*hex_to_rgb(colors["primary"]), 232))
        canvas.paste(Image.alpha_composite(
            canvas.crop((0, comp_block[1], W, comp_block[3])).convert("RGBA"),
            strip).convert("RGB"), (0, comp_block[1]))
        draw = ImageDraw.Draw(canvas, "RGBA")
        manifest["elements"].append({
            "type": "compliance-backing",
            "reason": f"compliance worst-case contrast {worst:.2f} < {MIN_CONTRAST}",
            "color": colors["primary"], "box": list(comp_block),
        })
    for label, txt, tlines in comp_wrapped:
        block_top = cy
        cbox = (sl, cy, W - sr, cy + comp_line_h * len(tlines))
        cratio = contrast_ratio(text_rgb, region_worst(canvas, cbox, text_rgb))
        for tl in tlines:
            draw.text((sl, cy), tl, font=cfont, fill=text_rgb)
            cy += comp_line_h
        cy -= comp_line_h  # the shared advance below expects one line-step
        el = {"type": "compliance", "field": label, "text": txt,
              "lines": len(tlines), "font_size": comp_size,
              "box": [sl, block_top, W - sr, block_top + comp_line_h * len(tlines)],
              "contrast": round(cratio, 2)}
        if cratio < MIN_CONTRAST:
            # Recorded, not silently accepted — brand_lint.py fails on this.
            el["below_min_contrast"] = True
            manifest["warnings"].append(
                f"compliance '{label}' contrast {cratio:.2f} < {MIN_CONTRAST}")
        manifest["elements"].append(el)
        cy += int(comp_size * 1.35)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out, quality=95)
    man_path = Path(args.manifest) if args.manifest else out.with_suffix(".composite.json")
    man_path.write_text(json.dumps(manifest, indent=2))

    print(f"COMPOSITE {brand.slug} / {args.channel} -> {out}")
    print(f"  {len(manifest['elements'])} elements, "
          f"{len(manifest['warnings'])} warning(s)")
    for w in manifest["warnings"]:
        print(f"    WARN: {w}")
    print(f"  manifest -> {man_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
