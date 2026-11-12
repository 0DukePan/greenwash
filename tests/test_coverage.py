"""Requirement coverage: which promises have evidence, and which do not.

The engine's whole point is that it refuses to convert coverage into
correctness. These tests pin the four statuses, the negative-case heuristic,
the "could not run" distinction, and the exit-code ladder -- all without
running a project's tests for real, except where a real pytest invocation is
the cheapest honest fixture.
"""

import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

from greenwash import coverage  # noqa: E402


def row(**kwargs):
    built = coverage.Row(text=kwargs.pop("text", "r"), **kwargs)
    built.status = coverage.classify(built)
    return built


def binding(target="tests/test_x.py::test_one", kind="test", status="pass"):
    return coverage.Binding(target=target, kind=kind, status=status)


def test_repeating_a_sentence_binds_more_evidence():
    rows = coverage.merge([
        "Login succeeds => tests/a.py::test_one",
        "Login succeeds => tests/a.py::test_two",
        "Refresh rotates => cmd: python -c pass",
    ])
    assert [r.text for r in rows] == ["Login succeeds", "Refresh rotates"]
    assert [b.target for b in rows[0].bindings] == [
        "tests/a.py::test_one", "tests/a.py::test_two"]
    assert rows[1].bindings[0].kind == "command"


def test_one_pass_and_one_fail_is_contradictory_not_failed():
    """The two are different findings and must not be flattened.

    A requirement that fails everywhere is evidence the code is wrong. One that
    passes in one test and fails in another is evidence the *suite* disagrees
    with itself, which is a different thing to fix.
    """
    disagreed = row(bindings=[binding(status="pass"), binding(status="fail")])
    assert coverage.classify(disagreed) == coverage.CONTRADICTORY
    broken = row(bindings=[binding(status="fail")])
    assert coverage.classify(broken) == coverage.FAILED


def test_no_evidence_is_unverified_and_evidence_that_could_not_run_is_unavailable():
    assert coverage.classify(row()) == coverage.UNVERIFIED
    assert coverage.classify(row(bindings=[binding(status="unavailable")])) \
        == coverage.UNAVAILABLE


def test_a_negative_case_is_found_by_name_or_by_body(tmp_path):
    source = tmp_path / "tests" / "test_auth.py"
    source.parent.mkdir(parents=True)
    source.write_text(textwrap.dedent('''
        import pytest

        def test_accepts():
            assert login("a", "b") is True

        def test_rejects_bad_password():
            assert login("a", "x") is False

        def test_raises():
            with pytest.raises(ValueError):
                login(None, None)
    '''), encoding="utf-8")

    assert coverage.negative_case("tests/test_auth.py::test_rejects_bad_password",
                                  str(tmp_path)) == "present"
    assert coverage.negative_case("tests/test_auth.py::test_raises",
                                  str(tmp_path)) == "present"
    assert coverage.negative_case("tests/test_auth.py::test_accepts",
                                  str(tmp_path)) == "missing"


def test_a_name_that_says_reject_is_a_negative_case_even_without_source():
    """A test id is evidence about the test even when the file is unavailable."""
    assert coverage.negative_case("tests/whatever.py::test_rejects_expired", ".") \
        == "present"


def test_an_unreadable_target_is_unknown_not_missing():
    """Guessing here would be worse than saying so."""
    assert coverage.negative_case("test/does_not_exist.py::test_one", ".") == "unknown"
    assert coverage.negative_case("cmd: python -c pass", ".") == "unknown"


def test_the_report_says_coverage_is_not_correctness():
    rows = [row(text="a", bindings=[binding(status="pass")])]
    rendered = coverage.render(rows)
    assert "not a claim that the code is correct" in rendered
    assert "1 of 1 requirements have evidence that held up" in rendered


def test_the_summary_counts_every_status():
    rows = [
        row(text="ok", bindings=[binding(status="pass")]),
        row(text="bad", bindings=[binding(status="fail")]),
        row(text="split", bindings=[binding(status="pass"), binding(status="fail")]),
        row(text="empty"),
        row(text="unrunnable", bindings=[binding(status="unavailable")]),
    ]
    summary = coverage.summary(rows)
    assert summary["total"] == 5
    assert summary["verified"] == 1
    assert summary["failed"] == 1
    assert summary["contradictory"] == 1
    assert summary["unverified"] == 1
    assert summary["unavailable"] == 1


def test_the_cli_reports_the_four_states_with_the_documented_exit_codes(tmp_path):
    """The exit ladder is the contract: 0 verified, 1 failed, 2 unverified, 3 not run."""
    env = {**__import__("os").environ, "PYTHONPATH": str(ROOT)}

    def run(*args):
        return subprocess.run([sys.executable, "-m", "greenwash", "coverage", *args],
                              cwd=tmp_path, capture_output=True, text=True,
                              encoding="utf-8", errors="replace",
                              env=env, timeout=120)

    verified = run("--require", "nothing is checked", "--json")
    assert verified.returncode == 2, verified.stderr
    payload = json.loads(verified.stdout)
    assert payload["summary"]["unverified"] == 1

    nothing = run()
    assert nothing.returncode == 3, nothing.stderr

    # A command binding is the cheapest way to make a real pass and a real fail.
    contradictory = run(
        "--require", f"the command works => cmd: {sys.executable} -c 0",
        "--require", f"the command works => cmd: {sys.executable} -c 1/0",
        "--json")
    assert contradictory.returncode == 1, contradictory.stderr
    payload = json.loads(contradictory.stdout)
    assert payload["summary"]["contradictory"] == 1


@pytest.mark.skipif(sys.platform == "win32", reason="the shell quoting differs there")
def test_a_real_pytest_binding_reports_verified(tmp_path):
    (tmp_path / "test_one.py").write_text(
        "def test_ok():\n    assert True\n", encoding="utf-8")
    # PATH comes from the environment on purpose: stripping it made the child
    # unable to find `python`, and the test failed with "could not check"
    # rather than testing anything.
    env = {**__import__("os").environ, "PYTHONPATH": str(ROOT)}
    result = subprocess.run(
        [sys.executable, "-m", "greenwash", "coverage",
         "--require", "the test passes => test_one.py::test_ok",
         "--run-tests", f"{sys.executable} -m pytest -q",
         "--json"],
        cwd=tmp_path, capture_output=True, text=True, encoding="utf-8",
        errors="replace", env=env, timeout=180)
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["summary"]["verified"] == 1, payload
