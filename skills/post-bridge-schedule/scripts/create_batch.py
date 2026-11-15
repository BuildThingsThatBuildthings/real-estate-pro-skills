#!/usr/bin/env python3
"""Compatibility entrypoint: AIA scheduling is owned by Content Factory.

No local policy or legacy fallback executes here. Importers and CLI callers use
one canonical engine; a missing installation fails closed.
"""
import importlib
import os
from pathlib import Path
import runpy
import sys

root = Path(os.environ.get("CONTENT_FACTORY_ROOT", str(Path.home() / "content-factory"))).resolve()
entry = root / "engine" / "distribute" / "create_batch.py"
if not entry.is_file():
    raise RuntimeError("Canonical Content Factory scheduler is unavailable: " + str(entry))
sys.path.insert(0, str(root))
module_name = "engine.distribute.create_batch"
if __name__ == "__main__":
    runpy.run_module(module_name, run_name="__main__")
else:
    sys.modules[__name__] = importlib.import_module(module_name)
