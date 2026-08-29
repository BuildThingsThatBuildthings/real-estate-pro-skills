#!/usr/bin/env python3
"""listing-price-brief dependency doctor.

    python3 scripts/doctor.py

Run at setup and any time the gate behaves strangely. Exits non-zero only if a
REQUIRED dependency is missing.

No network and no API keys in the export tier, which is the tier that always
works. The browser and reso tiers are configured per market in config/mls.json
and this doctor reports which one is live rather than guessing.

The one real dependency is the sibling content-foundry skill, because the Fair
Housing baseline is imported from it rather than copied. A second copy of those
rules would drift, and the copy that drifts is the one that reaches a client.
"""
import os
import platform
import subprocess
import sys
from pathlib import Path

OS = platform.system()
HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
BUNDLE = SKILL.parent.parent

HINTS = {
    "python": {
        "Darwin": "brew install python@3.11   (or https://python.org)",
        "Linux": "sudo apt install python3    (or your distro's package manager)",
        "Windows": "winget install Python.Python.3.11",
    },
    "content-foundry": {
        "Darwin": "the sibling skill is missing — re-run ./install.sh from the bundle root",
        "Linux": "the sibling skill is missing — re-run ./install.sh from the bundle root",
        "Windows": "the sibling skill is missing — re-run install.sh from the bundle root",
    },
}


def hint(name):
    return HINTS.get(name, {}).get(OS, f"install {name}")


class Doc:
    def __init__(self):
        self.required_missing = 0

    def check(self, tier, label, ok, detail):
        mark = "ok  " if ok else ("MISS" if tier == "required" else "warn")
        print(f"  [{tier:8}] {mark}  {label:<34} {detail}")
        if not ok and tier == "required":
            self.required_missing += 1
            print(f"                     -> {hint(label)}")


def main():
    d = Doc()
    print(f"listing-price-brief doctor — {OS}, python {platform.python_version()}\n")

    d.check("required", "python", sys.version_info >= (3, 8),
            f"{platform.python_version()} (need >= 3.8)")

    cf = BUNDLE / "skills" / "content-foundry" / "scripts" / "compliance.py"
    d.check("required", "content-foundry", cf.is_file(), str(cf) if cf.is_file() else "not found")

    # Importing it is the real test. Present-but-broken is the failure mode that
    # would otherwise pass every reconciliation silently.
    sys.path.insert(0, str(cf.parent))
    try:
        import compliance  # noqa: F401
        d.check("required", "fair housing baseline", True,
                f"{len(compliance.BANNED)} banned phrases, "
                f"{len(compliance.PROMISE)} promise patterns")
    except Exception as e:  # noqa: BLE001 — a doctor reports, it does not raise
        d.check("required", "fair housing baseline", False, f"import failed: {e}")

    # Optional: only needed when a client slug is passed to merge their card.
    try:
        sys.path.insert(0, str(BUNDLE / "skills" / "post-bridge-schedule" / "scripts"))
        import config as _cfg
        cc = _cfg.load("clients", required=False)
        d.check("optional", "clients.json", bool(cc),
                cc.get("_source", "not configured — --client will use the baseline only"))
    except Exception as e:  # noqa: BLE001
        d.check("optional", "clients.json", False, f"{e}")

    # Self-test. A doctor that does not exercise the gate cannot tell you the
    # gate still works, which is the only thing anyone actually wants to know.
    tests = SKILL / "tests" / "run_tests.sh"
    if tests.is_file():
        r = subprocess.run(["bash", str(tests)], capture_output=True, text=True,
                           cwd=str(SKILL), env={**os.environ})
        last = [l for l in r.stdout.strip().splitlines() if l.strip()]
        d.check("required", "gate self-test", r.returncode == 0,
                last[-1] if last else "no output")
        if r.returncode != 0:
            print(r.stdout)
    else:
        d.check("optional", "gate self-test", False, "tests/run_tests.sh not found")

    # Which comp tier is actually available. Guessing here would be the worst
    # possible failure: a brief built on a comp set nobody can reproduce.
    try:
        import subprocess as _sp
        t = _sp.run([sys.executable, str(HERE / "comp_source.py"), "tiers"],
                    capture_output=True, text=True)
        live = [l.strip() for l in t.stdout.splitlines() if "READY" in l or "CONFIGURED" in l]
        d.check("required", "comp source tier", bool(live), "; ".join(live) or "none available")
    except Exception as e:  # noqa: BLE001
        d.check("required", "comp source tier", False, str(e))

    print()
    if d.required_missing:
        print(f"{d.required_missing} required dependency missing. Fix the arrows above.")
        return 1
    print("Ready. Nothing here reaches a client until brief_gate.py exits 0, and nothing sends at all.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
