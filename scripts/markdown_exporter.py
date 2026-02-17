#!/usr/bin/env python3
"""Backward-compatible wrapper for scripts.legacy.planner.markdown_exporter."""

import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if __name__ == "__main__":
    runpy.run_module("scripts.legacy.planner.markdown_exporter", run_name="__main__")
else:
    from scripts.legacy.planner.markdown_exporter import *  # noqa: F401,F403

