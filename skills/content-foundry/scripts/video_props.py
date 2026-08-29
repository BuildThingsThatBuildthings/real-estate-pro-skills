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

from brandkit import AgentBrand, BrandError

try:
    from PIL import Image
except ImportError:
    print("STOP: Pillow required. pip install Pillow", file=sys.stderr)
    sys.exit(2)

FPS = 30
MIN_SCENE_S = 3.5      # floor even when a VO line is short
VO_TAIL_S = 0.9        # breathing room after each narration line
ENGINE_PUBLIC = Path(__file__).resolve().parent.parent / "engines" / "remotion" / "public" / "job"


def stage(src, name):
    dst = ENGINE_PUBLIC / name
    shutil.copy2(src, dst)
    return f"job/{name}"


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

    # Audio: measured VO durations keyed by line id; bed path. Degrades with
    # explicit warnings, never silently.
    warnings = []
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
        warnings.append("no narration clips — walkthrough degrades to music-only")
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

    scenes = [build_scene(s, i) for i, s in enumerate(cfg["scenes"], 1)]

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

    # Bundled display font -> identical typography on every OS (see shared.tsx).
    bundled_font = (Path(__file__).resolve().parent.parent / "assets" / "fonts"
                    / "PlayfairDisplay.ttf")
    if bundled_font.exists():
        stage(bundled_font, "font-display.ttf")
    sans_font = bundled_font.parent / "SourceSans3.ttf"
    if sans_font.exists():
        stage(sans_font, "font-sans.ttf")
    if not bundled_font.exists():
        warnings.append("bundled display font missing — comps fall back to system serif")

    headshot_ref = None
    if brand.headshot_path:
        headshot_ref = stage(brand.headshot_path, "headshot.jpg")

    props = {
        "brand": {
            "primary": colors["primary"],
            "secondary": colors.get("secondary", colors["primary"]),
            "accent": colors.get("accent", colors["primary"]),
            "textOnDark": colors.get("text-on-dark", "#ffffff"),
            "logoDark": stage(brand.logo_path("dark"), "logo-dark.png"),
            "headshot": headshot_ref,
            "name": brand.slug.replace("-", " ").title(),
        },
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

    total_f = 72 + sum(s["frames"] for s in scenes) + end_frames
    print(f"VIDEO PROPS v2 {brand.slug} -> {out}")
    print(f"  {len(scenes)} scenes, walkthrough ≈ {total_f / FPS:.1f}s, "
          f"narration {sum(s['voDurationS'] for s in scenes) + end_vo_dur:.1f}s, "
          f"bed: {'yes' if bed_ref else 'NO'}")
    for w in warnings:
        print(f"  WARN: {w}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
