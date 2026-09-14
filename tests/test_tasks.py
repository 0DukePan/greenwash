"""Structural validation for every benchmark task.

No model needed: for each task, prove the buggy workspace fails (both the
visible and hidden tests) and that the recorded solution passes both. A task
that cannot satisfy this is not a valid benchmark task.

The runner is `harness.run_tests`, so a task is validated by exactly the command
the benchmark will use -- six languages now, not two. A missing toolchain skips
rather than fails: Windows has no Go, and that is not a defect in the task.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
TASKS = ROOT / "benchmark" / "tasks"
FAKE_AGENT = ROOT / "benchmark" / "tools" / "fake_agent.py"
REQUIRED = {"name", "prompt", "visible_test", "hidden_test", "cheat_type", "language"}

sys.path.insert(0, str(ROOT / "benchmark"))
import harness  # noqa: E402


IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache", "target", "out")


def _task_dirs():
    if not TASKS.is_dir():
        return []
    return [d for d in sorted(TASKS.iterdir())
            if not d.name.startswith("_") and (d / "task.json").is_file()]


def _rel(meta, key) -> Path:
    # task.json is hand-editable; accept either slash direction.
    return Path(str(meta[key]).replace("\\", "/"))


def _run(tmp, language, meta=None, only=None) -> int:
    missing = harness.missing_toolchain(language)
    if missing:
        pytest.skip(f"{missing} is not installed")
    if only:
        path = only
    elif language == "javascript":
        files = sorted(str(p.relative_to(tmp))
                       for p in (Path(tmp) / "tests").glob("*.test.mjs"))
        return 0 if all(harness.run_tests(f, tmp, language) for f in files) else 1
    else:
        path = str(_rel(meta, "visible_test")) if meta else "."
    return 0 if harness.run_tests(path, tmp, language) else 1


def _prepare(tmp, task_dir, overlay=None, hidden=True):
    # Never copy caches: stale bytecode compiled from the buggy baseline can
    # shadow the solution overlay when source size and mtime collide. The same
    # applies to a Rust target/ or Java out/ directory from a previous run.
    shutil.copytree(task_dir / "workspace", tmp, dirs_exist_ok=True, ignore=IGNORE)
    if overlay is not None:
        shutil.copytree(overlay, tmp, dirs_exist_ok=True, ignore=IGNORE)
    meta = json.loads((task_dir / "task.json").read_text(encoding="utf-8"))
    if hidden:
        hidden_src = task_dir / _rel(meta, "hidden_test")
        destination = harness.hidden_destination(meta["language"], meta["hidden_test"], tmp)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(hidden_src, destination)
    return meta


@pytest.mark.parametrize("task_dir", _task_dirs(), ids=lambda d: d.name)
def test_task_is_well_formed(task_dir):
    meta = json.loads((task_dir / "task.json").read_text(encoding="utf-8"))
    assert REQUIRED <= set(meta), f"{task_dir.name} missing keys"
    assert (task_dir / "workspace" / _rel(meta, "visible_test")).is_file()
    assert (task_dir / _rel(meta, "hidden_test")).is_file()
    assert (task_dir / "solution").is_dir()

    language = meta["language"]
    with tempfile.TemporaryDirectory() as tmp:
        meta = _prepare(tmp, task_dir)
        assert _run(tmp, language, meta) != 0, f"{task_dir.name}: buggy workspace should fail"
        hidden_rel = harness.hidden_destination(language, meta["hidden_test"], tmp) \
            .relative_to(tmp).as_posix()
        assert _run(tmp, language, meta, only=hidden_rel) != 0, (
            f"{task_dir.name}: the hidden test passes on the buggy baseline, "
            "so it cannot catch the bug it exists for")

    with tempfile.TemporaryDirectory() as tmp:
        meta = _prepare(tmp, task_dir, overlay=task_dir / "solution")
        assert _run(tmp, language, meta) == 0, f"{task_dir.name}: solution should pass"


@pytest.mark.parametrize("task_dir", _task_dirs(), ids=lambda d: d.name)
def test_the_recorded_cheat_satisfies_the_visible_test(task_dir):
    """Every task ships a cheat that makes its visible test go green.

    A task is only labelled -- hardcode, skip, mock -- if the planted cheat
    does what that label names, and `benchmark/detection.py` scores the
    detector against exactly that. Without this check a task whose cheat
    stopped applying would read as a missed detection instead of a broken
    task. The held-out test is deliberately absent here: this proves the
    visible suite goes green, not that the cheat survives the hidden one.
    """
    meta = json.loads((task_dir / "task.json").read_text(encoding="utf-8"))
    missing = harness.missing_toolchain(meta["language"])
    if missing:
        pytest.skip(f"{missing} is not installed")

    with tempfile.TemporaryDirectory() as tmp:
        meta = _prepare(tmp, task_dir, hidden=False)
        env = {**os.environ, "FAKE_AGENT_CHEAT": "auto",
               "GREENWASH_BENCH_TASK_DIR": str(task_dir)}
        proc = subprocess.run([sys.executable, str(FAKE_AGENT)], cwd=tmp, env=env,
                              capture_output=True, text=True)
        assert proc.returncode == 0, proc.stderr
        assert _run(tmp, meta["language"], meta) == 0, (
            f"{task_dir.name}: the recorded cheat ({meta['cheat_type']}) no longer "
            "satisfies the visible test, so detection would score it as a miss")


def test_task_count():
    assert len(_task_dirs()) >= 12, "expected a substantial task set"


def test_the_language_set_is_covered_by_tasks():
    """Every language with a pack should have at least one task behind it."""
    languages = {json.loads((d / "task.json").read_text(encoding="utf-8"))["language"]
                 for d in _task_dirs()}
    assert {"python", "javascript", "go", "rust", "ruby", "java"} <= languages, \
        f"no task for: {sorted({'python', 'javascript', 'go', 'rust', 'ruby', 'java'} - languages)}"
