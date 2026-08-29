#!/usr/bin/env python3
"""Stage 8a — BRAND LINT. Deterministic verification of a composited asset.

Reads brand truth through the SAME brandkit reader composite.py used, then checks
the pixels — not just the manifest's claims. The manifest says where things are;
the pixels prove they're there. If composite.py lied or a later step damaged the
file, this catches it.

A lint that never fails is not wired up. Test it with a wrong hex before
trusting a pass.

Usage:
    python brand_lint.py <asset.jpg> --agent <agent-dir> [--manifest <path>]

Exit codes: 0 = pass (warns allowed), 1 = FAIL, 2 = usage error
"""

import argparse
import json
import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    print("STOP: Pillow required. pip install Pillow", file=sys.stderr)
    sys.exit(2)

from brandkit import AgentBrand, BrandError, hex_to_rgb

MIN_CONTRAST = 4.5
MIN_COMPLIANCE_PX = 14
# JPEG q95 shifts channels slightly; exact-hex checks allow this much per channel.
JPEG_TOLERANCE = 8
# ΔE-ish threshold for the generated-region palette drift warn (rough CIE76 on RGB).
PALETTE_DRIFT_WARN = 90


def close(rgb1, rgb2, tol=JPEG_TOLERANCE):
    return all(abs(a - b) <= tol for a, b in zip(rgb1, rgb2))


def sample(img, x, y):
    x = min(max(0, int(x)), img.width - 1)
    y = min(max(0, int(y)), img.height - 1)
    return img.getpixel((x, y))[:3]


def box_center(box):
    return ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)


