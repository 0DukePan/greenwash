"""Discover how to run a project's tests, with no configuration."""

from __future__ import annotations

import json
import sys
from pathlib import Path

PY_MARKERS = ["pyproject.toml", "setup.cfg", "pytest.ini", "tox.ini", "setup.py"]


def discover_test_command(root=".") -> str | None:
    root = Path(root)
    if any((root / marker).is_file() for marker in PY_MARKERS):
        return f'"{sys.executable}" -m pytest -q'

    package_json = root / "package.json"
    if package_json.is_file():
        try:
            data = json.loads(package_json.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
        if data.get("scripts", {}).get("test"):
            return "npm test --silent"

    # Explicit markers first, then a declared test script; a bare tests/
    # directory is the weakest signal, so it comes last.
    if (root / "tests").is_dir():
        return f'"{sys.executable}" -m pytest -q'

    return None
