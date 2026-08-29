#!/usr/bin/env python3
"""Stage 1 — INGEST. Walk a drop folder, emit asset-manifest.json.

Deterministic. Catches empty folders, unsupported files, and duplicates BEFORE any
tokens are spent on unification or generation.

Usage:
    python inventory.py <drop-path> [--out manifest.json] [--quiet]

Exit codes:
    0 = usable assets found
    1 = folder empty, missing, or no usable assets (STOP the pipeline, do not spend tokens)
    2 = usage error
"""

import argparse
import hashlib
import json
import os
import struct
import sys
from datetime import datetime, timezone
from pathlib import Path

# Type routing for Stage 2 (UNIFY). Extension -> (category, unify handler)
TYPE_MAP = {
    # images -> model description + EXIF
    ".jpg": ("image", "describe"), ".jpeg": ("image", "describe"),
    ".png": ("image", "describe"), ".heic": ("image", "describe"),
    ".webp": ("image", "describe"), ".gif": ("image", "describe"),
    ".tiff": ("image", "describe"), ".tif": ("image", "describe"),
    # video -> transcribe + keyframe
    ".mp4": ("video", "transcribe"), ".mov": ("video", "transcribe"),
    ".m4v": ("video", "transcribe"), ".avi": ("video", "transcribe"),
    ".webm": ("video", "transcribe"),
    # audio -> transcribe
    ".mp3": ("audio", "transcribe"), ".wav": ("audio", "transcribe"),
    ".m4a": ("audio", "transcribe"), ".aac": ("audio", "transcribe"),
    ".flac": ("audio", "transcribe"),
    # documents -> extract text
    ".pdf": ("document", "extract"),
    ".docx": ("document", "extract"),
    # text -> read; may contain links to fetch
    ".txt": ("text", "read_or_fetch"), ".md": ("text", "read_or_fetch"),
    ".rtf": ("text", "read_or_fetch"),
    # structured -> report but do not unify (common accidental drop)
    ".csv": ("data", "report_only"), ".xlsx": ("data", "report_only"),
    ".numbers": ("data", "report_only"),
}

SKIP_NAMES = {".DS_Store", "Thumbs.db", "desktop.ini", ".gitkeep"}
SKIP_DIRS = {"__MACOSX", ".git", "node_modules", ".venv"}


