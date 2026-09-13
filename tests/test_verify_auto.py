"""Zero-config verification: baseline-vs-current differential."""

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))

from greenwash import verify as verify_mod  # noqa: E402


def _git(tmp, *args):
    subprocess.run(["git", *args], cwd=tmp, check=True, capture_output=True, text=True)


def _init(tmp, files):
    _git(tmp, "init", "-q")
    for rel, content in files.items():
        path = Path(tmp) / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    _git(tmp, "add", "-A")
    _git(tmp, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "base")


GREEN = {
    "src/calc.py": "def add(a, b):\n    return a + b\n",
    "test_calc.py": "from src.calc import add\n\n\ndef test_add():\n    assert add(2, 3) == 5\n",
}
PYTEST = f'"{sys.executable}" -m pytest -q'


def test_auto_flags_regression(tmp_path, monkeypatch):
    _init(tmp_path, GREEN)
    (tmp_path / "src" / "calc.py").write_text("def add(a, b):\n    return a - b\n")
    monkeypatch.chdir(tmp_path)
    verification, flags = verify_mod.verify(auto=True, run_tests=PYTEST)
    assert verification["baseline_passed"] is True
    assert verification["tests_passed"] is False
    assert any(f.kind == "regression" for f in flags)


def test_auto_clean_when_still_green(tmp_path, monkeypatch):
    _init(tmp_path, GREEN)
    monkeypatch.chdir(tmp_path)
    verification, flags = verify_mod.verify(auto=True, run_tests=PYTEST)
    assert verification["baseline_passed"] is True
    assert verification["tests_passed"] is True
    assert flags == []


def test_auto_does_not_flag_preexisting_failure(tmp_path, monkeypatch):
    # Already-red at baseline for an unrelated reason: staying red is
    # "tests-failed", not a regression -- we only flag NEW failures.
    red = dict(GREEN)
    red["test_calc.py"] = (
        "from src.calc import add\n\n\n"
        "def test_add():\n    assert add(2, 3) == 5\n\n\n"
        "def test_always_red():\n    assert False\n"
    )
    _init(tmp_path, red)
    monkeypatch.chdir(tmp_path)
    verification, flags = verify_mod.verify(auto=True, run_tests=PYTEST)
    assert verification["baseline_passed"] is False
    assert verification["tests_passed"] is False
    assert not any(f.kind == "regression" for f in flags)
    assert any(f.kind == "tests-failed" for f in flags)
