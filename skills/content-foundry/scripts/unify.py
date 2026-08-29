#!/usr/bin/env python3
"""Stage 2 — UNIFY. Convert the asset manifest into one canonical context document.

Deterministic where possible, generative where necessary — literally:
  - text files: read inline
  - links found in text: listed for the skill to fetch (WebFetch is the runtime's job)
  - PDFs: extracted via pdftotext if installed, else queued for the skill
  - images: EXIF pulled here; DESCRIPTION slots emitted for the model to fill
  - audio/video: transcription queued (whisper or platform-native, runtime's job)

The output document contains explicit `<!-- MODEL: ... -->` slots. The skill fills
every slot before Stage 3; an unfilled slot in a brief is a defect.

Usage:
    python unify.py <asset-manifest.json> --out unified-context.md

Exit codes: 0 = ok, 1 = manifest unusable, 2 = usage error
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

URL_RE = re.compile(r"https?://[^\s)>\]]+")
MAX_INLINE_CHARS = 6000  # per text asset; longer content is truncated with a note


def read_text(path):
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return f"(unreadable: {e})"


def pdf_text(path):
    """Extract with pdftotext when available. Absence is reported, not fatal."""
    if shutil.which("pdftotext"):
        try:
            r = subprocess.run(["pdftotext", "-layout", str(path), "-"],
                               capture_output=True, text=True, timeout=60)
            if r.returncode == 0 and r.stdout.strip():
                return r.stdout, "pdftotext"
        except (subprocess.SubprocessError, OSError):
            pass
    return None, None


def main():
    ap = argparse.ArgumentParser(description="Content Foundry Stage 2 — UNIFY")
    ap.add_argument("manifest")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    man_p = Path(args.manifest)
    if not man_p.exists():
        print(f"STOP: manifest not found: {man_p}", file=sys.stderr)
        return 1
    manifest = json.loads(man_p.read_text())
    assets = [a for a in manifest.get("assets", [])
              if a.get("duplicate_of") is None]
    if not assets:
        print("STOP: manifest has no usable assets", file=sys.stderr)
        return 1

    lines = ["# Unified Context",
             "",
             f"Source drop: `{manifest.get('drop_path')}`",
             f"Assets: {len(assets)} usable "
             f"({manifest['summary']['duplicates']} duplicate(s) skipped, "
             f"{manifest['summary']['unsupported']} unsupported reported)",
             ""]
    model_slots = 0

    groups = {}
    for a in assets:
        groups.setdefault(a.get("group") or "(root)", []).append(a)

    for group, items in sorted(groups.items()):
        lines += [f"## Group: {group}", ""]
        for a in sorted(items, key=lambda x: x["path"]):
            cat, handler = a["category"], a["unify_handler"]
            lines.append(f"### `{a['path']}` — {cat}")

            if cat == "image":
                dims = (f"{a.get('width')}x{a.get('height')}"
                        if a.get("width") else "unknown dims")
                shot = (" — screenshot dimensions: classify as photography vs "
                        "reference graphic" if a.get("screenshot_dimensions") else "")
                lines.append(f"- {dims}, {a['size_bytes'] // 1024} KB{shot}")
                lines.append(f"<!-- MODEL: describe this image. State (1) what it "
                             f"shows, (2) photography vs finished graphic vs "
                             f"screenshot-of-graphic, (3) any legible text in it, "
                             f"(4) usability as a base image. Path: "
                             f"{a['abs_path']} -->")
                model_slots += 1

            elif handler == "transcribe":
                lines.append(f"- {a['size_bytes'] // 1024} KB — transcription "
                             f"required")
                lines.append(f"<!-- MODEL: transcribe {a['abs_path']} (whisper or "
                             f"platform-native), then summarize speakers + key "
                             f"claims. Every claim used in a brief must trace "
                             f"here. -->")
                model_slots += 1

            elif handler == "extract":
                text, tool = pdf_text(a["abs_path"])
                if text:
                    t = text.strip()
                    if len(t) > MAX_INLINE_CHARS:
                        t = t[:MAX_INLINE_CHARS] + "\n(truncated — full text in source PDF)"
                    lines += [f"- extracted via {tool}:", "", "```", t, "```"]
                else:
                    lines.append("<!-- MODEL: pdftotext unavailable — read this "
                                 f"PDF directly and extract its text: "
                                 f"{a['abs_path']} -->")
                    model_slots += 1

            elif handler == "read_or_fetch":
                text = read_text(a["abs_path"])
                urls = URL_RE.findall(text)
                body = text.strip()
                if len(body) > MAX_INLINE_CHARS:
                    body = body[:MAX_INLINE_CHARS] + "\n(truncated)"
                if body:
                    lines += ["", "```", body, "```"]
                for u in urls:
                    lines.append(f"<!-- MODEL: fetch {u} and summarize what it "
                                 f"contributes (listing data, article, comp). "
                                 f"Cite it if any fact from it reaches a brief. -->")
                    model_slots += 1

            elif handler == "report_only":
                lines.append(f"- structured data file, {a['size_bytes']} bytes — "
                             f"NOT auto-ingested. Ask the user whether it matters "
                             f"for this job before reading it.")

            lines.append("")

    if manifest.get("unsupported"):
        lines += ["## Unsupported (reported, not fatal)", ""]
        for u in manifest["unsupported"]:
            lines.append(f"- `{u['path']}` ({u['ext']})")
        lines.append("")

    lines += ["---",
              f"MODEL SLOTS TO FILL: {model_slots}. Stage 3 (RESEARCH) must not "
              f"begin until every slot above is resolved.",
              ""]

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines))
    print(f"UNIFY -> {out}")
    print(f"  {len(assets)} assets, {model_slots} model slot(s) to fill")
    return 0


if __name__ == "__main__":
    sys.exit(main())
