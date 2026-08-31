#!/usr/bin/env python3
"""brand-voice dependency doctor."""
import glob, os, sys
_HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.realpath(os.path.join(_HERE, "..", "..", "..", "lib")))
from skill_doctor import Doctor  # noqa: E402

d = Doctor("brand-voice")
d.python()
root = os.path.realpath(os.path.join(_HERE, "..", "..", "..", "config", "voice"))
packs = [os.path.basename(p)[:-3] for p in glob.glob(os.path.join(root, "*.md"))
         if not os.path.basename(p).startswith("_")]
d.check("optional", "voice packs", bool(packs),
        ", ".join(packs) if packs else "none yet — copy config/voice/_TEMPLATE.md per brand")
d.check("optional", "_RULES.md", os.path.isfile(os.path.join(root, "_RULES.md")),
        "shared rules present" if os.path.isfile(os.path.join(root, "_RULES.md")) else "missing")
d.self_test()
sys.exit(d.finish("Ready. The pack is the source of truth; a missing pack refuses, never invents."))
