"""The report: three formats, one truth, and no bare FAILED anywhere."""

import io
import json

import pytest

from greenwash.domain import (Claim, Evidence, FileChange, Outcome, Requirement, Run,
                              Signal, TrustReport, VerificationResult)
from greenwash.report import render, terminal

CAUGHT = Signal(rule_id="hardcoded-return", code="GW-TEST-004", title="Hardcoded return",
                category="test-integrity", severity="HIGH", confidence="MEDIUM",
                explanation="returns literal 200, which a test asserts against",
                files=["src/api.py"], line=42, remediation="Compute the value.")


def caught(**kwargs) -> TrustReport:
    verification = kwargs.pop("verification", VerificationResult(
        test_command="pytest -q", outcome=Outcome.PASS.value, tests_run=84, tests_passed=84,
        baseline=Outcome.PASS.value, heldout=Outcome.FAIL.value,
        heldout_detail={"passed": 2, "failed": 6},
        evidence=[Evidence(expected="API returns 401 for expired token",
                           observed="API returned 200",
                           source="held-out verification case #07")]))
    return TrustReport.build(
        run=Run(agent="claude-code", branch="feat/api", mode=kwargs.pop("mode", "report"),
                changed_files=[FileChange("src/api.py", 40, 9)],
                claim=Claim(text="Fixed payment validation")),
        signals=kwargs.pop("signals", [CAUGHT]), verification=verification, **kwargs)


def test_terminal_report_reads_like_a_report():
    text = render(caught())
    assert "GREENWASH TRUST REPORT" in text
    assert 'Agent claim: "Fixed payment validation"' in text
    assert "1 file changed, +40/-9" in text
    assert "Verdict: NOT_VERIFIED" in text
    assert "Confidence: " in text
    assert "Expected: API returns 401 for expired token" in text
    assert "Observed: API returned 200" in text


def test_no_bare_failure_is_ever_printed():
    """Every failing verdict carries evidence, in every format."""
    for fmt in ("terminal", "markdown", "json"):
        text = render(caught(), fmt=fmt)
        assert "NOT_VERIFIED" in text
        assert "401" in text           # the expected/observed pair
    terminal_text = render(caught())
    assert terminal_text.strip() != "FAILED"
    assert "FAILED\n" not in terminal_text


def test_a_never_verified_report_says_so():
    report = TrustReport.build(signals=[], verification=VerificationResult())
    text = render(report)
    assert "not run" in text
    assert "this report is a diff review only" in text
    assert report.confidence.level == "LOW"


def test_requires_review_is_spelled_out():
    review = Signal(rule_id="mock-in-test", code="GW-TEST-005", severity="MEDIUM",
                    explanation="new MagicMock( in a test file", files=["tests/t.py"],
                    requires_review=True)
    text = render(TrustReport.build(signals=[review], verification=VerificationResult()))
    assert "requires review -- not a failure by itself" in text


def test_quiet_is_one_line():
    text = render(caught(), quiet=True)
    assert len(text.strip().splitlines()) == 1
    assert "not_verified" in text
    assert "confidence" in text


def test_verbose_adds_the_change_list_and_every_reason():
    report = caught()
    terse, verbose = render(report), render(report, verbose=True)
    assert verbose.count("\n") > terse.count("\n")
    assert "src/api.py" in verbose
    assert all(reason in verbose for reason in report.confidence.reasons)


def test_markdown_is_paste_ready():
    text = render(caught(), fmt="markdown")
    assert text.startswith("## Greenwash trust report")
    assert "| Check | Result | Detail |" in text
    assert "**FAIL**" in text
    assert "<html" not in text and "<div" not in text


def test_json_is_versioned_and_first_key_is_the_schema():
    text = render(caught(), fmt="json")
    payload = json.loads(text)
    assert list(payload)[0] == "schema_version"
    assert payload["schema_version"] == "1"
    assert payload["signals"][0]["rule_id"] == "hardcoded-return"
    assert payload["verification"]["heldout"] == "fail"


