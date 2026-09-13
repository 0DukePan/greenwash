"""Finding out how to run this project's tests, with no configuration.

Order matters: an explicit test script beats a marker file, which beats a bare
`tests/` directory. Each detection carries where it came from, so `doctor` and
the first-run message can say *why* they believe what they believe.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

PY_MARKERS = ("pyproject.toml", "setup.cfg", "pytest.ini", "tox.ini", "setup.py")
JS_LOCKFILES = (("pnpm-lock.yaml", "pnpm test"),
                ("yarn.lock", "yarn test"),
                ("bun.lockb", "bun test"),
                ("package-lock.json", "npm test --silent"))


@dataclass
class Detection:
    command: Optional[str] = None
    kind: str = ""                 # pytest | npm | unknown
    source: str = ""               # what made us believe it
    detail: str = ""

    @property
    def found(self) -> bool:
        return bool(self.command)


def _pytest_command() -> str:
    return f'"{sys.executable}" -m pytest -q'


def detect(root=".") -> Detection:
    root = Path(root)

    package_json = root / "package.json"
    if package_json.is_file():
        try:
            data = json.loads(package_json.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
        script = (data.get("scripts") or {}).get("test")
        if script:
            for lock, command in JS_LOCKFILES:
                if (root / lock).is_file():
                    return Detection(command, "npm", lock, f'"test": "{script}"')
            return Detection("npm test --silent", "npm", "package.json",
                             f'"test": "{script}"')

    marker = next((m for m in PY_MARKERS if (root / m).is_file()), None)
    if marker:
        detail = "pytest configuration present"
        if marker == "pyproject.toml":
            text = (root / marker).read_text(encoding="utf-8", errors="ignore")
            if "pytest" in text:
                detail = "[tool.pytest.ini_options] in pyproject.toml"
        return Detection(_pytest_command(), "pytest", marker, detail)

    for candidate in ("tests", "test"):
        directory = root / candidate
        if directory.is_dir() and any(directory.rglob("test_*.py")):
            return Detection(_pytest_command(), "pytest", f"{candidate}/",
                             f"a {candidate}/ directory with test_*.py files")

    if (root / "tests").is_dir():
        return Detection(_pytest_command(), "pytest", "tests/", "a tests/ directory")

    return Detection(None, "", "", "no test command found")


def discover_test_command(root=".") -> Optional[str]:
    """Back-compat shim: the command, or None."""
    return detect(root).command


def changed_file_coverage(changed_paths, root=".") -> Optional[float]:
    """Share of changed source files that have a test file associated with them.

    A proxy, and named as one: it answers "does anything in this repo test the
    files this diff touched", not "which lines executed". Line coverage would
    need a coverage plugin the user may not have, and silently reporting 0%
    for a project without one would be a lie dressed as a number.
    """
    from ..gitutil import find_related_test_files

    source = [p for p in changed_paths
              if os.path.splitext(p)[1] in (".py", ".js", ".ts", ".jsx", ".tsx")
              and "test" not in os.path.basename(p).lower()
              and "spec" not in os.path.basename(p).lower()]
    if not source:
        return None
    covered = sum(1 for path in source if find_related_test_files(path, root))
    return round(covered / len(source), 3)
