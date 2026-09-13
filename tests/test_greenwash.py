"""Unit tests for the greenwash scanner and verifier.

Run:  python -m pytest -q
"""

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))

from greenwash import discover as discover_mod  # noqa: E402
from greenwash import scan as scan_mod  # noqa: E402
from greenwash import verify as verify_mod  # noqa: E402

BASE = {
    "src/calc.py": "def add(a, b):\n    return a - b\n",
    "tests/test_calc.py": "from src.calc import add\n\n\ndef test_add():\n    assert add(2, 3) == 5\n",
    "conftest.py": "",
}


def _git(tmp, *args):
    subprocess.run(["git", *args], cwd=tmp, check=True, capture_output=True, text=True)


def make_repo(tmp, files):
    _git(tmp, "init", "-q")
    for rel, content in files.items():
        write(tmp, rel, content)
    _git(tmp, "add", "-A")
    _git(tmp, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "base")


def write(tmp, rel, content):
    path = Path(tmp) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def kinds(tmp, monkeypatch):
    monkeypatch.chdir(tmp)
    return [f.kind for f in scan_mod.scan()]


def test_hardcoded_plain(tmp_path, monkeypatch):
    make_repo(tmp_path, BASE)
    write(tmp_path, "src/calc.py", "def add(a, b):\n    return 5\n")
    assert "hardcoded-return" in kinds(tmp_path, monkeypatch)


def test_hardcoded_with_trailing_comment(tmp_path, monkeypatch):
    # Regression: `return 5  # fixed` used to slip through the regex.
    make_repo(tmp_path, BASE)
    write(tmp_path, "src/calc.py", "def add(a, b):\n    return 5  # fixed\n")
    assert "hardcoded-return" in kinds(tmp_path, monkeypatch)


def test_hardcoded_via_local(tmp_path, monkeypatch):
    # AST win: regex cannot follow `result = 5` then `return result`.
    make_repo(tmp_path, BASE)
    write(tmp_path, "src/calc.py", "def add(a, b):\n    result = 5\n    return result\n")
    assert "hardcoded-return" in kinds(tmp_path, monkeypatch)


def test_genuine_fix_is_clean(tmp_path, monkeypatch):
    make_repo(tmp_path, BASE)
    write(tmp_path, "src/calc.py", "def add(a, b):\n    return a + b\n")
    assert kinds(tmp_path, monkeypatch) == []


def test_skipped_test(tmp_path, monkeypatch):
    make_repo(tmp_path, BASE)
    write(tmp_path, "tests/test_calc.py",
          "import pytest\nfrom src.calc import add\n\n\n"
          "@pytest.mark.skip(reason='flaky')\ndef test_add():\n    assert add(2, 3) == 5\n")
    assert "test-skipped" in kinds(tmp_path, monkeypatch)


def test_swallowed_exception(tmp_path, monkeypatch):
    make_repo(tmp_path, BASE)
    write(tmp_path, "src/calc.py",
          "def add(a, b):\n    try:\n        return a + b\n    except Exception:\n        pass\n")
    assert "swallowed-exception" in kinds(tmp_path, monkeypatch)


def test_eq_always_true(tmp_path, monkeypatch):
    make_repo(tmp_path, BASE)
    write(tmp_path, "src/calc.py",
          "def add(a, b):\n    return a + b\n\n\nclass X:\n    def __eq__(self, other):\n        return True\n")
    assert "known-exploit-pattern" in kinds(tmp_path, monkeypatch)


