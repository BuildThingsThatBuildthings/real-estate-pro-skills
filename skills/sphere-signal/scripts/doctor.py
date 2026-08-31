#!/usr/bin/env python3
"""sphere-signal dependency doctor.  Run at setup and whenever the gate acts oddly."""
import os, sys
_HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.realpath(os.path.join(_HERE, "..", "..", "..", "lib")))
from skill_doctor import Doctor  # noqa: E402

d = Doctor("sphere-signal")
d.python()
d.sibling_import("compliance-gate", "fair_housing",
                 probe=lambda m: f"{len(m.BANNED)} banned phrases, {len(m.PROMISE)} promise patterns")
d.self_test()
sys.exit(d.finish("Ready. Nothing goes out until touch_gate.py exits 0, and nothing sends at all."))
