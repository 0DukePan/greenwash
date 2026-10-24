"""The preliminary trial report: the friction round artifact, the usability
responses before and after the one wording revision, the static overhead per
repository, and the checker version and configuration, stated with their
denominators and sample sizes.

The report refuses by name whatever it cannot read, renders its licensed-wording
section from the claim ledger rows only, and states in one line that Gate C is
not decided and required mode is out of scope.

Every respondent label in the response fixture starts with `fixture-`: those
rows are invented for these tests and are never real participant data.
"""

import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "benchmark"))

import claim_ledger  # noqa: E402
import friction_round  # noqa: E402
import trial_report  # noqa: E402

FRICTION_FIXTURES = HERE / "fixtures" / "friction_round"
FIXTURES = HERE / "fixtures" / "trial_report"
PR_LOG = FRICTION_FIXTURES / "pr-log.json"
JUDGMENTS = FRICTION_FIXTURES / "judgments.json"
CONSENT = FRICTION_FIXTURES / "consent.json"
RESPONSES = FIXTURES / "responses.json"
OVERHEAD = FIXTURES / "overhead-alpha.json"
CHECKER = FIXTURES / "checker.json"


def friction_artifact(tmp_path):
    """The friction round's own artifact, produced by the round itself."""
    out = tmp_path / "friction-round.json"
    merged = tmp_path / "pr-log-reviewed.json"
    friction_round.run_round(PR_LOG, JUDGMENTS, CONSENT,
                             out=out, merged_log=merged)
    return out


def write_overhead(tmp_path, repository, runs_ms):
    path = tmp_path / f"overhead-{repository}.json"
    path.write_text(json.dumps({
        "repository": repository,
        "measurement": "static scan (scan --json, no test execution), "
                       "wall milliseconds",
        "runs_ms": runs_ms}), encoding="utf-8")
    return path


# -- the report: repositories, sizes, counts, the five measures -------------


def test_the_report_states_the_participating_repositories_and_their_sizes(
        tmp_path):
    report = trial_report.build(friction_artifact(tmp_path), RESPONSES,
                                [OVERHEAD], CHECKER)

    assert report["repositories"] == [
        {"repository": "alpha", "merged_prs": 5}]
    rendered = trial_report.render(report)
    assert "alpha: 5 merged pull requests replayed" in rendered


def test_the_report_states_the_pr_counts_with_their_denominators(tmp_path):
    report = trial_report.build(friction_artifact(tmp_path), RESPONSES,
                                [OVERHEAD], CHECKER)

    assert report["pr_counts"] == {
        "merged_prs": 5,
        "touched_tests": 4,
        "flagged": 3,
        "reviewed_alerts": 2,
        "unreviewed_alerts": 1,
        "with_both_timestamps": 2,
        "consented_repositories": 1}
    rendered = trial_report.render(report)
    assert ("pull requests that touched tests: 4 -- denominator: merged pull "
            "requests that touched tests") in rendered
    assert ("flagged pull requests: 3 -- denominator: flagged pull requests") \
        in rendered
    assert ("alerts with a recorded human judgment: 2 -- denominator: flagged "
            "pull requests with a recorded human judgment") in rendered
    assert "unreviewed alerts: 1 (never counted as unnecessary)" in rendered
    assert ("flagged pull requests with both timestamps: 2 -- denominator: "
            "flagged pull requests with both flagged_at and resolved_at") \
        in rendered


def test_the_report_states_the_five_friction_measures_with_denominators(
        tmp_path):
    report = trial_report.build(friction_artifact(tmp_path), RESPONSES,
                                [OVERHEAD], CHECKER)

    rendered = trial_report.render(report)
    measures = report["friction"]["measures"]
    assert (measures["interruption_rate"]["k"],
            measures["interruption_rate"]["n"]) == (3, 4)
    assert (measures["unnecessary_interruption_rate"]["k"],
            measures["unnecessary_interruption_rate"]["n"]) == (1, 2)
    assert measures["time_to_resolve_seconds"]["n"] == 2
    assert (measures["override_rate"]["k"],
            measures["override_rate"]["n"]) == (1, 3)
    assert (measures["removal_optout_rate"]["k"],
            measures["removal_optout_rate"]["n"]) == (0, 1)
    for denominator in ("merged pull requests that touched tests",
                        "flagged pull requests with a recorded human judgment",
                        "flagged pull requests with both flagged_at and "
                        "resolved_at",
                        "flagged pull requests",
                        "consented repositories appearing in the PR log"):
        assert denominator in rendered, denominator


