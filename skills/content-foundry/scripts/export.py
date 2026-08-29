#!/usr/bin/env python3
"""Stage 9 — EXPORT. Size, encode, and name a linted asset per channel.

Only runs on assets that PASSED brand lint — it refuses anything without a
manifest, because an unverified asset must not reach a channel-named file that
looks shippable.

Naming: [AGENT]_[TYPE]_[descriptor]_[YYYY-MM-DD]_[channel].[ext]

Usage:
    python export.py <asset.jpg> --agent-slug riley-shore --type new-listing \\
        --descriptor lakefront-craftsman --channels ig,fb,li --outdir output/

Exit codes: 0 = exported, 1 = refused, 2 = usage error
"""

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    print("STOP: Pillow required. pip install Pillow", file=sys.stderr)
    sys.exit(2)

# Mirrors references/channel-specs.md §Export defaults.
EXPORT = {
    "ig":  {"size": (1080, 1350), "fmt": "JPEG", "quality": 90, "max_mb": 8},
    "igs": {"size": (1080, 1920), "fmt": "JPEG", "quality": 90, "max_mb": 8},
    "fb":  {"size": (1200, 630),  "fmt": "JPEG", "quality": 90, "max_mb": 8},
    "li":  {"size": (1200, 1200), "fmt": "JPEG", "quality": 90, "max_mb": 5},
    "tt":  {"size": (1080, 1920), "fmt": "JPEG", "quality": 90, "max_mb": 8},
    "yt":  {"size": (1280, 720),  "fmt": "JPEG", "quality": 90, "max_mb": 2},
    "x":   {"size": (1600, 900),  "fmt": "JPEG", "quality": 90, "max_mb": 5},
}

SLUG_RE = re.compile(r"[^a-z0-9-]+")


def slugify(s):
    return SLUG_RE.sub("-", s.lower().strip()).strip("-")


def main():
    ap = argparse.ArgumentParser(description="Content Foundry Stage 9 — EXPORT")
    ap.add_argument("asset")
    ap.add_argument("--agent-slug", required=True)
    ap.add_argument("--type", required=True, help="e.g. new-listing, just-sold")
    ap.add_argument("--descriptor", required=True)
    ap.add_argument("--channels", required=True, help="comma list: ig,fb,li,...")
    ap.add_argument("--outdir", default="output")
    args = ap.parse_args()

    asset_p = Path(args.asset)
    if not asset_p.exists():
        print(f"STOP: asset not found: {asset_p}", file=sys.stderr)
        return 1
    man_p = asset_p.with_suffix(".composite.json")
    if not man_p.exists():
        print(f"STOP: refusing to export — no composite manifest at {man_p}. "
              f"Only linted, provenance-carrying assets get channel names.",
              file=sys.stderr)
        return 1
    src_manifest = json.loads(man_p.read_text())
    src_channel = src_manifest.get("channel")

    channels = [c.strip() for c in args.channels.split(",") if c.strip()]
    bad = [c for c in channels if c not in EXPORT]
    if bad:
        print(f"STOP: unknown channel(s): {', '.join(bad)}. "
              f"Known: {', '.join(sorted(EXPORT))}", file=sys.stderr)
        return 2

    img = Image.open(asset_p).convert("RGB")
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    stem = "_".join([slugify(args.agent_slug), slugify(args.type),
                     slugify(args.descriptor), today])

    results, refused = [], []
    for ch in channels:
        spec = EXPORT[ch]
        tw, th = spec["size"]
        if (img.width, img.height) == (tw, th):
            out_img = img
            note = "native"
        elif ch == src_channel:
            out_img = img.resize((tw, th), Image.Resampling.LANCZOS)
            note = "resized same-channel"
        else:
            # A composite is laid out for ONE channel's safe zones. Center-crop
            # to a different aspect would move the logo/compliance out of their
            # verified positions — that must be a re-composite, not a crop.
            refused.append((ch, "asset was composited for "
                            f"'{src_channel}' — re-run composite.py for '{ch}' "
                            f"instead of cropping verified layout"))
            continue

        out_p = outdir / f"{stem}_{ch}.jpg"
        out_img.save(out_p, spec["fmt"], quality=spec["quality"])
        size_mb = out_p.stat().st_size / (1024 * 1024)
        if size_mb > spec["max_mb"]:
            out_img.save(out_p, spec["fmt"], quality=80)
            size_mb = out_p.stat().st_size / (1024 * 1024)
        results.append({"channel": ch, "path": str(out_p),
                        "size": [out_img.width, out_img.height],
                        "mb": round(size_mb, 2), "note": note})

    summary = {
        "exported_on": today,
        "agent": args.agent_slug,
        "source_asset": str(asset_p),
        "source_manifest": str(man_p),
        "results": results,
        "refused": [{"channel": c, "reason": r} for c, r in refused],
    }
    sum_p = outdir / f"{stem}_export.json"
    sum_p.write_text(json.dumps(summary, indent=2))

    print(f"EXPORT {asset_p.name}")
    for r in results:
        print(f"  {r['channel']}: {r['path']} ({r['size'][0]}x{r['size'][1]}, "
              f"{r['mb']} MB, {r['note']})")
    for c, reason in refused:
        print(f"  REFUSED {c}: {reason}")
    print(f"  summary -> {sum_p}")
    return 0 if results else 1


if __name__ == "__main__":
    sys.exit(main())
