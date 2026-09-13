"""Every rule, both ways: what it must catch, and what it must leave alone.

The negative cases are the point. A rule that only has positive tests is a
rule that will eventually eat someone's honest commit.
"""

import subprocess
import sys
import time
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from greenwash import scan as scan_mod  # noqa: E402
from greenwash.scan.rules import RULES  # noqa: E402

BASE = {
    "src/calc.py": "def add(a, b):\n    return a - b\n",
    "tests/test_calc.py": "from src.calc import add\n\n\ndef test_add():\n    assert add(2, 3) == 5\n",
    "conftest.py": "",
}


def _git(tmp, *args):
    subprocess.run(["git", *args], cwd=tmp, check=True, capture_output=True, text=True)


def _write(tmp, rel, content):
    path = Path(tmp) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _repo(tmp, files=None):
    _git(tmp, "init", "-q")
    for rel, content in (files or BASE).items():
        _write(tmp, rel, content)
    _git(tmp, "add", "-A")
    _git(tmp, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "base")


def _kinds(tmp, monkeypatch):
    monkeypatch.chdir(tmp)
    return [signal.rule_id for signal in scan_mod.scan()]


# (rule, path, new content, should the rule fire?)
CASES = [
    # a disabled test is caught; a docstring that merely mentions the marker is not
    ("test-skipped", "tests/test_calc.py",
     "import pytest\n\n\n@pytest.mark.skip(reason='later')\ndef test_add():\n    assert True\n", True),
    ("test-skipped", "tests/test_calc.py",
     '"""Talks about @pytest.mark.skip and self.skipTest in prose."""\n\n\n'
     "def test_add():\n    assert True\n", False),

    # weakening is a net loss of assertions, not any edit to a test
    ("assertion-weakened", "tests/test_calc.py",
     "def test_add():\n    pass\n", True),
    ("assertion-weakened", "tests/test_calc.py",
     "from src.calc import add\n\n\ndef test_add():\n    assert add(2, 3) == 5\n\n\n"
     "def test_more():\n    assert add(1, 1) == 2\n", False),

    # a literal a test asserts against; a literal nothing asserts passes by
    ("hardcoded-return", "src/calc.py", "def add(a, b):\n    return 5\n", True),
    ("hardcoded-return", "src/calc.py", "def add(a, b):\n    return 42\n", False),

    # mocks are flagged only where they can hide the unit under test
    ("mock-in-test", "tests/test_calc.py",
     "from unittest.mock import MagicMock\n\n\ndef test_add():\n    assert MagicMock()\n", True),
    ("mock-in-test", "src/calc.py",
     "from unittest.mock import MagicMock\n\n\ndef add(a, b):\n    return MagicMock()\n", False),

    # a swallowed error is caught; re-raising is not
    ("swallowed-exception", "src/calc.py",
     "def add(a, b):\n    try:\n        return a + b\n    except TypeError:\n        pass\n", True),
    ("swallowed-exception", "src/calc.py",
     "def add(a, b):\n    try:\n        return a + b\n    except TypeError:\n        raise\n", False),

    # the AlwaysEqual exploit, and ordinary equality
    ("known-exploit-pattern", "src/calc.py",
     "class X:\n    def __eq__(self, other):\n        return True\n", True),
    ("known-exploit-pattern", "src/calc.py",
     "class X:\n    def __eq__(self, other):\n        return self.value == other.value\n", False),

    # conftest.py is always worth a look
    ("conftest-changed", "conftest.py", "import pytest\n", True),
    ("conftest-changed", "src/calc.py", "def add(a, b):\n    return a + b\n", False),
]


@pytest.mark.parametrize("rule,path,content,expected", CASES,
                         ids=[f"{c[0]}-{'fires' if c[3] else 'quiet'}" for c in CASES])
def test_rule_positive_and_negative(tmp_path, monkeypatch, rule, path, content, expected):
    _repo(tmp_path)
    _write(tmp_path, path, content)
    kinds = _kinds(tmp_path, monkeypatch)
    assert (rule in kinds) is expected, f"{rule}: got {kinds}"


def test_test_file_deletion_is_caught(tmp_path, monkeypatch):
    _repo(tmp_path)
    (tmp_path / "tests" / "test_calc.py").unlink()
    _git(tmp_path, "add", "-A")
    assert "test-file-deleted" in _kinds(tmp_path, monkeypatch)