def test_the_report_says_in_one_line_that_gate_c_is_not_decided(tmp_path):
    report = trial_report.build(friction_artifact(tmp_path), RESPONSES,
                                [OVERHEAD], CHECKER)

    rendered = trial_report.render(report)
    lines = [line for line in rendered.splitlines() if "Gate C" in line]
    assert lines == ["Gate C is not decided; required mode is out of scope."]
    assert "required mode is out of scope" in lines[0]


def test_the_report_states_the_open_questions(tmp_path):
    report = trial_report.build(friction_artifact(tmp_path), RESPONSES,
                                [OVERHEAD], CHECKER)

    assert len(report["open_questions"]) == 4
    rendered = trial_report.render(report)
    for question in report["open_questions"]:
        assert question in rendered


# -- usability before and after the one wording revision ---------------------


def test_the_report_states_usability_before_and_after_the_wording_revision(
        tmp_path):
    report = trial_report.build(friction_artifact(tmp_path), RESPONSES,
                                [OVERHEAD], CHECKER)

    assert report["usability"]["before"] == {
        "responses": 8, "correct": 5,
        "share_correct": 0.625, "median_seconds": 21.5}
    assert report["usability"]["after"] == {
        "responses": 8, "correct": 7,
        "share_correct": 0.875, "median_seconds": 14.5,
        "target": 0.80, "met": True}
    assert report["usability"]["wording_revision"] == 1
    rendered = trial_report.render(report)
    assert ("before the revision (round 1): 5 of 8 responses correct -- "
            "share correct 0.625, median time 21.5 s (8 responses).") in rendered
    assert ("after the revision (round 2): 7 of 8 responses correct -- "
            "share correct 0.875, median time 14.5 s (8 responses).") in rendered
    assert "one wording revision" in rendered


def test_responses_carrying_no_round_two_rows_are_refused_by_name(tmp_path):
    rows = json.loads(RESPONSES.read_text(encoding="utf-8"))
    only_before = tmp_path / "responses.json"
    only_before.write_text(json.dumps([row for row in rows if row["round"] == 1]),
                           encoding="utf-8")

    with pytest.raises(trial_report.Refusal) as excinfo:
        trial_report.build(friction_artifact(tmp_path), only_before,
                           [OVERHEAD], CHECKER)
    assert "round 2" in str(excinfo.value)


def test_a_response_row_outside_the_two_rounds_is_refused_by_name(tmp_path):
    rows = json.loads(RESPONSES.read_text(encoding="utf-8"))
    rows[0]["round"] = 3
    broken = tmp_path / "responses.json"
    broken.write_text(json.dumps(rows), encoding="utf-8")

    with pytest.raises(trial_report.Refusal) as excinfo:
        trial_report.build(friction_artifact(tmp_path), broken,
                           [OVERHEAD], CHECKER)
    assert "response.round" in str(excinfo.value)


# -- static overhead per repository, and the checker record ------------------


def test_the_report_states_static_overhead_per_repository_with_sample_size(
        tmp_path):
    overhead = write_overhead(tmp_path, "alpha", [402.0, 386.0, 394.0])

    report = trial_report.build(friction_artifact(tmp_path), RESPONSES,
                                [overhead], CHECKER)

    assert report["overhead"] == [{
        "repository": "alpha",
        "measurement": "static scan (scan --json, no test execution), "
                       "wall milliseconds",
        "runs": 3, "median_ms": 394.0}]
    rendered = trial_report.render(report)
    assert "alpha: median 394.0 ms over 3 runs" in rendered


