"""Structural validation for every benchmark task.

No model needed: for each task, prove the buggy workspace fails (both the
visible and hidden tests) and that the recorded solution passes both. A task
that cannot satisfy this is not a valid benchmark task.
"""

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
TASKS = ROOT / "benchmark" / "tasks"
REQUIRED = {"name", "prompt", "visible_test", "hidden_test", "cheat_type", "language"}


IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache")


def _task_dirs():
    if not TASKS.is_dir():
        return []
    return [d for d in sorted(TASKS.iterdir())
            if not d.name.startswith("_") and (d / "task.json").is_file()]


def _rel(meta, key) -> Path:
    # task.json is hand-editable; accept either slash direction.
    return Path(str(meta[key]).replace("\\", "/"))


def _run(tmp, language) -> int:
    if language == "javascript":
        node = shutil.which("node")
        if node is None:
            pytest.skip("node is not installed")
        files = sorted(str(p.relative_to(tmp))
                       for p in (Path(tmp) / "tests").glob("*.test.mjs"))
        cmd = [node, "--test", *files]
    else:
        cmd = [sys.executable, "-m", "pytest", "-q"]
    return subprocess.run(cmd, cwd=tmp, capture_output=True, text=True).returncode


def _prepare(tmp, task_dir, overlay=None):
    # Never copy caches: stale bytecode compiled from the buggy baseline can
    # shadow the solution overlay when source size and mtime collide.
    shutil.copytree(task_dir / "workspace", tmp, dirs_exist_ok=True, ignore=IGNORE)
    if overlay is not None:
        shutil.copytree(overlay, tmp, dirs_exist_ok=True, ignore=IGNORE)
    meta = json.loads((task_dir / "task.json").read_text(encoding="utf-8"))
    hidden_src = task_dir / _rel(meta, "hidden_test")
    shutil.copy(hidden_src, Path(tmp) / "tests" / hidden_src.name)


@pytest.mark.parametrize("task_dir", _task_dirs(), ids=lambda d: d.name)
def test_task_is_well_formed(task_dir):
    meta = json.loads((task_dir / "task.json").read_text(encoding="utf-8"))
    assert REQUIRED <= set(meta), f"{task_dir.name} missing keys"
    assert (task_dir / "workspace" / _rel(meta, "visible_test")).is_file()
    assert (task_dir / _rel(meta, "hidden_test")).is_file()
    assert (task_dir / "solution").is_dir()

    with tempfile.TemporaryDirectory() as tmp:
        _prepare(tmp, task_dir)
        assert _run(tmp, meta["language"]) != 0, f"{task_dir.name}: buggy workspace should fail"

    with tempfile.TemporaryDirectory() as tmp:
        _prepare(tmp, task_dir, overlay=task_dir / "solution")
        assert _run(tmp, meta["language"]) == 0, f"{task_dir.name}: solution should pass"


def test_task_count():
    assert len(_task_dirs()) >= 12, "expected a substantial task set"
