#!/usr/bin/env python3
"""Stage 1 — INGEST. Walk a drop folder, emit asset-manifest.json.

Deterministic. Catches empty folders, unsupported files, and duplicates BEFORE any
tokens are spent on unification or generation.

Usage:
    python inventory.py <drop-path> [--out manifest.json] [--quiet]
    python inventory.py none --job <n> --agent <agent-dir> --out manifest.json
    python inventory.py <drop-path> --allow-empty --job <n> --agent <agent-dir> --out ...

No-drop path: research-only library jobs (an entry in prompt-library.md with no
"Needs from drop" line, or whose only need the agent folder already satisfies,
e.g. #5's headshot) may run with no dropped assets. It must be asked for
explicitly (drop path `none`, or `--allow-empty`) and named (`--job`). It is
refused for any job that needs something only a drop can supply. The decision is
recorded in the manifest and in run.json (next to --out unless --run-json says
otherwise), so every later stage can see the run had no drop.

Exit codes:
    0 = usable assets found, or an allowed no-drop job
    1 = folder empty, missing, or no usable assets (STOP the pipeline, do not spend tokens)
    2 = usage error
"""

import argparse
import hashlib
import json
import os
import re
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

PROMPT_LIBRARY = Path(__file__).resolve().parent.parent / "references" / "prompt-library.md"
# Drop needs that the agent folder can satisfy instead of the drop. Keyed by a
# phrase in the library's "Needs from drop" line -> check against AgentBrand.
AGENT_FOLDER_NEEDS = {"agent headshot": ("headshot", lambda b: b.headshot_path)}

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


def library_entries(path=PROMPT_LIBRARY):
    """Parse prompt-library.md into {number: {title, needs, research}}."""
    entries, cur = {}, None
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^##\s+(\d+)\.\s+(.+?)\s*$", line)
        if m:
            cur = {"number": int(m.group(1)), "title": m.group(2).strip(),
                   "needs": None, "research": None}
            entries[cur["number"]] = cur
            continue
        if line.startswith("## ") or line.startswith("---"):
            cur = None
            continue
        if cur is None:
            continue
        m = re.search(r"\*\*Needs from drop:\*\*\s*(.+)$", line)
        if m:
            cur["needs"] = m.group(1).strip()
        m = re.search(r"\*\*Research:\*\*\s*\**\s*(skip|light|deep)", line, re.I)
        if m:
            cur["research"] = m.group(1).lower()
    return entries


def resolve_job(job, entries):
    """Accept '4', '#4', or a title fragment ('market update')."""
    key = str(job).strip().lstrip("#")
    if key.isdigit():
        return entries.get(int(key))
    norm = lambda t: re.sub(r"[^a-z0-9]+", " ", t.lower()).strip()
    hits = [e for e in entries.values() if norm(key) in norm(e["title"])]
    return hits[0] if len(hits) == 1 else None


def no_drop_decision(job, agent_dir):
    """Decide whether a named library job may run with no drop.

    Returns (allowed, record, message). The record goes into the manifest and
    run.json; the message is what the operator reads either way.
    """
    if not job:
        return False, None, ("a no-drop run must name its library job (--job N). "
                             "Freehand prompts need a drop.")
    entry = resolve_job(job, library_entries())
    if entry is None:
        return False, None, (f"--job {job!r} is not an entry in "
                             f"references/prompt-library.md")
    record = {"mode": "none", "job": entry["number"], "job_title": entry["title"],
              "research": entry["research"], "satisfied_from_agent_folder": {}}
    label = f"#{entry['number']} {entry['title']}"
    needs = entry["needs"]
    if not needs:
        return True, record, f"{label} needs nothing from the drop (research: {entry['research']})"

    unmet = []
    for part in [n.strip() for n in re.split(r",|\band\b", needs) if n.strip()]:
        hit = next((k for k in AGENT_FOLDER_NEEDS if k in part.lower()), None)
        if not hit:
            unmet.append(part)
            continue
        if not agent_dir:
            unmet.append(f"{part} (or declare it in the agent folder and pass --agent)")
            continue
        try:
            from brandkit import AgentBrand, BrandError
        except ImportError:
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            from brandkit import AgentBrand, BrandError
        try:
            found = AGENT_FOLDER_NEEDS[hit][1](AgentBrand(agent_dir))
        except BrandError as e:
            return False, None, str(e)
        if found:
            record["satisfied_from_agent_folder"][AGENT_FOLDER_NEEDS[hit][0]] = str(found)
        else:
            unmet.append(f"{part} (none declared in brand-context-visual.md, "
                         f"or the declared file is missing)")
    if unmet:
        return False, None, (f"{label} needs from the drop: {'; '.join(unmet)}. "
                             f"It cannot run without a drop.")
    got = ", ".join(f"{k} from {v}" for k, v in record["satisfied_from_agent_folder"].items())
    return True, record, f"{label}: drop need met by the agent folder ({got})"