def text_pixel_fraction(img, box, text_rgb, tol=60):
    """Fraction of pixels in box near the text color — proves type was drawn.

    Sampled at NATIVE resolution on a stride. Downscaling first would blend a
    thin text row into its background and erase the very pixels being counted.
    """
    region = img.crop([int(v) for v in box]).convert("RGB")
    if region.width == 0 or region.height == 0:
        return 0.0
    stride_x = max(1, region.width // 300)
    stride_y = max(1, region.height // 40)
    px = [region.getpixel((x, y)) for y in range(0, region.height, stride_y)
          for x in range(0, region.width, stride_x)]
    if not px:
        return 0.0
    hits = sum(1 for p in px if close(p, text_rgb, tol))
    return hits / len(px)


def dominant_colors(img, box, n=4):
    region = img.crop([int(v) for v in box]).convert("RGB")
    region.thumbnail((64, 64))
    q = region.quantize(colors=n, method=Image.Quantize.MEDIANCUT).convert("RGB")
    counts = {}
    for y in range(q.height):
        for x in range(q.width):
            p = q.getpixel((x, y))
            counts[p] = counts.get(p, 0) + 1
    return [c for c, _ in sorted(counts.items(), key=lambda kv: -kv[1])]


def main():
    ap = argparse.ArgumentParser(description="Content Foundry Stage 8a — BRAND LINT")
    ap.add_argument("asset")
    ap.add_argument("--agent", required=True, help="path to agents/{slug}/")
    ap.add_argument("--manifest", default=None,
                    help="composite manifest (default: <asset>.composite.json)")
    args = ap.parse_args()

    asset_p = Path(args.asset)
    if not asset_p.exists():
        print(f"FAIL: asset not found: {asset_p}", file=sys.stderr)
        return 1
    man_p = Path(args.manifest) if args.manifest else asset_p.with_suffix(".composite.json")

    fails, warns = [], []

    if not man_p.exists():
        # No manifest = no provenance. An asset that skipped the composite
        # stage cannot be brand-verified and must not ship.
        print(f"FAIL: no composite manifest at {man_p} — asset did not go "
              f"through Stage 7, cannot verify brand truth.", file=sys.stderr)
        return 1
    manifest = json.loads(man_p.read_text())

    try:
        brand = AgentBrand(args.agent)
        colors = brand.colors
        required = brand.required_strings()
    except BrandError as e:
        print(f"FAIL: {e}", file=sys.stderr)
        return 1

    # Tenancy: the manifest must belong to THIS agent.
    if manifest.get("agent") != brand.slug:
        fails.append(f"manifest agent '{manifest.get('agent')}' != '{brand.slug}' "
                     f"— cross-agent bleed")

    img = Image.open(asset_p).convert("RGB")
    W, H = img.size
    if [W, H] != manifest.get("size"):
        fails.append(f"asset size {W}x{H} != manifest {manifest.get('size')}")

    sz = manifest.get("safe_zone", {})
    sl, st = sz.get("left", 0), sz.get("top", 0)
    sr, sb = sz.get("right", 0), sz.get("bottom", 0)
    els = manifest.get("elements", [])
    by_type = {}
    for e in els:
        by_type.setdefault(e["type"], []).append(e)

    # --- 1. brand hexes actually drawn (solid elements: panel, accent rule) --
    manifest_primary = manifest.get("colors", {}).get("primary")
    if manifest_primary and manifest_primary != colors["primary"]:
        fails.append(f"manifest primary {manifest_primary} != brand file "
                     f"{colors['primary']} — asset composited from stale/wrong "
                     f"brand values")
    for panel in by_type.get("panel", []):
        # sample near the panel's corner, inside the fill, away from type
        probe = sample(img, panel["box"][2] - 40, panel["box"][3] - 12)
        if not close(probe, hex_to_rgb(colors["primary"])):
            fails.append(f"panel pixel {probe} != brand primary "
                         f"{hex_to_rgb(colors['primary'])} at panel corner "
                         f"— exact hex not on canvas")
    for scrim in by_type.get("scrim", []):
        if scrim.get("below_min_contrast"):
            fails.append(f"scrim recorded below_min_contrast "
                         f"({scrim.get('contrast_after')}) and no panel rescued it"
                         if not by_type.get("panel") else "")
    fails = [f for f in fails if f]

    # --- 2. logo present, at position, at legal size --------------------------
    logos = by_type.get("logo", [])
    if not logos:
        fails.append("no logo element in manifest")
    for lg in logos:
        if lg["width"] < brand.logo_min_width:
            fails.append(f"logo width {lg['width']}px < declared minimum "
                         f"{brand.logo_min_width}px")
        box = lg["box"]
        if box[0] < 0 or box[1] < 0 or box[2] > W or box[3] > H:
            fails.append(f"logo box {box} exceeds canvas")
        # Pixel proof: the region must differ from its surroundings — a logo
        # that pasted fully transparent or off-canvas leaves the box unchanged.
        src = Path(lg["source"])
        if not src.exists():
            fails.append(f"logo source missing: {src}")
        else:
            logo_img = Image.open(src).convert("RGBA")
            lw = box[2] - box[0]
            lh = box[3] - box[1]
            scaled = logo_img.resize((max(1, lw), max(1, lh)))
            opaque = [(x, y) for y in range(0, scaled.height, max(1, scaled.height // 8))
                      for x in range(0, scaled.width, max(1, scaled.width // 8))
                      if scaled.getpixel((x, y))[3] > 200]
            if opaque:
                hits = 0
                for x, y in opaque:
                    expect = scaled.getpixel((x, y))[:3]
                    got = sample(img, box[0] + x, box[1] + y)
                    if close(got, expect, tol=40):
                        hits += 1
                frac = hits / len(opaque)
                if frac < 0.6:
                    fails.append(f"logo pixels match source at only "
                                 f"{frac:.0%} of sampled points — logo not "
                                 f"actually on canvas as declared")

    # --- 3. compliance strings: present, verbatim, legible, sized -------------
    comp_els = {e["field"]: e for e in by_type.get("compliance", [])}
    for field, val in required.items():
        if val is None:
            fails.append(f"compliance '{field}' is unfilled in "
                         f"brand-context-compliance.md — production asset "
                         f"cannot ship")
            continue
        el = comp_els.get(field)
        if not el:
            fails.append(f"compliance '{field}' missing from asset")
            continue
        if el["text"].strip() != val.strip():
            fails.append(f"compliance '{field}' text differs from brand file — "
                         f"wording must be verbatim, never paraphrased")
        if el["font_size"] < MIN_COMPLIANCE_PX:
            fails.append(f"compliance '{field}' at {el['font_size']}px < "
                         f"{MIN_COMPLIANCE_PX}px floor")
        if el.get("contrast", 99) < MIN_CONTRAST and not by_type.get("panel"):
            fails.append(f"compliance '{field}' contrast {el['contrast']} < "
                         f"{MIN_CONTRAST}")
        # pixel proof that type exists in the box
        text_rgb = hex_to_rgb(manifest["colors"].get("text-on-dark", "#ffffff"))
        frac = text_pixel_fraction(img, el["box"], text_rgb)
        if frac < 0.005:
            fails.append(f"compliance '{field}' box contains no text-colored "
                         f"pixels — string not actually drawn")

    # --- 4. everything inside the safe zone -----------------------------------
    for e in els:
        if e["type"] in ("scrim", "panel", "compliance-backing"):
            continue  # full-bleed treatments may run to the edge by design
        box = e.get("box")
        if not box:
            continue
        if box[0] < sl or box[1] < st or box[2] > W - sr or box[3] > H - sb:
            fails.append(f"{e['type']} box {box} violates safe zone "
                         f"(l{sl} t{st} r{sr} b{sb}) — platform UI will cover it")

    # --- 5. headline drawn + generated-region palette drift (warns) -----------
    for h in by_type.get("headline", []):
        text_rgb = hex_to_rgb(manifest["colors"].get("text-on-dark", "#ffffff"))
        frac = text_pixel_fraction(img, h["box"], text_rgb)
        if frac < 0.01:
            fails.append("headline box contains no text-colored pixels")
    # generated region = everything above the panel/scrim top
    treat_tops = [e["box"][1] for e in els if e["type"] in ("panel", "scrim")]
    gen_bottom = min(treat_tops) if treat_tops else H
    if gen_bottom > 100:
        doms = dominant_colors(img, (0, 0, W, gen_bottom))
        brand_rgbs = [hex_to_rgb(v) for v in colors.values()]
        drift = min(
            min(sum((a - b) ** 2 for a, b in zip(d, brgb)) ** 0.5
                for brgb in brand_rgbs)
            for d in doms[:2])
        if drift > PALETTE_DRIFT_WARN:
            warns.append(f"generated region palette sits ~{drift:.0f} RGB-distance "
                         f"from every brand color — imagery may fight the brand")

    for w in manifest.get("warnings", []):
        if "contrast" in w:
            fails.append(f"composite self-reported: {w}")
        else:
            # every other composite self-report surfaces as a warn — never drop
            warns.append(w)

    # --- distinctness vs demo fixtures ---------------------------------------
    DEMO_PRIMARIES = {"#676147": "riley-shore demo", "#1b4d3e": "testbrand fixture",
                      "#051221": "retired demo"}
    prim = colors.get("primary", "").lower()
    if prim in DEMO_PRIMARIES and not getattr(brand, "demo", False):
        fails.append(f"palette primary {prim} matches the {DEMO_PRIMARIES[prim]} "
                     f"palette — output is not distinct from a demo persona")

    # --- verdict --------------------------------------------------------------
    print(f"BRAND LINT {brand.slug} / {asset_p.name}")
    if fails:
        for f in fails:
            print(f"  FAIL: {f}")
    for w in warns:
        print(f"  warn: {w}")
    if fails:
        print(f"\nVERDICT: FAIL ({len(fails)} finding(s)) — route back to "
              f"GENERATE with a root-cause note. Max 2 retries.", file=sys.stderr)
        return 1
    print(f"VERDICT: PASS ({len(warns)} warning(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
