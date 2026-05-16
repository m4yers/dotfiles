"""Pytest stage1.

Adds ``scripts/`` to ``sys.path`` so tests can ``from engine
import ...`` the same way the runtime shim does (via PYTHONPATH in
plan.sh). Keeps tests invocable from any directory without requiring
the caller to remember to set PYTHONPATH.
"""
import sys
from pathlib import Path

# tests/ → curator/ (skill root) → scripts/
_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
