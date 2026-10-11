#!/usr/bin/env python3
"""Video engine glue v2: agent folder + scenes + audio -> Remotion props.json.

Scene-based: each scene carries the room name, the feature line, the photo's
real aspect ratio (so the comp can lay it out instead of blind-cropping), and
its narration clip with measured duration (so VO drives timing).

Brand values come from brandkit — the same single source the stills path reads.
The comp never hardcodes a brand fact.

Usage:
    python video_props.py --agent <agent-dir> --scenes <scenes.json> \\
        [--audio-meta <audio_meta.json>] --out props.json

Exit codes: 0 = ok, 1 = blocked (brand fact missing / asset missing), 2 = usage
"""

import argparse
import json
import shutil
import sys
from pathlib import Path

from brandkit import AgentBrand, BrandError, contrast_ratio, hex_to_rgb

try:
    from PIL import Image
except ImportError:
    print("STOP: Pillow required. pip install Pillow", file=sys.stderr)
    sys.exit(2)

FPS = 30
MIN_CONTRAST = 4.5      # WCAG AA, normal text
MIN_CONTRAST_LARGE = 3  # WCAG AA, large text (the stat values)
KINDS = ("listing", "market", "general")
MIN_SCENE_S = 3.5      # floor even when a VO line is short
VO_TAIL_S = 0.9        # breathing room after each narration line
ENGINE_PUBLIC = Path(__file__).resolve().parent.parent / "engines" / "remotion" / "public" / "job"


def stage(src, name):
    dst = ENGINE_PUBLIC / name
    shutil.copy2(src, dst)
    return f"job/{name}"


def rgb_hex(rgb):
    return "#" + "".join(f"{int(c):02x}" for c in rgb)


def tint(hex_color, amount):
    """Mix a brand hex toward white. Derived from the brand, never invented."""
    r = hex_to_rgb(hex_color)
    return rgb_hex(tuple(round(c + (255 - c) * amount) for c in r))


def best_ink(ground, candidates, floor):
    """The first candidate that clears the contrast floor on this ground, else
    the highest-contrast one with its ratio (the caller decides to stop)."""
    scored = [(c, contrast_ratio(hex_to_rgb(c), hex_to_rgb(ground))) for c in candidates if c]
    for c, r in scored:
        if r >= floor:
            return c, r
    return max(scored, key=lambda x: x[1])


def image_aspect(path):
    with Image.open(path) as im:
        w, h = im.size
    return round(w / h, 4) if h else 1.0


