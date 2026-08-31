"""Shared doctor framework for the bundle's skills.

Each skill's scripts/doctor.py declares its checks and calls run(). One copy of
the checking logic, because the bundle's own law applies to its tooling too:
the copy that drifts is the one that lies to somebody at setup time.

Found from a skill's scripts/ dir the same way config/ is found — realpath and
upward traversal — so it works both in the repo and through a symlinked or
plugin install.

Usage, the whole thing:

    from skill_doctor import Doctor
    d = Doctor("my-skill")
    d.python(minimum=(3, 8))
    d.sibling_import("compliance-gate", "fair_housing",
                     probe=lambda m: f"{len(m.BANNED)} banned phrases")
    d.self_test()                       # runs tests/run_tests.sh
    d.check("optional", "clients.json", ok, detail)   # anything bespoke
    sys.exit(d.finish("Ready. <one line about what the gate protects>"))
"""
import inspect
import os
import platform
import subprocess
import sys

OS = platform.system()

HINTS = {
    "python": {
        "Darwin": "brew install python@3.11   (or https://python.org)",
        "Linux": "sudo apt install python3    (or your distro's package manager)",
        "Windows": "winget install Python.Python.3.11",
    },
}


class Doctor:
    def __init__(self, skill_name, skill_dir=None):
        self.name = skill_name
        if skill_dir is None:
            # the caller is <skill>/scripts/doctor.py
            caller = inspect.stack()[1].filename
            skill_dir = os.path.dirname(os.path.dirname(os.path.realpath(caller)))
        self.skill = skill_dir
        self.bundle = os.path.dirname(os.path.dirname(skill_dir))  # <repo> from skills/<name>
        self.required_missing = 0
        print(f"{skill_name} doctor — {OS}, python {platform.python_version()}\n")

    def check(self, tier, label, ok, detail, hint=None):
        mark = "ok  " if ok else ("MISS" if tier == "required" else "warn")
        print(f"  [{tier:8}] {mark}  {label:<34} {detail}")
        if not ok and tier == "required":
            self.required_missing += 1
            h = hint or HINTS.get(label, {}).get(OS) or f"install {label}"
            print(f"                     -> {h}")
        return ok

    def python(self, minimum=(3, 8)):
        self.check("required", "python", sys.version_info >= minimum,
                   f"{platform.python_version()} (need >= {'.'.join(map(str, minimum))})")

    def sibling_import(self, sibling, module, probe=None, tier="required"):
        """The bundle's skills share code by importing a sibling, never copying.
        Importing is the real test — present-but-broken is the failure mode that
        would otherwise pass everything silently."""
        path = os.path.join(self.bundle, "skills", sibling, "scripts")
        f = os.path.join(path, f"{module}.py")
        if not self.check(tier, sibling, os.path.isfile(f), f if os.path.isfile(f) else "not found",
                          hint="the sibling skill is missing — reinstall the whole bundle, "
                               "its skills import from each other"):
            return None
        sys.path.insert(0, path)
        try:
            m = __import__(module)
            self.check(tier, f"{module} import", True, probe(m) if probe else "imports clean")
            return m
        except Exception as e:  # noqa: BLE001 — a doctor reports, it does not raise
            self.check(tier, f"{module} import", False, f"import failed: {e}")
            return None

    def self_test(self, tier="required"):
        """Run the skill's own suite. A doctor that does not exercise the gate
        cannot tell you the gate still works — the only thing anyone asks it."""
        tests = os.path.join(self.skill, "tests", "run_tests.sh")
        if not os.path.isfile(tests):
            self.check("optional", "gate self-test", False, "tests/run_tests.sh not found")
            return
        r = subprocess.run(["bash", tests], capture_output=True, text=True, cwd=self.skill)
        last = [l for l in r.stdout.strip().splitlines() if l.strip()]
        self.check(tier, "gate self-test", r.returncode == 0, last[-1] if last else "no output")
        if r.returncode != 0:
            print(r.stdout)

    def finish(self, ready_line):
        print()
        if self.required_missing:
            print(f"{self.required_missing} required dependency missing. Fix the arrows above.")
            return 1
        print(ready_line)
        return 0

