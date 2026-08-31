#!/usr/bin/env python3
"""listing-price-brief dependency doctor.  Run at setup; reports which comp-source tier is live."""
import json, os, sys
_HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.realpath(os.path.join(_HERE, "..", "..", "..", "lib")))
from skill_doctor import Doctor  # noqa: E402

d = Doctor("listing-price-brief")
d.python()
d.sibling_import("compliance-gate", "fair_housing",
                 probe=lambda m: f"{len(m.BANNED)} banned phrases, {len(m.PROMISE)} promise patterns")
# comp-source tier from config/mls.json: export (always works) | browser | reso
tier = "export"
for up in range(1, 5):
    p = os.path.realpath(os.path.join(_HERE, *[".."] * up, "config", "mls.json"))
    if os.path.isfile(p):
        tier = json.load(open(p)).get("tier", "export")
        break
d.check("optional", "comp source tier", True,
        f"{tier}" + ("" if tier != "export" else " (default: agent drops their own MLS/RPR export)"))
d.self_test()
sys.exit(d.finish("Ready. Python owns every number; nothing is published below the comp floor."))