def market_block(cfg, colors):
    """Validate the market-update data and pick legible inks for a light ground.

    Every statistic needs a source and the data period must be stated
    (prompt-library #4). Ink colours are chosen by measured WCAG contrast
    against the ground, so light brand grounds never get white text.
    """
    m = cfg.get("market") or {}
    stats = m.get("stats") or []
    if not stats:
        raise ValueError("market video needs market.stats (one idea per stat card)")
    if not m.get("period"):
        raise ValueError("market.period is required — a statistic without its data "
                         "period reads as current when it may not be")
    for i, st in enumerate(stats, 1):
        for key in ("label", "value", "source"):
            if not str(st.get(key, "")).strip():
                raise ValueError(f"market.stats[{i}] has no {key!r} — uncited or "
                                 f"unlabelled numbers do not ship")
    ground = m.get("ground") or colors.get("light-ground") or tint(colors["primary"], 0.92)
    ink, ink_r = best_ink(ground, [colors.get("text-on-light"), colors["primary"],
                                   "#111111"], MIN_CONTRAST)
    if ink_r < MIN_CONTRAST:
        raise ValueError(f"no text colour reaches {MIN_CONTRAST}:1 on ground "
                         f"{ground} (best {ink} at {ink_r:.2f}:1)")
    value_ink, _ = best_ink(ground, [colors["primary"], ink], MIN_CONTRAST_LARGE)
    rule = colors.get("accent", colors["primary"])
    return {
        "area": m.get("area", ""),
        "period": m["period"],
        "ground": ground,
        "ink": ink,
        "valueInk": value_ink,
        "rule": rule,
        "stats": [{"label": st["label"], "value": str(st["value"]),
                   "detail": st.get("detail", ""), "source": st["source"]}
                  for st in stats],
        "contrast": {"ink": round(ink_r, 2),
                     "value": round(contrast_ratio(hex_to_rgb(value_ink), hex_to_rgb(ground)), 2)},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent", required=True)
    ap.add_argument("--scenes", required=True, help="scenes.json from the brief")
    ap.add_argument("--audio-meta", default=None, help="audio_meta.json from media engine")
    ap.add_argument("--out", required=True)
    ap.add_argument("--allow-demo", action="store_true")
    ap.add_argument("--flights-dir", default=None,
                    help="dir of per-scene i2v parallax clips (s1.mp4..sN.mp4); scenes gain video mode")
    args = ap.parse_args()

    try:
        brand = AgentBrand(args.agent)
        colors = brand.colors
        required = brand.required_strings()
    except BrandError as e:
        print(f"STOP: {e}", file=sys.stderr)
        return 1

    if brand.demo and not args.allow_demo:
        print(f"STOP: {brand.slug} is a DEMO persona — listing content requires the "
              f"presenting agent's folder (or --allow-demo).", file=sys.stderr)
        return 1

    missing = [k for k, v in required.items() if v is None]
    if missing:
        print(f"STOP: compliance strings not filled: {', '.join(missing)} — "
              f"a video without the disclosure endcard does not render.",
              file=sys.stderr)
        return 1

    scenes_p = Path(args.scenes)
    cfg = json.loads(scenes_p.read_text())
    run_dir = scenes_p.parent
    warnings = []
    kind = cfg.get("kind")
    if kind is None:
        kind = "listing"
        warnings.append("scenes.json has no 'kind' — treated as a listing video "
                        "(the endcard says 'Now Showing'); set kind: market|general otherwise")
    if kind not in KINDS:
        print(f"STOP: scenes.json kind {kind!r} is not one of {', '.join(KINDS)}",
              file=sys.stderr)
        return 1
    market = None
    if kind == "market":
        try:
            market = market_block(cfg, colors)
        except ValueError as e:
            print(f"STOP: {e}", file=sys.stderr)
            return 1

    # Audio: measured VO durations keyed by line id; bed path. Degrades with
    # explicit warnings, never silently.
    voices, bed = {}, None
    if args.audio_meta:
        meta = json.loads(Path(args.audio_meta).read_text())
        for v in meta.get("voices", []):
            voices[v["id"]] = {"path": run_dir / v["path"],
                               "duration_s": float(v["duration_s"]),
                               "words": [{"t": w.get("text", ""),
                                          "s": float(w.get("start", 0)),
                                          "e": float(w.get("end", 0))}
                                         for w in v.get("words", [])]}
        bgm = meta.get("bgm") or {}
        if bgm.get("path"):
            bed = run_dir / bgm["path"]
    if not voices:
        warnings.append("no narration clips — video degrades to music-only")
    if bed is None or not Path(bed).exists():
        warnings.append("no music bed — video will be silent")
        bed = None

    # Stage assets fresh.
    if ENGINE_PUBLIC.exists():
        shutil.rmtree(ENGINE_PUBLIC)
    ENGINE_PUBLIC.mkdir(parents=True)

    def build_scene(s, idx):
        src = Path(s["photo"])
        if not src.exists():
            print(f"STOP: photo not found: {src}", file=sys.stderr)
            sys.exit(1)
        with Image.open(src) as im:
            w, h = im.size
        ref = stage(src, f"s{idx}{src.suffix.lower()}")
        clip_ref = None
        if args.flights_dir:
            cand = Path(args.flights_dir) / f"s{idx}.mp4"
            if cand.exists():
                clip_ref = stage(cand, f"clip-s{idx}.mp4")
        vo_id = s.get("vo")
        vo_ref, vo_dur, vo_words = None, 0.0, []
        if vo_id and vo_id in voices:
            vo_ref = stage(voices[vo_id]["path"], f"vo-{vo_id}.wav")
            vo_dur = voices[vo_id]["duration_s"]
            vo_words = voices[vo_id]["words"]
        elif vo_id:
            warnings.append(f"scene '{s['room']}': VO line '{vo_id}' missing")
        # Pinned facts: each pin appears when its keyword is SPOKEN, then stays
        # on screen for the rest of the scene (reading persistence).
        pins = []
        import re as _re
        for pin in s.get("pins", []):
            keys = [kw.lower().strip(".,") for kw in _re.split(r"[^A-Za-z0-9,\.]+", pin)
                    if len(kw) > 3 or kw.replace(",", "").replace(".", "").isdigit()]
            at = None
            for wd in vo_words:
                wt = wd["t"].lower().strip(".,!?")
                if any(k and (k in wt or wt in k) for k in keys):
                    at = wd["s"]
                    break
            pins.append({"text": pin, "atS": round(at if at is not None else 1.0, 3)})
        dur_s = max(MIN_SCENE_S, vo_dur + VO_TAIL_S)
        return {
            "photo": ref, "clip": clip_ref,
            "width": w, "height": h, "aspect": round(w / h, 4),
            "room": s["room"], "feature": s["feature"],
            "vo": vo_ref, "voDurationS": round(vo_dur, 3),
            "voWords": vo_words, "pins": pins,
            "frames": int(round(dur_s * FPS)),
        }

    scenes = [build_scene(s, i) for i, s in enumerate(cfg.get("scenes", []), 1)]
    if kind != "market" and not scenes:
        print("STOP: scenes.json has no scenes — listing and general comps need "
              "photos (a market update uses kind: market + market.stats)", file=sys.stderr)
        return 1

    end_vo_ref, end_vo_dur, end_vo_words = None, 0.0, []
    end_id = cfg.get("endcard_vo")
    if end_id and end_id in voices:
        end_vo_ref = stage(voices[end_id]["path"], f"vo-{end_id}.wav")
        end_vo_dur = voices[end_id]["duration_s"]
        end_vo_words = voices[end_id]["words"]
    end_frames = int(round(max(4.0, end_vo_dur + 1.4) * FPS))

    brief_cards = []
    for i, c in enumerate(cfg.get("brief_cards", []), 1):
        src = Path(c["photo"])
        with Image.open(src) as im:
            w, h = im.size
        brief_cards.append({"photo": stage(src, f"b{i}{src.suffix.lower()}"),
                            "width": w, "height": h, "aspect": round(w / h, 4),
                            "line": c["line"]})

    bed_ref = stage(bed, "bed" + Path(bed).suffix.lower()) if bed else None

    # Fonts: the agent's declared headline/body fonts when they resolve (from
    # the agent folder, same as stills), else the bundled OFL defaults, so
    # typography is identical on every OS (see shared.tsx). Browsers detect
    # the font format from the file itself, so the staged name is fixed.
    bundled_font = (Path(__file__).resolve().parent.parent / "assets" / "fonts"
                    / "PlayfairDisplay.ttf")
    sans_font = bundled_font.parent / "SourceSans3.ttf"
    head_decl, body_decl = brand.headline_font, brand.body_font
    head_file = Path(head_decl) if head_decl and Path(head_decl).is_file() else None
    body_file = Path(body_decl) if body_decl and Path(body_decl).is_file() else None
    if head_decl and not head_file:
        warnings.append(f"headline font {head_decl!r} is not a file in the agent "
                        f"folder — video uses the bundled display font")
    if body_decl and not body_file:
        warnings.append(f"body font {body_decl!r} is not a file in the agent "
                        f"folder — video uses the system sans")
    display_src = head_file or (bundled_font if bundled_font.exists() else None)
    if display_src:
        stage(display_src, "font-display.ttf")
    else:
        warnings.append("bundled display font missing — comps fall back to system serif")
    if head_file:
        stage(head_file, "font-sans.ttf")   # declared headline font wins for sans display too
    elif sans_font.exists():
        stage(sans_font, "font-sans.ttf")
    if body_file:
        stage(body_file, "font-body.ttf")

    headshot_ref = None
    if brand.headshot_path:
        headshot_ref = stage(brand.headshot_path, "headshot.jpg")

    # The endcard sits on brand primary. Pick the ink and logo variant that
    # are legible there instead of assuming primary is dark.
    on_dark = colors.get("text-on-dark", "#ffffff")
    on_primary, on_primary_r = best_ink(colors["primary"],
                                        [on_dark, colors.get("text-on-light")], MIN_CONTRAST)
    if on_primary_r < MIN_CONTRAST:
        warnings.append(f"endcard text {on_primary} is {on_primary_r:.2f}:1 on primary "
                        f"{colors['primary']} (below {MIN_CONTRAST}:1)")
    # The endcard label ("Now Showing") is large display type: 3:1 floor.
    label_ink, _ = best_ink(colors["primary"], [colors.get("accent"), on_primary],
                            MIN_CONTRAST_LARGE)
    logo_dark = brand.logo_path("dark")
    logo_light = brand.logo_path("light")
    endcard_logo = logo_dark if on_primary == on_dark else logo_light

    props = {
        "brand": {
            "primary": colors["primary"],
            "secondary": colors.get("secondary", colors["primary"]),
            "accent": colors.get("accent", colors["primary"]),
            "textOnDark": on_dark,
            "textOnLight": colors.get("text-on-light", "#111111"),
            "onPrimary": on_primary,
            "labelOnPrimary": label_ink,
            "logoDark": stage(logo_dark, "logo-dark.png"),
            "logoDarkAspect": image_aspect(logo_dark),
            "logoLight": stage(logo_light, "logo-light.png"),
            "logoLightAspect": image_aspect(logo_light),
            "endcardLogo": "job/logo-dark.png" if endcard_logo == logo_dark else "job/logo-light.png",
            "endcardLogoAspect": image_aspect(endcard_logo),
            "headshot": headshot_ref,
            "name": brand.slug.replace("-", " ").title(),
        },
        "kind": kind,
        "market": market,
        "design": brand.design,
        "addressChip": cfg.get("address_chip", ""),
        "headline": cfg["headline"],
        "subline": cfg["subline"],
        "hook": cfg.get("hook", cfg["headline"]),
        "community": cfg.get("community", ""),
        "scenes": scenes,
        "briefCards": brief_cards,
        "endcard": {"vo": end_vo_ref, "voDurationS": round(end_vo_dur, 3),
                    "voWords": end_vo_words, "frames": end_frames},
        "audio": {"bed": bed_ref, "bedVolume": 0.16, "bedVolumeSolo": 0.30},
        "compliance": {
            "license": required["license"],
            "disclosure": required["disclosure"],
            "fairHousing": required["fair_housing"],
        },
        "warnings": warnings,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(props, indent=2))

    print(f"VIDEO PROPS v2 {brand.slug} ({kind}) -> {out}")
    if market:
        print(f"  market: {len(market['stats'])} stat card(s), {market['period']}, "
              f"ground {market['ground']}, ink {market['ink']} "
              f"({market['contrast']['ink']}:1), values {market['valueInk']} "
              f"({market['contrast']['value']}:1)")
    else:
        total_f = 72 + sum(s["frames"] for s in scenes) + end_frames
        print(f"  {len(scenes)} scenes, walkthrough ≈ {total_f / FPS:.1f}s, "
              f"narration {sum(s['voDurationS'] for s in scenes) + end_vo_dur:.1f}s, "
              f"bed: {'yes' if bed_ref else 'NO'}")
    for w in warnings:
        print(f"  WARN: {w}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
