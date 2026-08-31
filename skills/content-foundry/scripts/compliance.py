#!/usr/bin/env python3
"""Shim. The canonical rules moved to skills/compliance-gate/scripts/fair_housing.py
when a fourth skill needed them — one copy in the bundle, ever.

Everything that did `import compliance` from this path keeps working, and the
CLI is the same tool at the new home. Do not add rules here; they belong in
compliance-gate, where every skill picks them up at once.
"""
import os, runpy, sys

_HERE = os.path.dirname(os.path.realpath(__file__))
_CANON = os.path.realpath(os.path.join(_HERE, "..", "..", "compliance-gate", "scripts"))
sys.path.insert(0, _CANON)

from fair_housing import *          # noqa: F401,F403
from fair_housing import (          # noqa: F401 — explicit for importers that reach for names
    BANNED, PROMISE, NEEDS_SOURCE, check, load_card, load_profile, report,
)

if __name__ == "__main__":
    sys.argv[0] = os.path.join(_CANON, "fair_housing.py")
    runpy.run_path(sys.argv[0], run_name="__main__")
