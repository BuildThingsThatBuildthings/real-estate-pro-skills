#!/usr/bin/env python3
"""Content Foundry dependency doctor.

Run this at setup (SKILL.md setup step 5) and any time something feels broken.
Checks every dependency by tier, prints per-OS install commands for anything
missing, and exits non-zero only if a REQUIRED dependency is absent.

    python scripts/doctor.py

Tiers:
  required  — stills pipeline (the core product)
  video     — Remotion walkthrough/sales-brief/teaser + scroll tour
  optional  — Post Bridge scheduling
"""

import platform
import shutil
import subprocess
import sys
from pathlib import Path

OS = platform.system()  # 'Darwin' | 'Linux' | 'Windows'

HINTS = {
    "ffmpeg": {
        "Darwin": "brew install ffmpeg",
        "Linux": "sudo apt install ffmpeg   (or your distro's package manager)",
        "Windows": "winget install Gyan.FFmpeg   (or download from ffmpeg.org)",
    },
    "node": {
        "Darwin": "brew install node   (or https://nodejs.org — LTS)",
        "Linux": "https://nodejs.org — LTS (or your distro's nodejs package)",
        "Windows": "winget install OpenJS.NodeJS.LTS",
    },
    "pillow": {
        "Darwin": "pip3 install Pillow", "Linux": "pip3 install Pillow",
        "Windows": "pip install Pillow",
    },
}


def hint(name):
    return HINTS.get(name, {}).get(OS, f"install {name}")


def check_cmd(name, args, min_major=None):
    exe = shutil.which(args[0])
    if not exe:
        return False, "not found"
    try:
        out = subprocess.run(args, capture_output=True, text=True, timeout=15)
        ver = (out.stdout or out.stderr).strip().splitlines()[0]
    except Exception as e:  # noqa: BLE001 — report anything, this is a doctor
        return False, f"found but errored: {e}"
    if min_major is not None:
        import re
        m = re.search(r"v?(\d+)\.", ver)
        if m and int(m.group(1)) < min_major:
            return False, f"{ver} (need >= {min_major})"
    return True, ver


def main():
    results = []  # (tier, name, ok, detail, hint)

    ok = sys.version_info >= (3, 10)
    results.append(("required", "python >= 3.10", ok,
                    platform.python_version(), "install Python 3.10+"))

    try:
        import PIL
        results.append(("required", "Pillow", True, PIL.__version__, ""))
    except ImportError:
        results.append(("required", "Pillow", False, "not installed",
                        hint("pillow")))

    fonts = Path(__file__).resolve().parent.parent / "assets" / "fonts"
    have_fonts = (fonts / "PlayfairDisplay.ttf").exists()
    results.append(("required", "bundled fonts", have_fonts,
                    str(fonts) if have_fonts else "missing",
                    "re-download the skill package — assets/fonts/ is part of it"))

    for tier, name, args, mm in (
        ("video", "ffmpeg", ["ffmpeg", "-version"], None),
        ("video", "ffprobe", ["ffprobe", "-version"], None),
        ("video", "node >= 18", ["node", "--version"], 18),
        ("video", "npm", ["npm", "--version"], None),
    ):
        ok, detail = check_cmd(name, args, mm)
        results.append((tier, name, ok, detail,
                        hint(args[0]) if not ok else ""))

    engine = Path(__file__).resolve().parent.parent / "engines" / "remotion"
    node_modules = (engine / "node_modules").exists()
    results.append(("video", "remotion engine installed", node_modules,
                    "ready" if node_modules else "not yet installed",
                    f"cd {engine} && npm install   (first video use only)"))

    if shutil.which("npx"):
        r = subprocess.run(["npx", "-y", "postbridge-cli"],
                           capture_output=True, text=True, timeout=60)
        ok_pb = "post" in (r.stdout + r.stderr).lower()
        detail_pb = "available via npx" if ok_pb else "not reachable"
    else:
        ok_pb, detail_pb = False, "needs node/npm"
    results.append(("optional", "Post Bridge CLI", ok_pb, detail_pb,
                    "npx postbridge-cli setup --key <your-key>  "
                    "(post-bridge.com → Settings → API)"))

    print("Content Foundry doctor\n" + "=" * 46)
    failed_required = False
    for tier, name, ok, detail, fix in results:
        mark = "OK " if ok else ("!! " if tier == "required" else "-- ")
        print(f"{mark}[{tier:8}] {name}: {detail}")
        if not ok and fix:
            print(f"            fix: {fix}")
        if not ok and tier == "required":
            failed_required = True

    print("=" * 46)
    if failed_required:
        print("Result: REQUIRED dependencies missing — stills pipeline will "
              "not run. Fix the !! lines above.")
        return 1
    video_ok = all(ok for t, _, ok, _, _ in results if t == "video")
    print("Result: core pipeline ready."
          + (" Video engines ready." if video_ok else
             " Video engines need the -- items above (stills still work)."))
    return 0


if __name__ == "__main__":
    sys.exit(main())