def test_unknown_format_is_a_clear_error():
    with pytest.raises(ValueError):
        render(caught(), fmt="xml")


def test_ascii_console_is_survivable():
    """A default Windows console is cp1252: nothing may raise."""
    stream = io.TextIOWrapper(io.BytesIO(), encoding="cp1252")
    text = terminal.encode_safe(render(caught(), color=False), stream)
    text.encode("cp1252")          # would raise if anything slipped through
    assert "VERDICT" not in text   # the decorations degraded, the content did not
    assert "Verdict: NOT_VERIFIED" in text


def test_colour_is_opt_out():
    plain = render(caught(), color=False)
    painted = render(caught(), color=True)
    assert "\033[" not in plain
    assert "\033[" in painted


def test_signals_are_listed_with_their_code_and_location():
    text = render(caught())
    assert "[hardcoded-return]" in text
    assert "GW-TEST-004" in text
    assert "src/api.py:42" in text


REQUIREMENTS = [
    Requirement(text="Login succeeds", kind="test",
                target="tests/test_auth.py::test_login", status=Outcome.PASS.value),
    Requirement(text="Token rotation", kind="prose", status=Outcome.UNAVAILABLE.value,
                detail={"reason": "no evidence was bound to this requirement"}),
    Requirement(text="Rate limit resets", kind="test",
                target="tests/test_rate.py::test_reset", status=Outcome.FAIL.value,
                detail={"command": "pytest -q tests/test_rate.py"}),
]


def test_requirements_are_rendered_in_every_format():
    report = TrustReport.build(
        verification=VerificationResult(outcome=Outcome.PASS.value, tests_run=4,
                                        tests_passed=4),
        requirements=REQUIREMENTS)

    text = render(report)
    assert "Requirements:" in text
    assert "Login succeeds" in text
    assert "tests/test_auth.py::test_login" in text
    assert "no evidence was bound to this requirement" in text
    # a requirement the claim itself bound and failed is a failed check
    assert report.verdict == "NOT_VERIFIED"
    assert "do not hold" in text

    markdown_text = render(report, fmt="markdown")
    assert "### Requirements" in markdown_text
    assert "**FAIL**" in markdown_text
    assert "unverifiable" in markdown_text

    payload = json.loads(render(report, fmt="json"))
    assert [item["text"] for item in payload["requirements"]] == [
        "Login succeeds", "Token rotation", "Rate limit resets"]
    assert payload["requirements"][0]["status"] == "pass"


def test_the_integrity_line_reports_what_actually_ran():
    def report_for(integrity, detail=None):
        return TrustReport.build(verification=VerificationResult(
            outcome=Outcome.PASS.value, tests_run=1, tests_passed=1,
            integrity=integrity, integrity_detail=detail or {}))

    failed = render(report_for(Outcome.FAIL.value,
                               {"weakened": ["a::b", "c::d"],
                                "test_files": ["tests/test_x.py"]}))
    assert "Test integrity" in failed
    assert "2 case(s) fail in the committed version" in failed
    # and it cannot print that next to VERIFIED
    assert "Verdict: SUSPICIOUS" in failed

    passed = render(report_for(Outcome.PASS.value, {"test_files": ["tests/test_x.py"]}))
    assert "1 changed test file(s) still pass" in passed

    for outcome, shown in ((Outcome.UNAVAILABLE.value, "unavailable"),
                           (Outcome.NOT_REQUESTED.value, "not run")):
        line = next(line for line in render(report_for(outcome)).splitlines()
                    if "Test integrity" in line)
        assert shown in line

    markdown_failed = render(report_for(Outcome.FAIL.value, {"weakened": ["a::b"]}),
                             fmt="markdown")
    assert "| Test integrity | **FAIL** |" in markdown_failed
