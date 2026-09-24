"""The compatibility entry point every integration actually calls.

`scripts/greenwash_check.py` is what the GitHub Action, `adapters/ci.sh` and the
pre-commit hook run, and its command line, stdout and exit codes are a published
contract. It had no functional test -- only a byte-comparison against the
benchmark's copy -- which is how the exit codes drifted from the table in its own
docstring without anything noticing, exactly as the enforce-mode codes did before
0.4.1.
"""

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
CHECK = ROOT / "scripts" / "greenwash_check.py"

GREEN = {
    "conftest.py": "",
    "src/calc.py": "def add(a, b):\n    return a + b\n",
    "tests/test_calc.py": (
        "from src.calc import add\n\n\n"
        "def test_add():\n    assert add(2, 3) == 5\n\n\n"
        "def test_add_negative():\n    assert add(-1, -1) == -2\n"
    ),
}


def _git(tmp, *args):
    subprocess.run(["git", *args], cwd=tmp, check=True, capture_output=True, text=True)


def _write(tmp, rel, content):
    path = Path(tmp) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _repo(tmp, files=None):
    _git(tmp, "init", "-q")
    for rel, content in (files or GREEN).items():
        _write(tmp, rel, content)
    _git(tmp, "add", "-A")
    _git(tmp, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "base")


def _run(tmp, *args):
    return subprocess.run([sys.executable, str(CHECK), *args], cwd=tmp,
                          capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


def test_clean_is_exit_zero(tmp_path):
    _repo(tmp_path)
    result = _run(tmp_path, "scan")
    assert result.returncode == 0, result.stderr
    assert "clean" in result.stdout


def test_a_flag_is_exit_one(tmp_path):
    _repo(tmp_path)
    _write(tmp_path, "src/calc.py", "def add(a, b):\n    return 5\n")
    result = _run(tmp_path, "scan")
    assert result.returncode == 1, result.stderr
    assert "hardcoded-return" in result.stdout


def test_a_tool_error_is_exit_two_not_one(tmp_path):
    """1 means "flags raised". A missing git is not a flagged diff.

    `sys.exit(message)` exits 1, so a CI job reading exit 1 as "your code was
    flagged" was told the wrong thing -- and the docstring, and
    `adapters/README.md`, both publish 2 for this.
    """
    _git(tmp_path, "init", "-q")          # a repository with no commits to diff
    result = _run(tmp_path, "scan")
    assert result.returncode == 2, result.stdout + result.stderr
    assert "no commits" in result.stderr
    assert result.stdout.strip() == ""


def test_json_is_machine_readable(tmp_path):
    _repo(tmp_path)
    _write(tmp_path, "src/calc.py", "def add(a, b):\n    return 5\n")
    result = _run(tmp_path, "scan", "--json")
    assert result.returncode == 1
    assert '"clean": false' in result.stdout
    assert '"hardcoded-return"' in result.stdout


def test_verify_reports_a_weakened_test(tmp_path):
    """The CI path gets the integrity check, not only the CLI and the hook.

    Without the change list the verifier cannot tell a test file was touched, so
    every Action, pre-commit and CI run would have silently skipped the one
    check that catches a suite edited to fit the code.
    """
    _repo(tmp_path)
    _write(tmp_path, "src/calc.py", "def add(a, b):\n    return abs(a) + abs(b)\n")
    _write(tmp_path, "tests/test_calc.py",
           "from src.calc import add\n\n\ndef test_add():\n    assert add(2, 3) == 5\n")

    result = _run(tmp_path, "verify", "--run-tests",
                  f'"{sys.executable}" -m pytest -q tests/test_calc.py')
    assert result.returncode == 1, result.stdout + result.stderr
    assert "test-weakened" in result.stdout
    assert "tests/test_calc.py" in result.stdout


def test_all_shares_one_diff_between_scan_and_verify(tmp_path):
    _repo(tmp_path)
    _write(tmp_path, "src/calc.py", "def add(a, b):\n    return abs(a) + abs(b)\n")
    _write(tmp_path, "tests/test_calc.py",
           "from src.calc import add\n\n\ndef test_add():\n    assert add(2, 3) == 5\n")

    result = _run(tmp_path, "all", "--run-tests",
                  f'"{sys.executable}" -m pytest -q tests/test_calc.py')
    assert result.returncode == 1
    assert "test-weakened" in result.stdout