def sha256(path, chunk=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while block := f.read(chunk):
            h.update(block)
    return h.hexdigest()


def image_dims(path):
    """Read dimensions from JPEG/PNG headers without a dependency.

    Returns (w, h) or None. Pillow would be cleaner but inventory must run
    before any pip install — this stage's whole job is failing cheaply.
    """
    try:
        with open(path, "rb") as f:
            head = f.read(26)
            if head[:8] == b"\x89PNG\r\n\x1a\n":
                w, h = struct.unpack(">II", head[16:24])
                return int(w), int(h)
            if head[:2] == b"\xff\xd8":  # JPEG: walk segment markers
                f.seek(2)
                while True:
                    b = f.read(1)
                    while b and b != b"\xff":
                        b = f.read(1)
                    marker = f.read(1)
                    while marker == b"\xff":
                        marker = f.read(1)
                    if not marker:
                        return None
                    m = marker[0]
                    if 0xC0 <= m <= 0xCF and m not in (0xC4, 0xC8, 0xCC):
                        f.read(3)
                        h, w = struct.unpack(">HH", f.read(4))
                        return int(w), int(h)
                    seg = f.read(2)
                    if len(seg) < 2:
                        return None
                    (length,) = struct.unpack(">H", seg)
                    f.seek(length - 2, os.SEEK_CUR)
    except Exception:
        return None
    return None


def scan(drop_path):
    assets, unsupported = [], []
    for root, dirs, files in os.walk(drop_path):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
        for name in sorted(files):
            if name in SKIP_NAMES or name.startswith("._"):
                continue
            p = Path(root) / name
            try:
                st = p.stat()
            except OSError:
                continue
            ext = p.suffix.lower()
            rel = str(p.relative_to(drop_path))
            if ext not in TYPE_MAP:
                unsupported.append({"path": rel, "ext": ext or "(none)",
                                    "size_bytes": st.st_size,
                                    "reason": "unrecognized extension"})
                continue
            category, handler = TYPE_MAP[ext]
            rec = {
                "path": rel,
                "abs_path": str(p.resolve()),
                "group": str(Path(rel).parent) if Path(rel).parent != Path(".") else None,
                "category": category,
                "unify_handler": handler,
                "ext": ext,
                "size_bytes": st.st_size,
                "modified": datetime.fromtimestamp(st.st_mtime, timezone.utc).isoformat(),
                "sha256": sha256(p),
            }
            if category == "image":
                dims = image_dims(p)
                if dims:
                    rec["width"], rec["height"] = dims
                    rec["aspect"] = round(dims[0] / dims[1], 4) if dims[1] else None
                    # Common iPhone screenshot widths. This detects CAPTURE METHOD
                    # only, not content: a screenshot of a listing photo is still
                    # usable photography, while a screenshot of a finished
                    # marketing graphic is a reference asset. Only UNIFY, which
                    # actually looks at the image, can tell them apart — so this
                    # flag routes to classification, it does not disqualify.
                    rec["screenshot_dimensions"] = dims[0] in (1170, 1179, 1284, 1290, 1320)
            assets.append(rec)
    return assets, unsupported


def find_duplicates(assets):
    by_hash = {}
    for a in assets:
        by_hash.setdefault(a["sha256"], []).append(a["path"])
    dupes = [{"sha256": h, "paths": p} for h, p in by_hash.items() if len(p) > 1]
    seen = set()
    for d in dupes:
        for path in d["paths"][1:]:
            seen.add(path)
    for a in assets:
        a["duplicate_of"] = None
        if a["path"] in seen:
            group = next(d for d in dupes if a["sha256"] == d["sha256"])
            a["duplicate_of"] = group["paths"][0]
    return dupes


def main():
    ap = argparse.ArgumentParser(description="Content Foundry Stage 1 — INGEST")
    ap.add_argument("drop_path")
    ap.add_argument("--out", default=None, help="manifest output path")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    drop = Path(args.drop_path).expanduser()
    if not drop.exists():
        print(f"STOP: drop folder does not exist: {drop}", file=sys.stderr)
        return 1
    if not drop.is_dir():
        print(f"STOP: not a folder: {drop}", file=sys.stderr)
        return 2

    assets, unsupported = scan(drop)
    dupes = find_duplicates(assets)

    usable = [a for a in assets
              if a["duplicate_of"] is None and a["unify_handler"] != "report_only"]
    groups = sorted({a["group"] for a in assets if a["group"]})

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "drop_path": str(drop.resolve()),
        "summary": {
            "total_files": len(assets) + len(unsupported),
            "assets": len(assets),
            "usable": len(usable),
            "duplicates": sum(len(d["paths"]) - 1 for d in dupes),
            "unsupported": len(unsupported),
            "by_category": {
                c: len([a for a in assets if a["category"] == c])
                for c in sorted({a["category"] for a in assets})
            },
            "groups": groups,
        },
        "assets": assets,
        "duplicates": dupes,
        "unsupported": unsupported,
    }

    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(manifest, indent=2))

    if not args.quiet:
        s = manifest["summary"]
        print(f"INGEST {drop}")
        print(f"  {s['assets']} assets ({s['usable']} usable) across "
              f"{len(groups) or 1} group(s)")
        for cat, n in s["by_category"].items():
            print(f"    {cat}: {n}")
        if s["duplicates"]:
            print(f"  {s['duplicates']} duplicate(s) — will be skipped:")
            for d in dupes:
                print(f"    {d['paths'][0]} == {', '.join(d['paths'][1:])}")
        if unsupported:
            # Reported, never fatal.
            print(f"  {len(unsupported)} unsupported file(s) — reported, not fatal:")
            for u in unsupported:
                print(f"    {u['path']} ({u['ext']})")
        shots = [a for a in assets if a.get("screenshot_dimensions")]
        if shots:
            print(f"  {len(shots)} file(s) have screenshot dimensions — UNIFY must "
                  f"classify each as photography vs. reference graphic")
        if args.out:
            print(f"  manifest -> {args.out}")

    if not usable:
        sys.stdout.flush()  # keep the summary above the STOP line
        print("\nSTOP: no usable assets. Nothing to unify — pipeline halted before "
              "spending tokens.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
