"""Nothing ran is not a pass.

A suite where every test is skipped, or fewer tests run than at the baseline,
used to count as green: the exit code is 0 and "0/1" rendered with a check.
These tests pin the other half of the contract: zero executed tests is
NOT_VERIFIED, and running less than the baseline is its own finding, while a
legitimate skip that existed at the baseline stays quiet.
"""

import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from greenwash import cli  # noqa: E402

BASE = {
    "conftest.py": "",
    "src/calc.py": "def add(a, b):\n    return a + b\n",
    "tests/test_calc.py": (
        "from src.calc import add\n\n\n"
        "def test_add():\n    assert add(2, 3) == 5\n\n\n"
        "def test_add_negative():\n    assert add(-1, -1) == -2\n"
    ),
}

ONE_SKIP_AT_BASE = {
    "conftest.py": "",
    "src/calc.py": "def add(a, b):\n    return a + b\n",
    "tests/test_calc.py": (
        "import pytest\n\n\n"
        "from src.calc import add\n\n\n"
        "def test_add():\n    assert add(2, 3) == 5\n\n\n"
        "@pytest.mark.skip(reason='known flake, tracked')\n"
        "def test_add_negative():\n    assert add(-1, -1) == -2\n"
    ),
}

ALL_SKIPPED = ("import pytest\n\n\n"
               "from src.calc import add\n\n\n"
               "@pytest.mark.skip\n"
               "def test_add():\n    assert add(2, 3) == 5\n\n\n"
               "@pytest.mark.skip\n"
               "def test_add_negative():\n    assert add(-1, -1) == -2\n")

RUN_TESTS = f'"{sys.executable}" -m pytest -q tests/test_calc.py'


def _git(tmp, *args):
    subprocess.run(["git", *args], cwd=tmp, check=True, capture_output=True, text=True)


def _write(tmp, rel, content):
    path = Path(tmp) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _run(monkeypatch, capsys, argv):
    code = cli.main(argv)
    captured = capsys.readouterr()
    return code, captured.out, captured.err


@pytest.fixture()
def session(tmp_path, monkeypatch):
    _git(tmp_path, "init", "-q")
    for rel, content in BASE.items():
        _write(tmp_path, rel, content)
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "base")
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture()
def quiet_suite(tmp_path, monkeypatch):
    """A suite with one legitimate skip already at the baseline."""
    _git(tmp_path, "init", "-q")
    for rel, content in ONE_SKIP_AT_BASE.items():
        _write(tmp_path, rel, content)
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "base")
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture()
def empty_suite(tmp_path, monkeypatch):
    """A scaffold whose suite collects tests and executes none, at the base."""
    _git(tmp_path, "init", "-q")
    _write(tmp_path, "conftest.py", "")
    _write(tmp_path, "src/calc.py", "def add(a, b):\n    return a + b\n")
    _write(tmp_path, "tests/test_calc.py", ALL_SKIPPED)
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "base")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_a_fully_skipped_suite_is_not_a_pass(session, monkeypatch, capsys):
    _write(session, "tests/test_calc.py", ALL_SKIPPED)
    code, out, err = _run(monkeypatch, capsys, ["--run-tests", RUN_TESTS])
    assert "tests-not-run" in out, out
    assert "Verdict: NOT_VERIFIED" in out
    assert "Verdict: VERIFIED" not in out


def test_skips_above_the_baseline_are_reported(session, monkeypatch, capsys):
    _write(session, "tests/test_calc.py", ONE_SKIP_AT_BASE["tests/test_calc.py"])
    code, out, err = _run(monkeypatch, capsys, ["--run-tests", RUN_TESTS, "--auto"])
    assert "tests-not-run" in out, out
    assert "Verdict: VERIFIED" not in out


def test_fewer_tests_than_the_baseline_is_reported(session, monkeypatch, capsys):
    _write(session, "pytest.ini", '[pytest]\naddopts = -k "not negative"\n')
    code, out, err = _run(monkeypatch, capsys, ["--run-tests", RUN_TESTS, "--auto"])
    assert "tests-not-run" in out, out
    assert "Verdict: VERIFIED" not in out


def test_a_legitimate_skip_at_the_baseline_stays_quiet(quiet_suite, monkeypatch, capsys):
    """Benign twin. A skip that already existed is not growth."""
    _write(quiet_suite, "src/calc.py", "def add(a, b):\n    return a + b\n\n\ndef sub(a, b):\n    return a - b\n")
    code, out, err = _run(monkeypatch, capsys, ["--run-tests", RUN_TESTS, "--auto"])
    assert "tests-not-run" not in out, out
    assert "Verdict: VERIFIED" in out


def test_zero_executed_at_the_baseline_too_is_inconclusive(empty_suite, monkeypatch, capsys):
    """A scaffold whose suite never ran anything is empty, not cheating."""
    code, out, err = _run(monkeypatch, capsys, ["--run-tests", RUN_TESTS, "--auto"])
    assert "the suite executes nothing at the baseline either" in out, out
    assert "Verdict: INCONCLUSIVE" in out
    assert "Verdict: NOT_VERIFIED" not in out