def record_run_json(path, drop_record):
    """Merge the drop decision into run.json without touching other keys."""
    path = Path(path)
    data = {}
    if path.exists():
        try:
            data = json.loads(path.read_text())
        except json.JSONDecodeError:
            print(f"STOP: {path} is not valid JSON; not overwriting it.", file=sys.stderr)
            return False
    data["drop"] = drop_record
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")
    return True


def main():
    ap = argparse.ArgumentParser(description="Content Foundry Stage 1 — INGEST")
    ap.add_argument("drop_path", help="drop folder, or `none` for a no-drop library job")
    ap.add_argument("--out", default=None, help="manifest output path")
    ap.add_argument("--allow-empty", action="store_true",
                    help="continue with no usable assets IF --job needs nothing from the drop")
    ap.add_argument("--job", default=None,
                    help="prompt-library job number or title (required for a no-drop run)")
    ap.add_argument("--agent", default=None,
                    help="agent folder; lets a drop need (e.g. headshot) be met from it")
    ap.add_argument("--run-json", default=None,
                    help="run.json to record the drop decision in (default: next to --out)")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    no_drop = args.drop_path.strip().lower() == "none"
    allow_empty = args.allow_empty or no_drop
    run_json = args.run_json or (str(Path(args.out).parent / "run.json") if args.out else None)

    if no_drop:
        drop = None
        assets, unsupported = [], []
    else:
        drop = Path(args.drop_path).expanduser()
        if not drop.exists():
            print(f"STOP: drop folder does not exist: {drop}. For a research-only "
                  f"library job, pass `none` as the drop with --job.", file=sys.stderr)
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
        "drop_path": str(drop.resolve()) if drop else None,
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

    # The drop decision. A no-drop run is never implicit: it needs `none` or
    # --allow-empty AND a library job whose needs the drop is not required for.
    drop_record = {"mode": "folder", "path": manifest["drop_path"]}
    decision_msg, stop_msg = None, None
    if not usable:
        if not allow_empty:
            stop_msg = ("no usable assets. Nothing to unify — pipeline halted before "
                        "spending tokens.\n      A research-only library job (no 'Needs "
                        "from drop' in prompt-library.md) can run without a drop:\n"
                        "      inventory.py none --job <n> --agent <agent-dir> --out ...")
        else:
            allowed, rec, decision_msg = no_drop_decision(args.job, args.agent)
            if allowed:
                rec.update(drop_path=manifest["drop_path"], reason=decision_msg,
                           decided_at=manifest["generated_at"])
                drop_record = rec
            else:
                stop_msg = f"no usable assets, and the no-drop path is refused: {decision_msg}"
        if stop_msg:
            drop_record = {"mode": "stopped", "path": manifest["drop_path"],
                           "reason": stop_msg.splitlines()[0]}
    manifest["drop"] = drop_record

    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(manifest, indent=2))

    _report(args, manifest, drop, dupes, unsupported, groups)
    if stop_msg:
        sys.stdout.flush()  # keep the summary above the STOP line
        print(f"\nSTOP: {stop_msg}", file=sys.stderr)
        return 1

    if run_json and not record_run_json(run_json, drop_record):
        return 1
    if drop_record["mode"] == "none" and not args.quiet:
        print(f"  NO DROP: {decision_msg}")
        print("  Every fact must trace to a Stage 3 citation or the agent folder. "
              "All QC gates still apply.")
        if run_json:
            print(f"  recorded in {run_json} (drop.mode = none)")
    return 0


def _report(args, manifest, drop, dupes, unsupported, groups):
    assets = manifest["assets"]
    if not args.quiet:
        s = manifest["summary"]
        print(f"INGEST {drop if drop else '(no drop)'}")
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


if __name__ == "__main__":
    sys.exit(main())