def test_deleting_a_source_file_is_not_a_deleted_test(tmp_path, monkeypatch):
    _repo(tmp_path)
    (tmp_path / "src" / "calc.py").unlink()
    _git(tmp_path, "add", "-A")
    assert "test-file-deleted" not in _kinds(tmp_path, monkeypatch)


def test_the_scanner_does_not_match_its_own_pattern_table(tmp_path, monkeypatch):
    """Regression: the exploit rule used to read the script that defines it.

    The pattern table contains `sys.exit(0)` and friends as string literals,
    and a docstring explaining an exploit is not an exploit. Python goes
    through the AST for exactly this reason.
    """
    _repo(tmp_path)
    _write(tmp_path, "src/notes.py",
           '"""Why sys.exit(0) and os._exit(0) and process.exit(0) are bad."""\n'
           'PATTERNS = ["sys.exit(0)", "os._exit(0)"]\n')
    assert "known-exploit-pattern" not in _kinds(tmp_path, monkeypatch)


# -- metadata -----------------------------------------------------------------

def test_every_rule_documents_itself():
    for rule in RULES:
        assert rule.id and rule.code and rule.title
        assert rule.description, f"{rule.id} has no description"
        assert rule.remediation, f"{rule.id} offers no remedy"
        assert rule.severity in ("HIGH", "MEDIUM", "LOW")
        assert rule.confidence in ("HIGH", "MEDIUM", "LOW")
        assert rule.category in ("test-integrity", "divergence", "exploit")


def test_codes_are_unique_and_well_formed():
    codes = [rule.code for rule in RULES]
    assert len(codes) == len(set(codes))
    for code in codes:
        assert code.startswith("GW-")
        assert len(code.split("-")) == 3


def test_asking_rules_never_convict():
    # a rule that only asks for a look must say so, and must not be high severity
    for rule in RULES:
        if rule.requires_review:
            assert rule.severity != "HIGH", f"{rule.id} both asks and convicts"


def test_the_readme_documents_every_rule():
    readme = (HERE.parent / "README.md").read_text(encoding="utf-8")
    undocumented = [rule.id for rule in RULES if f"`{rule.id}`" not in readme]
    assert undocumented == [], f"rules missing from the README table: {undocumented}"


# -- budget -------------------------------------------------------------------

def _synth(tmp, count):
    chunks = []
    for index in range(count):
        name = f"pkg{index // 50}/mod{index}.py"
        _write(tmp, name, f"def f{index}(a, b):\n    return a + b\n")
        chunks.append(
            f"diff --git a/{name} b/{name}\n--- a/{name}\n+++ b/{name}\n"
            f"@@ -1,0 +1,2 @@\n+def f{index}(a, b):\n+    return a + b\n")
    return "".join(chunks)


def test_five_hundred_file_diff_is_under_two_seconds(tmp_path):
    diff = _synth(tmp_path, 500)
    started = time.monotonic()
    signals = scan_mod.scan_diff(diff, cwd=str(tmp_path))
    elapsed = time.monotonic() - started
    assert signals == []
    assert elapsed < 2.0, f"500-file diff took {elapsed:.2f}s, budget is 2s"


def test_scan_is_scoped_to_the_directory_it_was_run_in(tmp_path, monkeypatch):
    """Regression, and an expensive one to learn.

    `git add -N -A` without a pathspec indexes the whole enclosing repository.
    Run from a subdirectory of a big checkout -- or from a temp directory that
    happens to sit under a `git init`-ed home directory, which is what happened
    here -- that is minutes of work and an index belonging to someone else.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _repo(repo)
    (repo / "elsewhere.py").write_text("def unrelated(a, b):\n    return 5\n", encoding="utf-8")
    work = repo / "sub"
    work.mkdir()
    (work / "calc.py").write_text("def add(a, b):\n    return 5\n", encoding="utf-8")

    monkeypatch.chdir(work)
    paths = {signal.path for signal in scan_mod.scan()}
    assert "sub/calc.py" in paths
    assert not any("elsewhere" in path for path in paths)


def test_subdirectory_run_still_resolves_related_tests(tmp_path, monkeypatch):
    # diff paths are repo-root relative, so the test that asserts the literal
    # has to be found relative to the root, not to the current directory
    repo = tmp_path / "repo"
    repo.mkdir()
    _repo(repo)
    (repo / "sub").mkdir()
    (repo / "sub" / "calc.py").write_text("def add(a, b):\n    return 5\n", encoding="utf-8")
    monkeypatch.chdir(repo / "sub")
    assert "hardcoded-return" in [s.rule_id for s in scan_mod.scan()]