def test_the_report_states_the_checker_version_and_configuration(tmp_path):
    report = trial_report.build(friction_artifact(tmp_path), RESPONSES,
                                [OVERHEAD], CHECKER)

    assert report["checker"] == {
        "version": "greenwash report-only beta (skill-only snapshot)",
        "configuration": {"mode": "report-only", "run_tests": False,
                          "strict": False}}
    rendered = trial_report.render(report)
    assert "version: greenwash report-only beta (skill-only snapshot)" \
        in rendered
    assert '"mode": "report-only"' in rendered


def test_an_overhead_file_for_a_repository_outside_the_trial_is_refused(
        tmp_path):
    outside = write_overhead(tmp_path, "beta", [300.0, 310.0])

    with pytest.raises(trial_report.Refusal) as excinfo:
        trial_report.build(friction_artifact(tmp_path), RESPONSES,
                           [OVERHEAD, outside], CHECKER)
    assert "'beta'" in str(excinfo.value)
    assert "absent from the trial" in str(excinfo.value)


def test_a_participating_repository_without_an_overhead_file_is_refused(
        tmp_path):
    with pytest.raises(trial_report.Refusal) as excinfo:
        trial_report.build(friction_artifact(tmp_path), RESPONSES, [],
                           CHECKER)
    assert "'alpha'" in str(excinfo.value)
    assert "no overhead measurement" in str(excinfo.value)


def test_a_malformed_overhead_measurement_is_refused_by_name(tmp_path):
    cases = {
        "repository": {"runs_ms": [300.0]},
        "runs_ms": {"repository": "alpha", "runs_ms": []},
        "run": {"repository": "alpha", "runs_ms": [300.0, 0]},
        "measurement": {"repository": "alpha", "runs_ms": [300.0]},
    }
    for field, payload in cases.items():
        path = tmp_path / f"broken-{field}.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        with pytest.raises(trial_report.Refusal) as excinfo:
            trial_report.build(friction_artifact(tmp_path), RESPONSES,
                               [path], CHECKER)
        assert "overhead" in str(excinfo.value), field
        assert str(path) in str(excinfo.value), field


def test_a_checker_record_missing_its_version_or_configuration_is_refused(
        tmp_path):
    for payload in ({"configuration": {}}, {"version": "x"},
                    {"version": "", "configuration": {}}):
        path = tmp_path / "checker.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        with pytest.raises(trial_report.Refusal) as excinfo:
            trial_report.build(friction_artifact(tmp_path), RESPONSES,
                               [OVERHEAD], path)
        assert "checker record" in str(excinfo.value)


# -- the licensed-wording section, from the claim ledger rows ----------------


def test_the_licensed_wording_section_renders_the_claim_ledger_rows(tmp_path):
    report = trial_report.build(friction_artifact(tmp_path), RESPONSES,
                                [OVERHEAD], CHECKER)

    section = trial_report.licensed_wording()
    for row in claim_ledger.rows():
        assert f"| {row.claim} | {row.allowed} |" in section
    rendered = trial_report.render(report)
    assert "## Licensed wording" in rendered
    assert "| Claim | Allowed wording |" in rendered
    assert "| detector-recall |" in rendered


def test_a_sentence_outside_the_ledger_rows_is_refused_by_name():
    with pytest.raises(trial_report.Refusal) as excinfo:
        trial_report.licensed_wording(
            ["The scanner always catches every planted cheat."])
    assert "The scanner always catches every planted cheat." \
        in str(excinfo.value)

    allowed = [row.allowed for row in claim_ledger.rows()]
    section = trial_report.licensed_wording(allowed[:1])
    assert f"| {claim_ledger.rows()[0].claim} | {allowed[0]} |" in section


# -- the beta guide explains how to join -------------------------------------


def test_the_beta_guide_explains_consent_the_export_and_what_an_owner_receives():
    text = (ROOT / "docs" / "beta.md").read_text(encoding="utf-8")
    start = text.lower().find("join the trial")
    assert start != -1
    section = text[start:].split("\n## ")[0].lower()
    for word in ("consent", "export", "receive"):
        assert word in section, word
