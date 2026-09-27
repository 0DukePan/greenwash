"""Test integrity: the committed version of a changed test, against the new code.

The case these exist for is the one the published measurement could not catch --
an agent that changes the test instead of the code. The baseline comparison runs
HEAD's tests against HEAD's code and the agent's run uses the agent's own tests,
so a loosened test passes in both.
"""

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from greenwash import gitutil  # noqa: E402
from greenwash import verify as verify_mod  # noqa: E402
from greenwash.domain import FileChange, Outcome, TrustReport, Verdict  # noqa: E402
from greenwash.scan import summarize  # noqa: E402
from greenwash.verify import integrity  # noqa: E402
from greenwash.verify.runner import RunResult  # noqa: E402


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


def _changes():
    """The change list the CLI would hand the verifier, built from the real diff."""
    changes, _ = summarize(gitutil.diff())
    return changes


PYTEST = f'"{sys.executable}" -m pytest -q'

GREEN = {
    "src/calc.py": "def add(a, b):\n    return a + b\n",
    "test_calc.py": (
        "from src.calc import add\n\n\n"
        "def test_add():\n    assert add(2, 3) == 5\n\n\n"
        "def test_add_negative():\n    assert add(-1, -1) == -2\n"
    ),
}


def test_weakened_test_is_caught(tmp_path, monkeypatch):
    """The agent breaks negatives and drops the test that would have noticed."""
    _init(tmp_path, GREEN)
    (tmp_path / "src" / "calc.py").write_text(
        "def add(a, b):\n    return abs(a) + abs(b)\n", encoding="utf-8")
    (tmp_path / "test_calc.py").write_text(
        "from src.calc import add\n\n\ndef test_add():\n    assert add(2, 3) == 5\n",
        encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    outcome = verify_mod.verify(auto=True, run_tests=PYTEST, changes=_changes())
    assert outcome.result.integrity == Outcome.FAIL.value
    assert outcome.result.integrity_detail["weakened"] == [
        "test_calc::test_add_negative"]
    weakened = [s for s in outcome.signals if s.rule_id == "test-weakened"]
    # pytest's JUnit id carries a dotted module name, not a path -- it resolves
    # here because exactly one changed test file answers to that module, and it
    # stays blank rather than guessing when the match is not exact (below).
    assert weakened and weakened[0].files == ["test_calc.py"]
    assert "test_calc::test_add_negative" in weakened[0].explanation


def test_case_id_is_only_attributed_to_a_real_path():
    changed = ["tests/test_calc.py"]
    assert integrity._path_for("tests/test_calc.py::test_add", changed) == "tests/test_calc.py"
    assert integrity._path_for("test_calc.py::test_add", changed) == "test_calc.py"
    # a dotted JUnit classname resolves through the changed-test-file list,
    # including the class-based shape pytest emits for a TestCase
    assert integrity._path_for("tests.test_calc::test_add", changed) == "tests/test_calc.py"
    assert integrity._path_for("tests.test_calc.TestCalc::test_add",
                               changed) == "tests/test_calc.py"
    # and never when it is ambiguous, unknown, or not a case id at all
    assert integrity._path_for("test_calc::test_add", []) == ""
    assert integrity._path_for("test_calc::test_add",
                               ["a/test_calc.py", "b/test_calc.py"]) == ""
    assert integrity._path_for("other::test_add", changed) == ""
    assert integrity._path_for("test_add", changed) == ""


def test_weakened_test_makes_the_report_suspicious(tmp_path, monkeypatch):
    """A HIGH-severity signal asks for an explanation -- it does not convict."""
    _init(tmp_path, GREEN)
    (tmp_path / "src" / "calc.py").write_text(
        "def add(a, b):\n    return abs(a) + abs(b)\n", encoding="utf-8")
    (tmp_path / "test_calc.py").write_text(
        "from src.calc import add\n\n\ndef test_add():\n    assert add(2, 3) == 5\n",
        encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    outcome = verify_mod.verify(auto=True, run_tests=PYTEST, changes=_changes())
    report = TrustReport.build(verification=outcome.result, signals=outcome.signals)
    assert report.verdict == Verdict.SUSPICIOUS.value
    # 50 neutral + 20 visible pass + 10 baseline pass, minus the high-severity
    # penalty for the weakened test: still short of HIGH, and never NOT_VERIFIED.
    assert report.confidence.level == "MEDIUM"


def test_added_test_file_is_not_weakening(tmp_path, monkeypatch):
    """A test the agent added does not exist at HEAD, so there is nothing to weaken."""
    _init(tmp_path, GREEN)
    (tmp_path / "test_extra.py").write_text(
        "from src.calc import add\n\n\ndef test_zero():\n    assert add(0, 0) == 0\n",
        encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    outcome = verify_mod.verify(auto=True, run_tests=PYTEST, changes=_changes())
    assert outcome.result.integrity == Outcome.PASS.value
    assert not any(signal.rule_id == "test-weakened" for signal in outcome.signals)


def test_an_unchanged_metadata_guard_is_not_mistaken_for_a_weakened_test(tmp_path, monkeypatch):
    """Only a changed test failing in its committed form is integrity evidence.

    A committed README-count guard sees the current README but the committed
    test tree, so adding a legitimate test makes its old count fail. That is
    metadata drift, not an agent loosening a test to fit broken code.
    """
    _init(tmp_path, {
        "README.md": "tests: 1\n",
        "src/calc.py": "def add(a, b):\n    return a + b\n",
        "tests/test_metadata.py": (
            "from pathlib import Path\n\n\n"
            "def test_documented_count_matches_suite():\n"
            "    count = len(list(Path('tests').glob('test_*.py')))\n"
            "    assert Path('README.md').read_text() == f'tests: {count}\\n'\n"
        ),
    })
    (tmp_path / "README.md").write_text("tests: 2\n", encoding="utf-8")
    (tmp_path / "tests" / "test_extra.py").write_text(
        "def test_new_coverage():\n    assert True\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    outcome = verify_mod.verify(auto=True, run_tests=PYTEST, changes=_changes())
    assert outcome.result.integrity == Outcome.PASS.value
    assert outcome.result.integrity_detail["unrelated_committed_failures"] == [
        "tests.test_metadata::test_documented_count_matches_suite"]
    assert not any(signal.rule_id == "test-weakened" for signal in outcome.signals)


def test_changed_conftest_keeps_affected_failures_attributable(tmp_path, monkeypatch):
    """A changed shared fixture can weaken an otherwise unchanged test."""
    (tmp_path / "test_calc.py").write_text("def test_valid(): pass\n", encoding="utf-8")
    current = integrity.results.TestOutcome(returncode=0, total=1, passed=1, failed=0,
                                            counts_available=True)
    committed = integrity.results.TestOutcome(
        returncode=1, total=1, passed=0, failed=1, counts_available=True,
        failing_ids=["test_calc::test_valid"])
    monkeypatch.setattr(integrity.results, "execute",
                        lambda *args, **kwargs: (RunResult(returncode=1), committed))

    outcome = integrity.check(
        "pytest", current, [FileChange(path="conftest.py")], str(tmp_path), cwd=str(tmp_path))
    assert outcome.outcome == Outcome.FAIL.value
    assert outcome.detail["weakened"] == ["test_calc::test_valid"]


def test_source_only_change_does_not_run_the_check(tmp_path, monkeypatch):
    _init(tmp_path, GREEN)
    (tmp_path / "src" / "calc.py").write_text(
        "def add(a, b):\n    return a + b\n\n\ndef sub(a, b):\n    return a - b\n",
        encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    outcome = verify_mod.verify(auto=True, run_tests=PYTEST, changes=_changes())
    assert outcome.result.integrity == Outcome.NOT_REQUESTED.value
    assert outcome.result.integrity_detail["reason"] == "no test file changed in this diff"


def test_turned_off_reports_why(tmp_path, monkeypatch):
    _init(tmp_path, GREEN)
    (tmp_path / "test_calc.py").write_text(
        "from src.calc import add\n\n\ndef test_add():\n    assert add(2, 3) == 5\n",
        encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    outcome = verify_mod.verify(auto=True, run_tests=PYTEST, changes=_changes(),
                                integrity=False)
    assert outcome.result.integrity == Outcome.NOT_REQUESTED.value
    assert outcome.result.integrity_detail["reason"] == "test integrity is turned off"


def test_the_cap_limits_how_many_cases_are_named(tmp_path, monkeypatch):
    cases = "\n\n\n".join(
        f"def test_case_{index}():\n    assert add({index}, 0) == {index}"
        for index in range(5))
    _init(tmp_path, {
        "src/calc.py": "def add(a, b):\n    return a + b\n",
        "test_calc.py": f"from src.calc import add\n\n\n{cases}\n",
    })
    # Every case now fails against the new code, and the edited test keeps none.
    (tmp_path / "src" / "calc.py").write_text(
        "def add(a, b):\n    return -1\n", encoding="utf-8")
    (tmp_path / "test_calc.py").write_text(
        "from src.calc import add\n\n\ndef test_add():\n    assert add(2, 3) == 5\n",
        encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    outcome = verify_mod.verify(auto=True, run_tests=PYTEST, changes=_changes(),
                                integrity_max=2)
    assert outcome.result.integrity == Outcome.FAIL.value
    assert len(outcome.result.integrity_detail["weakened"]) == 2
    assert len([s for s in outcome.signals if s.rule_id == "test-weakened"]) == 2


def test_conftest_is_held_at_head():
    """A patched conftest is part of the harness, not the implementation."""
    assert integrity.test_side("conftest.py")
    assert integrity.test_side("tests/conftest.py")
    assert integrity.test_side("test_calc.py")
    assert integrity.test_side("tests/test_calc.py")
    assert integrity.test_side("src/calc.spec.ts")
    assert not integrity.test_side("src/calc.py")


def test_an_unavailable_worktree_is_reported_not_guessed(tmp_path, monkeypatch):
    """A comparison that did not happen is never reported as a pass."""
    _init(tmp_path, GREEN)
    (tmp_path / "test_calc.py").write_text(
        "from src.calc import add\n\n\ndef test_add():\n    assert add(2, 3) == 5\n",
        encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(gitutil, "baseline_worktree", lambda cwd=None: None)

    outcome = verify_mod.verify(auto=True, run_tests=PYTEST, changes=_changes())
    assert outcome.result.integrity == Outcome.UNAVAILABLE.value
    assert "worktree" in outcome.result.integrity_detail["reason"]
    assert not any(signal.rule_id == "test-weakened" for signal in outcome.signals)
    assert any("test integrity: NOT AVAILABLE" in note for note in outcome.result.notes)


def test_a_runner_with_no_case_counts_falls_back_to_exit_status(tmp_path, monkeypatch):
    """No per-case names to compare is not the same as nothing to report.

    Plenty of runners print no summary line at all. The committed suite exiting
    non-zero where the edited one exits zero is still the signature, so it is
    reported -- and the detail says how it was judged.
    """
    _init(tmp_path, {
        "conftest.py": "",
        "src/calc.py": "def add(a, b):\n    return a + b\n",
        "tests/suite.py": "import sys\nprint('suite failed')\nsys.exit(1)\n",
    })
    (tmp_path / "tests" / "suite.py").write_text(
        "import sys\nprint('suite ok')\nsys.exit(0)\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    outcome = verify_mod.verify(auto=True, run_tests=f'"{sys.executable}" tests/suite.py',
                                changes=_changes())
    assert outcome.result.integrity == Outcome.FAIL.value
    assert "exit status" in outcome.result.integrity_detail["reason"]
    assert outcome.result.integrity_detail["weakened"] == []
    weakened = [s for s in outcome.signals if s.rule_id == "test-weakened"]
    assert weakened and "committed suite fails" in weakened[0].explanation