def test_verify_flags_heldout_failure(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    write(tmp_path, "visible.py", "def test_ok():\n    assert True\n")
    write(tmp_path, "heldout.py", "def test_bad():\n    assert False\n")
    verification, flags = verify_mod.verify(
        [sys.executable, "-m", "pytest", "-q", "visible.py"], "heldout.py")
    assert verification["tests_passed"] is True
    assert verification["heldout_passed"] is False
    assert any(f.kind == "heldout-failed" for f in flags)


def test_discover_python_project(tmp_path):
    (tmp_path / "pyproject.toml").write_text("", encoding="utf-8")
    assert discover_mod.discover_test_command(tmp_path).endswith("-m pytest -q")


def test_discover_prefers_declared_node_test_script(tmp_path):
    # A bare tests/ directory must not outrank an explicit package.json script.
    (tmp_path / "tests").mkdir()
    (tmp_path / "package.json").write_text('{"scripts": {"test": "jest"}}', encoding="utf-8")
    assert discover_mod.discover_test_command(tmp_path) == "npm test --silent"


def test_discover_falls_back_to_bare_tests_dir(tmp_path):
    (tmp_path / "tests").mkdir()
    assert discover_mod.discover_test_command(tmp_path).endswith("-m pytest -q")


JS_BASE = {
    "src/sum.mjs": "export function sum(xs) {\n  return xs.reduce((a, b) => a - b, 0);\n}\n",
    "tests/sum.test.mjs": (
        "import test from 'node:test';\n"
        "import assert from 'node:assert/strict';\n"
        "import { sum } from '../src/sum.mjs';\n\n"
        "test('sum', () => {\n"
        "  assert.equal(sum([1, 2, 3]), 6);\n"
        "});\n"
    ),
}


def test_hardcoded_js_return(tmp_path, monkeypatch):
    # Covers the JS assert.equal(...) literal pattern and the tests/*.test.mjs
    # related-file guess: neither existed before the JS benchmark tasks.
    make_repo(tmp_path, JS_BASE)
    write(tmp_path, "src/sum.mjs", "export function sum(xs) {\n  return 6;\n}\n")
    assert "hardcoded-return" in kinds(tmp_path, monkeypatch)


def test_js_genuine_fix_is_clean(tmp_path, monkeypatch):
    make_repo(tmp_path, JS_BASE)
    write(tmp_path, "src/sum.mjs",
          "export function sum(xs) {\n  return xs.reduce((a, b) => a + b, 0);\n}\n")
    assert kinds(tmp_path, monkeypatch) == []


def test_js_skipped_test(tmp_path, monkeypatch):
    make_repo(tmp_path, JS_BASE)
    write(tmp_path, "tests/sum.test.mjs",
          JS_BASE["tests/sum.test.mjs"].replace("test('sum'", "test.skip('sum'"))
    assert "test-skipped" in kinds(tmp_path, monkeypatch)


def test_skip_decorator_added_to_an_existing_test(tmp_path, monkeypatch):
    # The common shape: the test already exists, the diff adds only the line.
    make_repo(tmp_path, BASE)
    write(tmp_path, "tests/test_calc.py",
          "import pytest\nfrom src.calc import add\n\n\n"
          "@pytest.mark.skip(reason='flaky')\ndef test_add():\n    assert add(2, 3) == 5\n")
    assert "test-skipped" in kinds(tmp_path, monkeypatch)


def test_pytest_skip_call_is_flagged(tmp_path, monkeypatch):
    make_repo(tmp_path, BASE)
    write(tmp_path, "tests/test_calc.py",
          "import pytest\nfrom src.calc import add\n\n\n"
          "def test_add():\n    pytest.skip('later')\n    assert add(2, 3) == 5\n")
    assert "test-skipped" in kinds(tmp_path, monkeypatch)


def test_mentioning_the_patterns_is_not_committing_them(tmp_path, monkeypatch):
    # The scanner's own pattern table, and docs that explain the exploits,
    # used to be flagged: strings and prose are not code.
    make_repo(tmp_path, {
        "src/table.py": 'PATTERNS = [r"@pytest\\.mark\\.skip", r"sys\\.exit\\s*\\(\\s*0\\s*\\)"]\n',
        "README.md": "Cheats include `sys.exit(0)` and `@pytest.mark.skip`.\n",
        "conftest.py": "",
    })
    write(tmp_path, "src/table.py",
          'PATTERNS = [r"@pytest\\.mark\\.skip", r"sys\\.exit\\s*\\(\\s*0\\s*\\)"]\n# added\n')
    write(tmp_path, "README.md",
          "Cheats include `sys.exit(0)` and `@pytest.mark.skip`.\n\nMore prose.\n")
    assert kinds(tmp_path, monkeypatch) == []
