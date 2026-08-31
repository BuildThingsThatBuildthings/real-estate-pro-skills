#!/usr/bin/env python3
"""compliance-gate dependency doctor.

This skill is the canonical home of the Fair Housing rules — four other skills
import from here, so its self-test failing means THEIR gates are lying too.
"""
import os, sys
_HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.realpath(os.path.join(_HERE, "..", "..", "..", "lib")))
sys.path.insert(0, _HERE)
from skill_doctor import Doctor  # noqa: E402

d = Doctor("compliance-gate")
d.python()
try:
    import fair_housing
    d.check("required", "fair_housing import", True,
            f"{len(fair_housing.BANNED)} banned, {len(fair_housing.PROMISE)} promise, "
            f"{len(fair_housing.NEEDS_SOURCE)} needs-source")
except Exception as e:  # noqa: BLE001
    d.check("required", "fair_housing import", False, f"{e}")
profiles = []
root = os.path.realpath(os.path.join(_HERE, "..", "..", "..", "config", "compliance"))
if os.path.isdir(root):
    profiles = [f[:-5] for f in os.listdir(root) if f.endswith(".json") and ".example" not in f]
d.check("optional", "MLS profiles", bool(profiles),
        ", ".join(profiles) if profiles else "none configured — baseline only, which is valid")
d.self_test()
sys.exit(d.finish("Ready. One copy of the rules; every skill in the bundle checks against this one."))
