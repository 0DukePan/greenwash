"""Requirements: a claim decomposed into parts, each bound to its own evidence.

The rule under test is that nothing without evidence may be reported as a pass --
an unbound requirement is unverifiable, and a bound one that fails is a failed
check the claim depends on, which outranks any pattern match.
"""

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from greenwash import cli  # noqa: E402
from greenwash import verify as verify_mod  # noqa: E402
from greenwash.domain import Outcome, Requirement, TrustReport, Verdict  # noqa: E402
from greenwash.verify import requirements  # noqa: E402


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


PYTEST = f'"{sys.executable}" -m pytest -q'

GREEN = {
    "src/calc.py": "def add(a, b):\n    return a + b\n",
    "test_calc.py": "from src.calc import add\n\n\ndef test_add():\n    assert add(2, 3) == 5\n",
}


def test_parse_shapes():
    parsed = requirements.parse([
        "Login succeeds => tests/test_auth.py::test_login",
        "Token rotation",
        "Build stays green => cmd: pytest -q",
    ])
    assert [(r.text, r.kind, r.target) for r in parsed] == [
        ("Login succeeds", "test", "tests/test_auth.py::test_login"),
        ("Token rotation", "prose", ""),
        ("Build stays green", "command", "pytest -q"),
    ]


def test_parse_skips_an_empty_requirement():
    assert requirements.parse(["   => something", ""]) == []
    assert requirements.parse(None) == []


def test_a_test_id_needs_a_runner_that_takes_one():
    requirement = Requirement(text="x", kind="test", target="tests/a.py::b")
    assert requirements._command_for(requirement, "pytest -q") == 'pytest -q "tests/a.py::b"'
    assert requirements._command_for(requirement, "make test") == ""
    assert requirements._command_for(Requirement(text="x"), "pytest -q") == ""


def test_bound_requirement_that_passes(tmp_path, monkeypatch):
    _init(tmp_path, GREEN)
    monkeypatch.chdir(tmp_path)

    outcome = verify_mod.verify(
        auto=True, run_tests=PYTEST,
        requirements=["Addition works => test_calc.py::test_add"])
    assert [r.status for r in outcome.requirements] == [Outcome.PASS.value]
    assert not any(s.rule_id == "requirement-failed" for s in outcome.signals)

    report = TrustReport.build(verification=outcome.result, signals=outcome.signals,
                               requirements=outcome.requirements)
    assert report.verdict == Verdict.VERIFIED.value


def test_prose_requirement_is_never_a_pass(tmp_path, monkeypatch):
    _init(tmp_path, GREEN)
    monkeypatch.chdir(tmp_path)

    outcome = verify_mod.verify(
        auto=True, run_tests=PYTEST,
        requirements=["Addition works => test_calc.py::test_add", "Handles unicode"])
    assert [r.status for r in outcome.requirements] == [
        Outcome.PASS.value, Outcome.UNAVAILABLE.value]

    report = TrustReport.build(verification=outcome.result, signals=outcome.signals,
                               requirements=outcome.requirements)
    assert report.verdict == Verdict.PARTIALLY_VERIFIED.value
    assert any("no evidence bound" in reason for reason in report.confidence.reasons)


def test_failed_requirement_is_not_verified(tmp_path, monkeypatch):
    """A green visible suite does not rescue a requirement that does not hold."""
    _init(tmp_path, GREEN)
    monkeypatch.chdir(tmp_path)

    outcome = verify_mod.verify(
        auto=True, run_tests=PYTEST,
        requirements=["The build stays green => cmd: exit 1"])
    assert [r.status for r in outcome.requirements] == [Outcome.FAIL.value]
    assert any(s.rule_id == "requirement-failed" for s in outcome.signals)

    report = TrustReport.build(verification=outcome.result, signals=outcome.signals,
                               requirements=outcome.requirements)
    assert report.verdict == Verdict.NOT_VERIFIED.value
    assert report.verification.outcome == Outcome.PASS.value
    assert any(item.expected.startswith("The build stays green")
               for item in report.verification.evidence)


def test_the_cap_limits_how_many_run(tmp_path, monkeypatch):
    _init(tmp_path, GREEN)
    monkeypatch.chdir(tmp_path)

    outcome = verify_mod.verify(
        auto=True, run_tests=PYTEST, requirements=None)
    assert outcome.requirements == []

    listed, _ = requirements.run_requirements(
        [f"r{index} => cmd: exit 0" for index in range(4)],
        cwd=str(tmp_path), limit=2)
    assert [r.status for r in listed] == [
        Outcome.PASS.value, Outcome.PASS.value,
        Outcome.UNAVAILABLE.value, Outcome.UNAVAILABLE.value]
    assert "only the first 2" in listed[2].detail["reason"]


def test_requirements_survive_the_wire_format():
    report = TrustReport.build(requirements=[
        Requirement(text="Login succeeds", kind="test",
                    target="tests/test_auth.py::test_login", status=Outcome.PASS.value,
                    detail={"command": "pytest -q"}),
        Requirement(text="Handles unicode"),
    ])
    restored = TrustReport.from_dict(report.to_dict())
    assert [r.text for r in restored.requirements] == ["Login succeeds", "Handles unicode"]
    assert restored.requirements[0].kind == "test"
    assert restored.requirements[0].status == Outcome.PASS.value
    assert restored.requirements[1].status == Outcome.NOT_REQUESTED.value


def test_cli_require_reaches_the_report(tmp_path, monkeypatch, capsys):
    _init(tmp_path, GREEN)
    monkeypatch.chdir(tmp_path)

    code = cli.main(["--run-tests", PYTEST,
                     "--require", "Addition works => test_calc.py::test_add",
                     "--require", "Handles unicode",
                     "--json", "--no-color"])
    payload = capsys.readouterr().out
    assert code == 0
    assert '"text": "Addition works"' in payload
    assert '"text": "Handles unicode"' in payload
    assert '"verdict": "PARTIALLY_VERIFIED"' in payload


def test_cli_require_implies_verification(tmp_path, monkeypatch, capsys):
    """Naming a requirement is a request to check it, even with no other flag."""
    _init(tmp_path, GREEN)
    monkeypatch.chdir(tmp_path)

    cli.main(["--require", "The build stays green => cmd: exit 1", "--quiet"])
    assert "not_verified" in capsys.readouterr().out
