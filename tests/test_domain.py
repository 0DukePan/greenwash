"""The domain model: versioned, tolerant, and honest about missing data.

The wire format is a contract with other tools, so these tests pin the two
properties that matter: a report survives a round trip, and a malformed report
never raises.
"""

import json

from greenwash.domain import (SCHEMA_VERSION, Claim, Confidence, Evidence, FileChange,
                              Level, Outcome, Run, Signal, TrustReport,
                              VerificationResult, Verdict)


def test_schema_is_versioned():
    report = TrustReport.build()
    assert report.to_dict()["schema_version"] == "1"
    assert SCHEMA_VERSION == "1"


def test_round_trip_preserves_everything_that_matters():
    report = TrustReport.build(
        run=Run(agent="claude-code", branch="main", changed_files=[FileChange("a.py", 2, 1)],
                claim=Claim(text="fixed it")),
        signals=[Signal(rule_id="hardcoded-return", code="GW-TEST-004", severity="HIGH",
                        files=["a.py"], line=3, explanation="returns 5")],
        verification=VerificationResult(outcome="pass", tests_run=3, tests_passed=3,
                                        baseline="pass", heldout="fail",
                                        evidence=[Evidence(expected="401", observed="200")]))
    again = TrustReport.from_dict(json.loads(report.to_json()))
    assert again.verdict == report.verdict
    assert again.signals[0].rule_id == "hardcoded-return"
    assert again.signals[0].line == 3
    assert again.run.claim.text == "fixed it"
    assert again.run.changed_files[0].added == 2
    assert again.verification.heldout == "fail"
    assert again.verification.evidence[0].expected == "401"


def test_nested_models_serialize():
    run = Run(changed_files=[FileChange("a.py", 1, 2, "modified")], claim=Claim(text="x"))
    data = run.to_dict()
    assert data["changed_files"] == [{"path": "a.py", "added": 1, "removed": 2,
                                      "kind": "modified"}]
    assert data["claim"]["text"] == "x"


def test_missing_data_never_crashes_serialization():
    assert TrustReport.from_dict({}).verdict == Verdict.INCONCLUSIVE.value
    assert TrustReport.from_dict({"signals": None}).signals == []
    assert TrustReport.from_dict("not a dict").run is not None
    assert TrustReport.from_dict({"run": 5, "verification": [], "confidence": "no"}).run.agent == ""


def test_wrong_types_degrade_to_defaults():
    report = TrustReport.from_dict({"verdict": 42, "signals": [{"severity": "nonsense"},
                                                               {"rule_id": None}],
                                    "run": {"changed_files": "a.py"}})
    assert report.verdict == Verdict.INCONCLUSIVE.value
    assert report.signals[0].severity == Level.MEDIUM.value
    assert report.signals[1].rule_id == ""
    assert report.run.changed_files == [FileChange("a.py")]


def test_summary_lines_read_like_english():
    run = Run(changed_files=[FileChange("a.py", 40, 9), FileChange("b.py", 7, 3)])
    assert run.diff_summary() == "2 files changed, +47/-12"
    assert Run().diff_summary() == "no changes detected"
    assert VerificationResult(outcome="pass", tests_run=84, tests_passed=84).summary_line() == "84/84"
    assert VerificationResult().summary_line() == "not run"


def test_verdicts_parse_leniently():
    assert Verdict.parse("not_verified") is Verdict.NOT_VERIFIED
    assert Verdict.parse("  Verified ") is Verdict.VERIFIED
    assert Verdict.parse("???") is Verdict.INCONCLUSIVE


def test_confidence_sentence_has_no_fake_precision():
    confidence = Confidence(score=85, level="HIGH", reasons=["visible tests pass"])
    assert confidence.sentence() == "HIGH -- visible tests pass"
    assert "%" not in confidence.sentence()
