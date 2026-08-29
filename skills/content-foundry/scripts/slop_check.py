#!/usr/bin/env python3
"""Content Foundry slop linter (vendored from RyVibes). Scans design output files for mechanical slop signatures.

Usage:
    python slop_check.py <path> [<path> ...]

Paths can be files or directories (scanned recursively). Scans .html, .css,
.scss, .js, .jsx, .ts, .tsx, .md, .mdx, .svelte, .vue, .astro files.

Exit codes: 0 = clean, 1 = findings, 2 = usage error.
Findings are flags for human judgment, not automatic failures — but every
finding must be fixed or dismissed with a documented reason in the run's qc notes.
"""

import json
import re
import sys
from pathlib import Path

SCAN_EXTS = {".html", ".css", ".scss", ".js", ".jsx", ".ts", ".tsx",
             ".md", ".mdx", ".svelte", ".vue", ".astro"}
SKIP_DIRS = {"node_modules", ".git", "dist", "build", ".next", "out", "vendor"}

FLAG_MAP = {"i": re.IGNORECASE, "u": re.UNICODE, "m": re.MULTILINE}


def compile_flags(flag_str):
    flags = 0
    for ch in flag_str:
        flags |= FLAG_MAP.get(ch, 0)
    return flags


def load_config():
    cfg_path = Path(__file__).parent / "slop-patterns.json"
    with open(cfg_path, encoding="utf-8") as f:
        return json.load(f)


def collect_files(paths):
    files = []
    for p in paths:
        path = Path(p)
        if path.is_file():
            files.append(path)
        elif path.is_dir():
            for f in sorted(path.rglob("*")):
                if f.is_file() and f.suffix.lower() in SCAN_EXTS \
                        and not any(part in SKIP_DIRS for part in f.parts):
                    files.append(f)
        else:
            print(f"warning: {p} not found, skipping", file=sys.stderr)
    return files


def line_of(text, idx):
    return text.count("\n", 0, idx) + 1


def scan_file(path, cfg):
    findings = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        print(f"warning: cannot read {path}: {e}", file=sys.stderr)
        return findings

    lower = text.lower()

    # Banned phrases (case-insensitive substring)
    for phrase in cfg.get("banned_phrases", []):
        start = 0
        while True:
            idx = lower.find(phrase.lower(), start)
            if idx == -1:
                break
            findings.append((path, line_of(text, idx), "copy",
                             f'banned phrase: "{phrase}"'))
            start = idx + len(phrase)

    # Regex patterns
    all_regex = list(cfg.get("banned_regex", []))
    all_regex += list(cfg.get("structural_checks", {}).values())
    for rule in all_regex:
        try:
            rx = re.compile(rule["pattern"], compile_flags(rule.get("flags", "")))
        except re.error as e:
            print(f"warning: bad pattern '{rule.get('label')}': {e}", file=sys.stderr)
            continue
        if "em dash density" in rule.get("label", ""):
            continue  # handled separately below
        for m in rx.finditer(text):
            findings.append((path, line_of(text, m.start()), "pattern",
                             rule["label"]))

    # Em dash density (prose files only)
    if path.suffix.lower() in {".md", ".mdx", ".html"}:
        words = len(text.split())
        dashes = text.count("\u2014")
        max_per_500 = cfg.get("em_dash_max_per_500_words", 2)
        if words > 0 and dashes > max(1, (words / 500) * max_per_500):
            findings.append((path, 0, "copy",
                             f"em dash density: {dashes} in {words} words "
                             f"(threshold {max_per_500}/500w) — AI fingerprint"))

    return findings


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2

    cfg = load_config()
    files = collect_files(sys.argv[1:])
    if not files:
        print("no scannable files found", file=sys.stderr)
        return 2

    all_findings = []
    for f in files:
        all_findings.extend(scan_file(f, cfg))

    if not all_findings:
        print(f"CLEAN — {len(files)} file(s) scanned, 0 findings.")
        return 0

    print(f"FINDINGS — {len(all_findings)} across {len(files)} file(s) scanned:\n")
    for path, line, cat, label in all_findings:
        loc = f"{path}:{line}" if line else str(path)
        print(f"  [{cat}] {loc}\n      {label}")
    print(f"\n{cfg.get('exceptions_note', '')}")
    print("\nFix every finding or document the dismissal in the run's qc notes. "
          "If a pattern recurs, root-cause it (references/loop-debugging.md).")
    return 1


if __name__ == "__main__":
    sys.exit(main())
